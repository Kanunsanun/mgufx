"""埋め込み型スペクトラムアナライザー・ウィジェット

spectrum.py の FFT コア（リングバッファ + ホップ処理 + 対数表示 + 平滑化）を
移植し、独立 InputStream を持たない「受動的」ウィジェットにした。音声データは
Engine 側のコールバックから push() で供給される。

GEQ の背景に重ねて使うため:
  - カーソル / 右クリックメニュー等のインタラクションは持たない
  - 横軸（対数周波数レンジ）は set_band_range() で外部から固定できる
  - map_freq_to_x() で「周波数 → ウィジェット内 x 座標(px)」を返し、
    上に重ねる EQ スライダーの位置合わせに使う
"""

import numpy as np
import pyqtgraph as pg
from PyQt5 import QtCore, QtGui, QtWidgets


class SpectrumView(QtWidgets.QWidget):
    DB_FLOOR = -120.0
    DB_CEIL = 0.0
    SMOOTH_ALPHA = 0.72

    def __init__(self, fs=44100, fft_size=8192, parent=None):
        super().__init__(parent)
        self.fft_size = fft_size
        self._source_q = None      # Engine.spec_queue を後から接続
        self._band_range = None    # (f0, f1, n) 横軸固定用

        self._build_ui()
        self.configure(fs)

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._update)
        self.timer.start(16)       # ~60fps ポーリング

    # -- 設定 ---------------------------------------------------------------
    def set_queue(self, q):
        self._source_q = q

    def set_band_range(self, f0, f1, n):
        """横軸を 1/3oct バンド両端に合わせて固定（半バンド分のマージン付き）。"""
        self._band_range = (float(f0), float(f1), int(n))
        self._apply_band_range()

    def _apply_band_range(self):
        if not self._band_range:
            return
        f0, f1, n = self._band_range
        step = (np.log10(f1) - np.log10(f0)) / (n - 1) if n > 1 else 0.1
        self.plot.setXRange(np.log10(f0) - 0.5 * step,
                            np.log10(f1) + 0.5 * step, padding=0)

    def configure(self, fs):
        """サンプルレートに応じて FFT 周波数軸とバッファを再構築。"""
        self.fs = fs
        self.freqs = np.fft.rfftfreq(self.fft_size, 1.0 / fs)
        self.fmask = self.freqs >= 20.0
        self.x_freqs = np.maximum(self.freqs[self.fmask], 1e-6)
        # 手動 PlotCurveItem は logMode を自動適用しないため x は log10(Hz) を渡す
        self.log_x = np.log10(self.x_freqs)
        self.smooth = np.full(len(self.x_freqs), self.DB_FLOOR)
        self.ring = np.zeros(self.fft_size, dtype=np.float32)
        self.ring_pos = 0
        self.ordered = np.zeros(self.fft_size, dtype=np.float32)
        self.hann = np.hanning(self.fft_size).astype(np.float32)
        self.fft_ref = self.fft_size / 2.0
        self.curve.setData(self.log_x, self.smooth)
        if self._band_range:
            self._apply_band_range()
        else:
            fmax = min(fs / 2.0, 20000.0)
            self.plot.setXRange(np.log10(20.0), np.log10(fmax), padding=0.02)

    def map_freq_to_x(self, hz):
        """周波数(Hz) → このウィジェット内の x 座標(px)。重ね合わせ用。"""
        vb = self.plot.getViewBox()
        scene = vb.mapViewToScene(QtCore.QPointF(np.log10(hz), 0.0))
        p = self.plot.mapFromScene(scene)
        # plot はレイアウト余白0でこのウィジェットを満たすため座標系は一致
        return float(p.x())

    # -- 供給 ---------------------------------------------------------------
    def push(self, mono_block):
        n = len(mono_block)
        if n == 0:
            return
        end = self.ring_pos + n
        if end <= self.fft_size:
            self.ring[self.ring_pos:end] = mono_block
        else:
            split = self.fft_size - self.ring_pos
            self.ring[self.ring_pos:] = mono_block[:split]
            self.ring[: end - self.fft_size] = mono_block[split:]
        self.ring_pos = end % self.fft_size

    # -- UI -----------------------------------------------------------------
    def _build_ui(self):
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        pg.setConfigOptions(antialias=True)
        self.plot = pg.PlotWidget()
        self.plot.setBackground("#0d1117")
        self.plot.setLogMode(x=True, y=False)
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.plot.setYRange(self.DB_FLOOR, self.DB_CEIL)
        self.plot.setMouseEnabled(x=False, y=False)
        # インタラクション無効化（カーソル・右クリックメニュー等はオミット）
        self.plot.setMenuEnabled(False)
        self.plot.getViewBox().setMenuEnabled(False)
        self.plot.hideButtons()
        self.plot.setLabel("left", "dB", color="#56607a")
        self.plot.getAxis("bottom").setStyle(showValues=False)  # x目盛り文字は隠す
        for side in ("left", "bottom"):
            ax = self.plot.getAxis(side)
            ax.setPen(pg.mkPen("#222831"))
            ax.setTextPen(pg.mkPen("#56607a"))

        # カラフルな縦グラデーション塗り（上=大音量:赤 → 中:黄 → 下:緑）
        grad = QtGui.QLinearGradient(0, 0, 0, 1)
        grad.setCoordinateMode(QtGui.QGradient.ObjectBoundingMode)
        grad.setColorAt(0.0, QtGui.QColor(255, 70, 90, 200))    # 上(0dB側)
        grad.setColorAt(0.30, QtGui.QColor(255, 180, 60, 180))
        grad.setColorAt(0.60, QtGui.QColor(120, 255, 120, 150))
        grad.setColorAt(1.0, QtGui.QColor(40, 180, 255, 70))    # 下(底)
        self.curve = pg.PlotCurveItem(
            pen=pg.mkPen((180, 255, 255, 235), width=1.6),       # 明るいシアン白
            brush=QtGui.QBrush(grad),
            fillLevel=self.DB_FLOOR,
        )
        self.plot.addItem(self.curve)
        lay.addWidget(self.plot)

    # -- 更新ループ ---------------------------------------------------------
    def _update(self):
        updated = False
        q = self._source_q
        if q is not None:
            while not q.empty():
                try:
                    self.push(q.get_nowait())
                    updated = True
                except Exception:
                    break
        if not updated:
            return

        rp = self.ring_pos
        self.ordered[: self.fft_size - rp] = self.ring[rp:]
        self.ordered[self.fft_size - rp:] = self.ring[:rp]

        spec = np.abs(np.fft.rfft(self.ordered * self.hann))
        mag = spec[self.fmask]
        db = 20.0 * np.log10(mag / self.fft_ref + 1e-10)
        db = np.clip(db, self.DB_FLOOR, self.DB_CEIL)
        a = self.SMOOTH_ALPHA
        self.smooth[:] = a * self.smooth + (1.0 - a) * db
        self.curve.setData(self.log_x, self.smooth)
