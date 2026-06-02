"""DSP モジュール: グラフィックEQ / コンプレッサー / メーター検出

すべてのプロセッサはステレオ (frames, 2) の float32/float64 ブロックを
受け取り、同形状を返す。状態（フィルターの遅延・エンベロープ）は内部保持。
リアルタイムコールバック内から呼ばれるため、ブロック単位でベクトル化する。
"""

import numpy as np
from scipy.signal import sosfilt  # モジュールトップに移動（ホットパス毎回import防止）

# ISO 標準 1/3 オクターブ中心周波数 (Hz)
ISO_CENTERS = [
    20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500,
    630, 800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000,
    10000, 12500, 16000, 20000,
]


# ---------------------------------------------------------------------------
# Biquad ピーキングフィルター (RBJ Audio EQ Cookbook)
# ---------------------------------------------------------------------------
def _peaking_coeffs(fs, f0, gain_db, Q):
    """ピーキングEQの biquad 係数 (b, a) を返す。a[0]=1 に正規化済み。"""
    A = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * np.pi * f0 / fs
    alpha = np.sin(w0) / (2.0 * Q)
    cosw = np.cos(w0)
    b0 = 1 + alpha * A;  b1 = -2 * cosw;  b2 = 1 - alpha * A
    a0 = 1 + alpha / A;  a1 = -2 * cosw;  a2 = 1 - alpha / A
    b = np.array([b0, b1, b2], dtype=np.float64) / a0
    a = np.array([1.0, a1 / a0, a2 / a0], dtype=np.float64)
    return b, a


class GraphicEQ:
    """N バンドのピーキングフィルターを直列接続したグラフィックEQ。"""

    def __init__(self, fs, centers=ISO_CENTERS, Q=4.318):
        self.fs = fs
        self.Q = Q
        self.enabled = True
        nyq = fs / 2.0
        self.centers = [c for c in centers if c < nyq * 0.9]
        self.n = len(self.centers)
        self.gains_db = [0.0] * self.n
        self._sos = np.zeros((self.n, 6))
        self._zi = np.zeros((self.n, 2, 2))
        for i in range(self.n):
            self._update_band(i)

    def _update_band(self, i):
        b, a = _peaking_coeffs(self.fs, self.centers[i], self.gains_db[i], self.Q)
        self._sos[i, :3] = b
        self._sos[i, 3] = 1.0
        self._sos[i, 4:] = a[1:]

    def set_gain(self, i, gain_db):
        self.gains_db[i] = float(gain_db)
        self._update_band(i)

    def reset(self):
        self._zi[:] = 0.0

    def process(self, x):
        """x: (frames, 2) -> (frames, 2)。全バンド+両chを1回のsosfiltで処理。"""
        if not self.enabled:
            return x
        y, self._zi = sosfilt(self._sos, x, axis=0, zi=self._zi)
        return y


# ---------------------------------------------------------------------------
# ソフトニー共通関数（CompressorとCompGraphで共有）
# ---------------------------------------------------------------------------
def _soft_knee_gr(level_db, threshold_db, ratio, knee_db):
    """ソフトニーのゲインリダクション量(dB, <=0)をスカラーで返す。"""
    over = level_db - threshold_db
    half_k = knee_db / 2
    if over <= -half_k:
        return 0.0
    if over >= half_k:
        return -(over - over / ratio)
    x = over + half_k
    return -((1 - 1 / ratio) * x * x / (2 * max(knee_db, 1e-9)))


def _soft_knee_gr_vec(level_db_arr, threshold_db, ratio, knee_db):
    """_soft_knee_gr のベクトル版（numpy配列入力→numpy配列出力）。"""
    over = level_db_arr - threshold_db
    half_k = knee_db / 2
    above = -(over - over / ratio)
    knee = -((1 - 1 / ratio) * (over + half_k) ** 2 / (2 * max(knee_db, 1e-9)))
    return np.where(over <= -half_k, 0.0, np.where(over >= half_k, above, knee))


# ---------------------------------------------------------------------------
# コンプレッサー (ステレオリンク / フィードフォワード / 対数ドメイン)
# ---------------------------------------------------------------------------
class Compressor:
    def __init__(self, fs):
        self.fs = fs
        self.enabled = True
        self.threshold_db = -18.0
        self.ratio = 4.0
        self.attack_ms = 10.0
        self.release_ms = 120.0
        self.makeup_db = 0.0
        self.knee_db = 6.0
        self._env_db = 0.0  # ゲインリダクション包絡（dB, 0=無し）

    def _coeff(self, ms):
        return float(np.exp(-1.0 / (self.fs * max(ms, 0.01) / 1000.0)))

    def static_gain_db(self, level_db):
        """ソフトニーの静的入出力カーブ（スカラー版、グラフ描画用）。"""
        return _soft_knee_gr(level_db, self.threshold_db, self.ratio, self.knee_db)

    def process(self, x):
        """x: (frames, 2) -> (frames, 2)。ステレオリンク検出。"""
        if not self.enabled:
            self._env_db = 0.0
            return x
        n = x.shape[0]
        eps = 1e-9
        detect = np.maximum(np.abs(x[:, 0]), np.abs(x[:, 1]))

        # lvl_db・target_gr をベクトル計算（Pythonループから除外）
        lvl_db_arr = 20.0 * np.log10(detect + eps)
        target_gr_arr = _soft_knee_gr_vec(
            lvl_db_arr, self.threshold_db, self.ratio, self.knee_db)

        atk = self._coeff(self.attack_ms)
        rel = self._coeff(self.release_ms)
        makeup_lin = 10.0 ** (self.makeup_db / 20.0)

        # エンベロープ追従（本質的に逐次処理のためループは維持、body を最小化）
        env_db = self._env_db
        env_arr = np.empty(n, dtype=np.float64)
        for i in range(n):
            tg = target_gr_arr[i]
            c = atk if tg < env_db else rel
            env_db = c * env_db + (1 - c) * tg
            env_arr[i] = env_db
        self._env_db = env_db

        # gains をベクトル計算
        gains = (10.0 ** (env_arr / 20.0)) * makeup_lin
        return x * gains[:, None]

    @property
    def gain_reduction_db(self):
        return self._env_db


# ---------------------------------------------------------------------------
# ピークメーター検出（ブロックごとの dBFS ピーク）
# ---------------------------------------------------------------------------
def block_peak_dbfs(x):
    """x: (frames, 2) -> (left_db, right_db)。Pythonループなし。"""
    peaks = np.max(np.abs(x), axis=0)  # shape (2,), Cレイヤーで計算
    eps = 1e-6
    l = 20.0 * float(np.log10(peaks[0])) if peaks[0] > eps else -120.0
    r = 20.0 * float(np.log10(peaks[1])) if peaks[1] > eps else -120.0
    return l, r
