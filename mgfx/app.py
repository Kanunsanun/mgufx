"""GUI: グラフィックEQ + デジタルメーター + コンプレッサー（プロオーディオ刷新版）

実行: .venv\\Scripts\\python.exe -m mgfx.app   (asobiba ディレクトリから)

設計方針:
- 全カスタム描画は CachedWidget を継承し、静的背景を QPixmap にキャッシュ
  （resize時に1度だけ描画）。paintEvent は drawPixmap + 動的部分のみ。
  → リアルタイム音声を守るため GUI 描画負荷を最小化。
- テーマ（ライト/ダーク）は THEMES dict で集中管理。メーター/グラフは両テーマ
  とも暗背景固定（ライブ現場での視認性）。
"""

import sys
import os
import json
import math
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets

# プリセット保存形式の版数（DSP構造が大きく変わったら上げ、必要なら移行処理を追加）
PRESET_SCHEMA = 1

from . import __version__
from .engine import Engine, list_devices
from .dsp import _soft_knee_gr


# ---------------------------------------------------------------------------
# テーマ（パレット）— ライト/ダーク両対応。メーター/グラフは両方とも暗背景固定。
# ---------------------------------------------------------------------------
THEMES = {
    "dark": {
        "win_bg": "#121212", "panel_bg": "#1E1E1E", "panel_border": "#2E2E2E",
        "ctrl_bg": "#2A2A30", "text": "#E0E0E0", "text_dim": "#7A7A7A",
        "accent": "#00ADB5", "accent_dk": "#007E84",
        "accent2": "#FF5722", "accent2_dk": "#C63A12",
        # メーター（常に暗）
        "meter_bg": "#0A0A0C", "meter_frame": "#2A2A2E", "meter_text": "#B8B8C0",
        "z_green": "#00E676", "z_yellow": "#FFD600", "z_red": "#FF1744",
        # EQ
        "eq_track": "#333339", "eq_handle": "#E8E8EC", "eq_handle_bd": "#55555F",
        # コンプグラフ（常に暗）
        "graph_bg": "#0A1228", "graph_grid": "#243150", "graph_ref": "#8A90A4",
        "graph_curve": "#FF5722", "graph_thr": "#00ADB5", "graph_text": "#9FB0D0",
        # ノブ
        "knob_face": "#26262E", "knob_ring": "#3A3A44", "knob_text": "#E0E0E0",
        "knob_label": "#9AA0B0",
        # ON/OFF トグル
        "tog_on_bg": "#15292B", "tog_off_bg": "#202024", "tog_off_fg": "#6A6A72",
        # 巨大 START/STOP
        "run_bg": "#00E676", "run_fg": "#0A0A0A", "stop_bg": "#D32F2F", "stop_fg": "#FFFFFF",
    },
    "light": {
        "win_bg": "#ECECEF", "panel_bg": "#FBFBFD", "panel_border": "#D2D2D8",
        "ctrl_bg": "#FFFFFF", "text": "#1A1A20", "text_dim": "#6A6A72",
        "accent": "#0097A7", "accent_dk": "#006978",
        "accent2": "#E64A19", "accent2_dk": "#B23A10",
        "meter_bg": "#0A0A0C", "meter_frame": "#2A2A2E", "meter_text": "#B8B8C0",
        "z_green": "#00E676", "z_yellow": "#FFD600", "z_red": "#FF1744",
        "eq_track": "#C8CCD2", "eq_handle": "#FFFFFF", "eq_handle_bd": "#6B7280",
        "graph_bg": "#0A1228", "graph_grid": "#243150", "graph_ref": "#8A90A4",
        "graph_curve": "#E64A19", "graph_thr": "#00C2CC", "graph_text": "#9FB0D0",
        # ノブ: 白背景で視認できる濃さに
        "knob_face": "#FFFFFF", "knob_ring": "#AEB0BA", "knob_text": "#1A1A20",
        "knob_label": "#222222",
        # ON/OFF トグル
        "tog_on_bg": "#DAF4F5", "tog_off_bg": "#E6E6E9", "tog_off_fg": "#9A9AA2",
        # 巨大 START/STOP（緑はトーンを落とし白文字で上品に）
        "run_bg": "#00C853", "run_fg": "#FFFFFF", "stop_bg": "#D32F2F", "stop_fg": "#FFFFFF",
    },
}


def _rgba(hex_color, alpha):
    """'#RRGGBB' と alpha(0-255) → 'rgba(r,g,b,a)'。"""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def window_qss(t, has_bg=False):
    """ウィンドウ全体の QSS。has_bg=True（背景画像あり）のときは地を透過させ
    パネルを半透明にして、背景が透けるようにする（地は paintEvent が描く）。"""
    if has_bg:
        panel = _rgba(t["panel_bg"], 205)     # 半透明パネル（背景が透ける）
        scroll = "transparent"
    else:
        panel = t["panel_bg"]
        scroll = t["panel_bg"]
    return f"""
    QWidget {{ color: {t['text']}; }}
    QDialog {{ background: {t['win_bg']}; }}
    QGroupBox {{
        background: {panel}; border: 1px solid {t['panel_border']};
        border-radius: 6px; margin-top: 18px; font-weight: bold;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin; subcontrol-position: top left;
        left: 10px; padding: 2px 6px; color: {t['text']};
    }}
    QComboBox, QLineEdit {{
        background: {t['ctrl_bg']}; color: {t['text']};
        border: 1px solid {t['panel_border']}; border-radius: 4px; padding: 3px 6px;
    }}
    QComboBox QAbstractItemView {{
        background: {t['ctrl_bg']}; color: {t['text']};
        selection-background-color: {t['accent']};
    }}
    QPushButton {{
        background: {t['ctrl_bg']}; color: {t['text']};
        border: 1px solid {t['panel_border']}; border-radius: 4px; padding: 5px 12px;
    }}
    QPushButton:hover {{ border-color: {t['accent']}; }}
    QLabel {{ color: {t['text']}; background: transparent; }}
    QScrollArea {{ background: {scroll}; border: none; }}
    QScrollArea > QWidget > QWidget {{ background: {scroll}; }}
    """


# ---------------------------------------------------------------------------
# テキスト見切れ防止ヘルパー（QFontMetrics で実寸測定 → 収まる最大フォント、
# 最終手段は省略記号）。固定 point size に頼らず、領域に合わせて安全に描画する。
# ---------------------------------------------------------------------------
def draw_text_fit(p, rect, flags, text, max_pt, min_pt=6, bold=True):
    """rect に収まる最大フォントで text を描画。収まらなければ最小フォントで elide。

    boundingRect() で実際の描画寸法（幅・高さ）を測るため、フォント変更・
    DPI・文字種が変わっても領域外へはみ出さない。
    """
    f = p.font()
    f.setBold(bold)
    # ① 最大サイズで測る
    f.setPointSize(max_pt)
    p.setFont(f)
    br = p.fontMetrics().boundingRect(text)
    if br.width() <= rect.width() and br.height() <= rect.height():
        p.drawText(rect, flags, text)
        return
    # ② 余白比から適正サイズを一発算出（線形探索しない）
    scale = min(rect.width() / max(br.width(), 1),
                rect.height() / max(br.height(), 1))
    pt = max(min_pt, int(max_pt * scale))
    f.setPointSize(pt)
    p.setFont(f)
    br = p.fontMetrics().boundingRect(text)
    if br.width() <= rect.width() and br.height() <= rect.height():
        p.drawText(rect, flags, text)
        return
    # ③ それでも入らなければ最小フォントで省略記号
    f.setPointSize(min_pt)
    p.setFont(f)
    elided = p.fontMetrics().elidedText(text, QtCore.Qt.ElideRight, rect.width())
    p.drawText(rect, flags, elided)


# ---------------------------------------------------------------------------
# 自発光式 ON/OFF（BYPASS）スイッチ。プロ機材風インジケーターボタン。
#   ON  : 濃いグレー地＋シアン枠/文字＋点灯ドット
#   OFF : 消灯グレー＋"BYPASS"
# ---------------------------------------------------------------------------
class ToggleSwitch(QtWidgets.QPushButton):
    def __init__(self, on_text, off_text):
        super().__init__()
        self.on_text = on_text
        self.off_text = off_text
        self._t = THEMES["dark"]
        self.setCheckable(True)
        self.setChecked(True)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setMinimumHeight(30)
        # 長い方のテキスト("...BYPASS")が収まる幅を実測で確保（ドット＋余白込み）
        mf = QtGui.QFont(); mf.setBold(True); mf.setPointSize(11)
        fm = QtGui.QFontMetrics(mf)
        longest = max(on_text, off_text, key=lambda s: fm.horizontalAdvance(s))
        self.setMinimumWidth(30 + fm.horizontalAdvance(longest) + 18)
        # 既定の QPushButton 装飾を消して自前描画
        self.setStyleSheet("QPushButton { background: transparent; border: none; }")
        self.toggled.connect(lambda _=None: self.update())

    def set_theme(self, t):
        self._t = t
        self.update()

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        t = self._t
        on = self.isChecked()
        w, h = self.width(), self.height()
        if on:
            bg = QtGui.QColor(t["tog_on_bg"]); fg = QtGui.QColor(t["accent"])
        else:
            bg = QtGui.QColor(t["tog_off_bg"]); fg = QtGui.QColor(t["tog_off_fg"])
        # 枠＋地
        p.setBrush(bg)
        p.setPen(QtGui.QPen(fg, 1.5))
        p.drawRoundedRect(QtCore.QRectF(1, 1, w - 2, h - 2), 7, 7)
        # 点灯ドット（ON時はグロー付き）
        cx = 14.0
        cy = h / 2.0
        dr = max(4.0, h * 0.16)
        p.setPen(QtCore.Qt.NoPen)
        if on:
            glow = QtGui.QColor(t["accent"]); glow.setAlpha(70)
            p.setBrush(glow); p.drawEllipse(QtCore.QPointF(cx, cy), dr * 1.9, dr * 1.9)
            p.setBrush(QtGui.QColor(t["accent"]))
        else:
            p.setBrush(QtGui.QColor(t["tog_off_fg"]))
        p.drawEllipse(QtCore.QPointF(cx, cy), dr, dr)
        # テキスト
        txt = self.on_text if on else self.off_text
        p.setPen(fg)
        f = p.font(); f.setBold(True); f.setPointSize(max(8, min(11, h // 3)))
        p.setFont(f)
        p.drawText(QtCore.QRectF(cx + dr + 8, 0, w - (cx + dr + 8) - 8, h),
                   QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, txt)


# dBFS を 0..1 のメーター高さへ（-60dB を底とする）
def db_to_frac(db, floor=-60.0):
    if db <= floor:
        return 0.0
    if db >= 0.0:
        return 1.0
    return (db - floor) / (0.0 - floor)


# ---------------------------------------------------------------------------
# キャッシュ描画の基底クラス
#   _paint_static: 動かない要素（グリッド/目盛り/文字）→ resize時に QPixmap へ1度
#   _paint_dynamic: 毎フレーム動く要素（バー/針）→ paintEvent で上書き
# ---------------------------------------------------------------------------
class CachedWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._t = THEMES["dark"]
        self._bg = None

    def set_theme(self, t):
        self._t = t
        self._bg = None        # 背景キャッシュを無効化
        self.update()

    def resizeEvent(self, e):
        self._bg = None
        super().resizeEvent(e)

    def _render_bg(self):
        pm = QtGui.QPixmap(self.size())
        pm.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(pm)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        self._paint_static(p, self._t)
        p.end()
        self._bg = pm

    def paintEvent(self, _e):
        if self._bg is None or self._bg.size() != self.size():
            self._render_bg()
        p = QtGui.QPainter(self)
        p.drawPixmap(0, 0, self._bg)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        self._paint_dynamic(p, self._t)

    def _paint_static(self, p, t):
        pass

    def _paint_dynamic(self, p, t):
        pass


# ---------------------------------------------------------------------------
# 入出力ピークメーター（L/R 太い縦バー + 色ゾーン + dB目盛り）
# ---------------------------------------------------------------------------
class Meter(CachedWidget):
    TICKS = [0, -3, -6, -12, -18, -24, -40, -60]

    PAD_X = 6      # 左右の内側余白
    TEXT_GAP = 8   # 目盛り文字とバーの間の余白
    BAR_GAP = 4    # L/R バー間の余白

    def __init__(self, label="", mirror=False):
        super().__init__()
        self.label = label
        self.mirror = mirror             # True: 目盛りを右(外側)に配置(OUT用)
        self.vals = [-120.0, -120.0]     # L, R 現在値
        self.holds = [-120.0, -120.0]    # ピークホールド
        self._hold_decay = 0.6
        self.setMinimumSize(120, 200)

    def set_values(self, l, r):
        for i, v in enumerate((l, r)):
            self.vals[i] = v
            if v > self.holds[i]:
                self.holds[i] = v
            else:
                self.holds[i] -= self._hold_decay
        self.update()

    # 描画ジオメトリ（静的・動的で共有）。目盛り文字は sc_x..sc_x+sc_w に右寄せ、
    # バー領域(x_l/x_r)とは TEXT_GAP で必ず分離。mirror=True で目盛りを外側(右)へ。
    #   通常 : [PAD_X][目盛り][TEXT_GAP][L][BAR_GAP][R][PAD_X]
    #   反転 : [PAD_X][L][BAR_GAP][R][TEXT_GAP][目盛り][PAD_X]
    def fs_scale(self):
        return max(6, min(11, self.height() // 40))

    def _geom(self):
        w, h = self.width(), self.height()
        px = self.PAD_X
        fm = QtGui.QFontMetrics(QtGui.QFont("", self.fs_scale(), QtGui.QFont.Bold))
        # 真のグリフ幅(boundingRect)で確保（advanceより広い→符号クリップ防止）。
        # TICKS 中の最長文字列を実測。
        longest = max((f"{db}" for db in self.TICKS), key=lambda s: fm.boundingRect(s).width())
        sc_w = fm.boundingRect(longest).width() + 10
        bars_area = (w - px * 2) - sc_w - self.TEXT_GAP
        bw = (bars_area - self.BAR_GAP) // 2
        top = max(8, int(h * 0.03))
        # L/R ラベル専用の帯を確保し、バーと帯の間にも余白を取る（最下端で切らない）
        self._lr_band = max(18, min(26, h // 34))
        bar_h = h - top - self._lr_band - 4
        if self.mirror:
            x_l = px
            x_r = x_l + bw + self.BAR_GAP
            sc_x = x_r + bw + self.TEXT_GAP
        else:
            sc_x = px
            x_l = px + sc_w + self.TEXT_GAP
            x_r = x_l + bw + self.BAR_GAP
        return w, h, sc_x, sc_w, top, bar_h, bw, x_l, x_r

    def _y(self, db, top, bar_h):
        return top + bar_h * (1.0 - db_to_frac(db))

    def _paint_static(self, p, t):
        w, h, sc_x, sc_w, top, bar_h, bw, x_l, x_r = self._geom()
        p.fillRect(0, 0, w, h, QtGui.QColor(t["meter_bg"]))
        # バー枠（near-black 地に対しトラックを少し明るくして視認性を上げる）
        frame = QtGui.QColor(t["meter_frame"])
        for x in (x_l, x_r):
            p.fillRect(x, top, bw, bar_h, QtGui.QColor(38, 38, 48))
            p.setPen(QtGui.QPen(frame, 1))
            p.drawRect(x, top, bw, bar_h)
        # dB 目盛り（sc_x..sc_x+sc_w に右寄せ・draw_text_fit で確実に収める）
        fs = self.fs_scale()
        for db in self.TICKS:
            y = int(self._y(db, top, bar_h))
            p.setPen(QtGui.QColor(t["meter_text"]))
            draw_text_fit(p, QtCore.QRect(sc_x, y - 9, sc_w, 18),
                          QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,
                          f"{db}", max_pt=fs, min_pt=6)
            # 目盛り線
            p.setPen(QtGui.QPen(QtGui.QColor(t["meter_frame"]), 1))
            p.drawLine(x_l, y, x_l + bw, y)
            p.drawLine(x_r, y, x_r + bw, y)
        # L/R ラベル（専用帯に収める。widget 最下端には 2px 余白を残す）
        lr_y = top + bar_h + 2
        lr_h = h - lr_y - 2
        fs2 = max(8, min(14, self._lr_band - 2))
        p.setPen(QtGui.QColor(t["meter_text"]))
        draw_text_fit(p, QtCore.QRect(x_l, lr_y, bw, lr_h),
                      QtCore.Qt.AlignCenter, "L", max_pt=fs2, min_pt=7)
        draw_text_fit(p, QtCore.QRect(x_r, lr_y, bw, lr_h),
                      QtCore.Qt.AlignCenter, "R", max_pt=fs2, min_pt=7)

    def _paint_dynamic(self, p, t):
        w, h, sc_x, sc_w, top, bar_h, bw, x_l, x_r = self._geom()
        zones = [(-60.0, -18.0, t["z_green"]),
                 (-18.0, -3.0,  t["z_yellow"]),
                 (-3.0,   3.0,  t["z_red"])]
        for ch, x in ((0, x_l), (1, x_r)):
            v = self.vals[ch]
            # 色ゾーンを最大3矩形で塗る（1pxループを避ける）
            for lo_db, hi_db, col in zones:
                if v <= lo_db:
                    continue
                top_db = min(v, hi_db)
                y_top = self._y(top_db, top, bar_h)
                y_bot = self._y(lo_db, top, bar_h)
                p.fillRect(QtCore.QRectF(x + 1, y_top, bw - 2, y_bot - y_top),
                           QtGui.QColor(col))
            # ピークホールド線
            hy = int(self._y(self.holds[ch], top, bar_h))
            p.fillRect(x + 1, hy - 1, bw - 2, 2, QtGui.QColor(255, 255, 255))


# ---------------------------------------------------------------------------
# ゲインリダクション横バー（グラフ直下、右→左へ伸びる）
# ---------------------------------------------------------------------------
class GRBar(CachedWidget):
    """ゲインリダクション横メーター。右端(0dB)から左へ伸びる。
    数値目盛りは詰め込みすぎになるため廃止し、基準線(線のみ)を引く。
    ラベル・現在値は draw_text_fit で領域に収める。
    """
    GR_MAX = 24.0
    TICK_LINES = [-6, -12, -18]   # 基準線（数値は付けない＝見切れ要因を排除）
    LBL_W = 40                    # 左の "GR" ラベル領域

    def __init__(self):
        super().__init__()
        self.gr = 0.0
        self.setMinimumHeight(40)
        self.setMaximumHeight(58)

    def set_value(self, gr_db):
        self.gr = gr_db
        self.update()

    def _track(self):
        w, h = self.width(), self.height()
        tx = self.LBL_W
        tw = w - tx - 6
        ty, th = 4, h - 8
        return tx, ty, tw, th

    def _x_for(self, gr_db, tx, tw):
        frac = (-max(min(gr_db, 0.0), -self.GR_MAX)) / self.GR_MAX
        return tx + tw - tw * frac

    def _paint_static(self, p, t):
        w, h = self.width(), self.height()
        tx, ty, tw, th = self._track()
        p.fillRect(0, 0, w, h, QtGui.QColor(t["meter_bg"]))
        # トラック枠
        p.fillRect(tx, ty, tw, th, QtGui.QColor(28, 28, 32))
        p.setPen(QtGui.QPen(QtGui.QColor(t["meter_frame"]), 1))
        p.drawRect(tx, ty, tw, th)
        # 基準線（数値なし）
        for db in self.TICK_LINES:
            x = int(self._x_for(db, tx, tw))
            p.drawLine(x, ty, x, ty + th)
        # "GR" ラベル（左領域に収める）
        p.setPen(QtGui.QColor(t["meter_text"]))
        draw_text_fit(p, QtCore.QRect(4, ty, self.LBL_W - 8, th),
                      QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft,
                      "GR", max_pt=12, min_pt=7)

    def _paint_dynamic(self, p, t):
        tx, ty, tw, th = self._track()
        x_cur = self._x_for(self.gr, tx, tw)
        fw = (tx + tw) - x_cur
        if fw > 1:
            grad = QtGui.QLinearGradient(x_cur, 0, tx + tw, 0)
            grad.setColorAt(0.0, QtGui.QColor(t["z_red"]))
            grad.setColorAt(1.0, QtGui.QColor(t["accent2"]))
            p.fillRect(QtCore.QRectF(x_cur, ty + 1, fw, th - 2), QtGui.QBrush(grad))
        # 現在値（トラック右に収める）
        p.setPen(QtGui.QColor(255, 255, 255))
        draw_text_fit(p, QtCore.QRect(tx + 4, ty, tw - 8, th),
                      QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight,
                      f"{self.gr:.1f} dB", max_pt=11, min_pt=7)


# ---------------------------------------------------------------------------
# コンプレッサー伝達特性グラフ（静的グリッド/曲線をキャッシュ）
# ---------------------------------------------------------------------------
class CompGraph(CachedWidget):
    DB_MIN = -60.0
    DB_MAX = 0.0

    def __init__(self):
        super().__init__()
        self.threshold_db = -18.0
        self.ratio = 4.0
        self.knee_db = 6.0
        self.makeup_db = 0.0
        self.setMinimumSize(180, 150)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                           QtWidgets.QSizePolicy.Expanding)

    def set_params(self, thr, ratio, knee, makeup):
        self.threshold_db = thr
        self.ratio = ratio
        self.knee_db = knee
        self.makeup_db = makeup
        self._bg = None        # 曲線は静的キャッシュに含むため再生成
        self.update()

    def _static_gain(self, in_db):
        return in_db + _soft_knee_gr(in_db, self.threshold_db, self.ratio, self.knee_db)

    def _paint_static(self, p, t):
        W, H = self.width(), self.height()
        p.fillRect(0, 0, W, H, QtGui.QColor(t["graph_bg"]))

        # 先に軸フォントを決め、Y軸ラベルの実幅から左マージンを算出
        # （"-60dB" が枠線を突き抜けないようフォント連動で余白を確保）
        fs = max(7, min(12, H // 16))
        f = p.font(); f.setPointSize(fs); f.setBold(True); p.setFont(f)
        fm = p.fontMetrics()
        lh = fm.height()
        TXT_PAD = 8
        # Y軸ラベル("-60dB")が fs のまま収まるよう boundingRect 基準で左マージン確保
        ylabel_w = fm.boundingRect("-60dB").width()
        PAD_L = max(55, ylabel_w + TXT_PAD + 14)
        PAD_R, PAD_T, PAD_B = 15, 12, max(24, lh + 10)

        # プロット領域（マージンを引いた内側の長方形）
        gx0, gx1 = PAD_L, W - PAD_R
        gy0, gy1 = PAD_T, H - PAD_B
        gw, gh = gx1 - gx0, gy1 - gy0

        def ix(db):
            return gx0 + int((db - self.DB_MIN) / (self.DB_MAX - self.DB_MIN) * gw)

        def oy(db):
            return gy1 - int((db - self.DB_MIN) / (self.DB_MAX - self.DB_MIN) * gh)

        # グリッド（すべて内側長方形に収まる）
        p.setPen(QtGui.QPen(QtGui.QColor(t["graph_grid"]), 1))
        for db in (-60, -40, -20, 0):
            p.drawLine(ix(db), gy0, ix(db), gy1)
            p.drawLine(gx0, oy(db), gx1, oy(db))

        # 軸ラベル — X/Y を同一フォントサイズ(fs)で固定描画。
        # PAD_L は "-60dB" が fs で収まるよう確保済みなので縮小不要＝両軸サイズが揃う。
        p.setFont(f)
        p.setPen(QtGui.QColor(t["graph_text"]))
        # X軸（下マージン内に中央寄せ。-60は端で重なるため省略）
        for db in (-40, -20, 0):
            p.drawText(QtCore.QRect(ix(db) - 24, gy1 + 2, 48, PAD_B - 2),
                       QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop, str(db))
        # Y軸（左余白に右寄せ → 枠線を突き抜けない）
        for db in (-60, -40, -20, 0):
            p.drawText(QtCore.QRect(0, oy(db) - lh // 2 - 1, PAD_L - TXT_PAD, lh + 2),
                       QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter, f"{db}dB")

        # 1:1 参照線
        p.setPen(QtGui.QPen(QtGui.QColor(t["graph_ref"]), 1, QtCore.Qt.DashLine))
        p.drawLine(ix(self.DB_MIN), oy(self.DB_MIN), ix(self.DB_MAX), oy(self.DB_MAX))

        # スレッショルド縦線
        p.setPen(QtGui.QPen(QtGui.QColor(t["graph_thr"]), 1, QtCore.Qt.DashLine))
        p.drawLine(ix(self.threshold_db), gy0, ix(self.threshold_db), gy1)

        # 伝達特性曲線
        steps = max(gw, 60)
        pts = []
        for s in range(steps + 1):
            in_db = self.DB_MIN + s * (self.DB_MAX - self.DB_MIN) / steps
            out_db = self._static_gain(in_db) + self.makeup_db
            out_db = max(self.DB_MIN, min(self.DB_MAX, out_db))
            pts.append(QtCore.QPointF(ix(in_db), oy(out_db)))
        p.setPen(QtGui.QPen(QtGui.QColor(t["graph_curve"]), 2))
        p.setBrush(QtCore.Qt.NoBrush)
        p.drawPolyline(QtGui.QPolygonF(pts))


# ---------------------------------------------------------------------------
# 円形ロータリーノブ（QPainter自前描画・縦ドラッグ/ホイール・数値両表示）
# ---------------------------------------------------------------------------
class Knob(CachedWidget):
    valueChanged = QtCore.pyqtSignal(float)
    _DRAG_PX = 200.0   # フルレンジに必要なドラッグ量(px)
    _A_START = 225.0   # 開始角(度, 左下)
    _A_SWEEP = 270.0   # 時計回りスイープ量(度)

    def __init__(self, label, lo, hi, val, suffix, decimals=1, step=1.0):
        super().__init__()
        self.label = label
        self.lo, self.hi = float(lo), float(hi)
        self.suffix = suffix
        self.decimals = decimals
        self.step = step
        self._val = float(val)
        self.setMinimumSize(96, 116)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                           QtWidgets.QSizePolicy.Expanding)
        self.setCursor(QtCore.Qt.SizeVerCursor)
        self.setToolTip("↕ ドラッグ / ホイールで調整")
        self._drag_y = None
        self._drag_val = None

    def value(self):
        return self._val

    def setValue(self, v):
        v = max(self.lo, min(self.hi, v))
        v = round(v / self.step) * self.step
        if abs(v - self._val) < 1e-9:
            return
        self._val = v
        self.update()
        self.valueChanged.emit(v)

    def _frac(self):
        return (self._val - self.lo) / (self.hi - self.lo)

    def _geom(self):
        w, h = self.width(), self.height()
        lbl_h = max(14, int(h * 0.15))
        val_h = max(16, int(h * 0.18))
        avail = h - lbl_h - val_h
        r = min(w * 0.42, avail * 0.46)
        cx = w / 2.0
        cy = lbl_h + avail / 2.0
        return w, h, lbl_h, val_h, cx, cy, r

    def _paint_static(self, p, t):
        w, h, lbl_h, val_h, cx, cy, r = self._geom()
        # ラベル（上）— widget 幅に収める。ライトでも視認できる濃さ(knob_label)
        p.setPen(QtGui.QColor(t["knob_label"]))
        draw_text_fit(p, QtCore.QRect(2, 0, w - 4, lbl_h),
                      QtCore.Qt.AlignCenter, self.label,
                      max_pt=max(8, min(13, int(r * 0.34))), min_pt=7)
        # トラック弧（背景リング）
        rect = QtCore.QRectF(cx - r, cy - r, 2 * r, 2 * r)
        pen_w = max(3.0, r * 0.16)
        p.setPen(QtGui.QPen(QtGui.QColor(t["knob_ring"]), pen_w,
                            QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
        p.drawArc(rect, int(self._A_START * 16), int(-self._A_SWEEP * 16))
        # ノブ面
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor(t["knob_face"]))
        rf = r * 0.66
        p.drawEllipse(QtCore.QRectF(cx - rf, cy - rf, 2 * rf, 2 * rf))

    def _paint_dynamic(self, p, t):
        w, h, lbl_h, val_h, cx, cy, r = self._geom()
        frac = self._frac()
        rect = QtCore.QRectF(cx - r, cy - r, 2 * r, 2 * r)
        pen_w = max(3.0, r * 0.16)
        # 値弧（アクセント）
        p.setPen(QtGui.QPen(QtGui.QColor(t["accent"]), pen_w,
                            QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
        p.drawArc(rect, int(self._A_START * 16), int(-self._A_SWEEP * frac * 16))
        # 針
        ang = math.radians(self._A_START - self._A_SWEEP * frac)
        rf = r * 0.66
        x1 = cx + rf * 0.30 * math.cos(ang)
        y1 = cy - rf * 0.30 * math.sin(ang)
        x2 = cx + rf * math.cos(ang)
        y2 = cy - rf * math.sin(ang)
        p.setPen(QtGui.QPen(QtGui.QColor(t["accent"]), max(2.0, r * 0.10),
                            QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
        p.drawLine(QtCore.QPointF(x1, y1), QtCore.QPointF(x2, y2))
        # 数値（下・大きく）— widget 幅に収める
        p.setPen(QtGui.QColor(t["knob_text"]))
        txt = f"{self._val:.{self.decimals}f}{self.suffix}"
        draw_text_fit(p, QtCore.QRect(2, h - val_h, w - 4, val_h),
                      QtCore.Qt.AlignCenter, txt,
                      max_pt=max(10, min(18, int(r * 0.42))), min_pt=8)

    # --- 操作 -----------------------------------------------------------
    def wheelEvent(self, e):
        self.setValue(self._val + (e.angleDelta().y() / 120.0) * self.step)
        e.accept()

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            self._drag_y = e.y()
            self._drag_val = self._val
            e.accept()
        else:
            super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag_y is not None:
            dy = self._drag_y - e.y()
            span = self.hi - self.lo
            self.setValue(self._drag_val + (dy / self._DRAG_PX) * span)
            e.accept()
        else:
            super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._drag_y = None
        super().mouseReleaseEvent(e)


# ---------------------------------------------------------------------------
# EQ 1バンド（縦スライダー + dB値 + 周波数ラベル）
#   ハンドルはウィンドウ幅に応じて横長にスケール（resizeEventで再計算）。
# ---------------------------------------------------------------------------
# 主要周波数（文字を大きく/アクセント色で強調）
EQ_MAJOR = {100, 1000, 10000}


class EQBand(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal(int, float)

    @staticmethod
    def _qss(t, handle_h, handle_m, active):
        track = t["eq_track"]
        fill = t["accent"]
        if active:
            hbg, hbd = t["accent2"], t["accent2_dk"]
        else:
            hbg, hbd = t["eq_handle"], t["eq_handle_bd"]
        return f"""
        QSlider::groove:vertical {{ width: 8px; background: {track}; border-radius: 4px; }}
        QSlider::handle:vertical {{
            height: {handle_h}px; margin: 0 -{handle_m}px;
            background: {hbg}; border: 1px solid {hbd}; border-radius: 6px;
        }}
        QSlider::sub-page:vertical {{ background: {fill}; border-radius: 4px; }}
        QSlider::add-page:vertical {{ background: {track}; border-radius: 4px; }}
        """

    def __init__(self, index, center_hz, parent=None):
        super().__init__(parent)
        self.index = index
        self.center_hz = center_hz
        self.is_major = center_hz in EQ_MAJOR
        self._t = THEMES["dark"]
        self._last_active = None
        self._handle_h = 20
        self._handle_m = 20
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 1, 0, 1)
        lay.setSpacing(2)

        self.val_lbl = QtWidgets.QLabel("0.0")
        self.val_lbl.setAlignment(QtCore.Qt.AlignCenter)
        vf = self.val_lbl.font(); vf.setPointSize(10); vf.setBold(True)
        self.val_lbl.setFont(vf)

        self.slider = QtWidgets.QSlider(QtCore.Qt.Vertical)
        self.slider.setRange(-120, 120)
        self.slider.setValue(0)
        self.slider.setMinimumHeight(90)
        self.slider.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                  QtWidgets.QSizePolicy.Expanding)
        self.slider.valueChanged.connect(self._on)

        self.freq_lbl = QtWidgets.QLabel(self._fmt(center_hz))
        self.freq_lbl.setAlignment(QtCore.Qt.AlignCenter)
        # 主要周波数は大きく、他は一回り小さく
        ff = self.freq_lbl.font()
        ff.setPointSize(11 if self.is_major else 8)
        ff.setBold(True)
        self.freq_lbl.setFont(ff)

        vw = self.val_lbl.fontMetrics().horizontalAdvance("-12.0") + 8
        fw = self.freq_lbl.fontMetrics().horizontalAdvance("12.5k") + 6
        col_w = max(vw, fw)
        self.val_lbl.setFixedWidth(col_w)
        self.freq_lbl.setFixedWidth(col_w)
        # ラベル高さを全バンド共通に固定（主要周波数の大フォントでも領域が変わらず、
        # 0dB時のスライダー中心位置が全バンドで揃う）
        major_fm = QtGui.QFontMetrics(QtGui.QFont("", 11, QtGui.QFont.Bold))
        lbl_h = major_fm.height() + 2
        self.val_lbl.setFixedHeight(lbl_h)
        self.freq_lbl.setFixedHeight(lbl_h)
        lay.addWidget(self.val_lbl, 0, QtCore.Qt.AlignHCenter)
        lay.addWidget(self.slider, 1)
        lay.addWidget(self.freq_lbl, 0, QtCore.Qt.AlignHCenter)
        self._apply_label_colors()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        band_w = self.width()
        if band_w < 10:
            return
        new_h = max(14, min(28, band_w // 4))
        new_m = max(16, int(band_w * 0.40))
        if new_h != self._handle_h or new_m != self._handle_m:
            self._handle_h = new_h
            self._handle_m = new_m
            self._last_active = None
            self._on(self.slider.value())

    def _fmt(self, hz):
        if hz >= 1000:
            return f"{hz/1000:g}k"
        return f"{hz:g}"

    def _apply_label_colors(self):
        t = self._t
        active = self.slider.value() != 0
        if active:
            # 変更箇所: オレンジ＋太字でハッキリ（どこを動かしたか一目で判別）
            self.val_lbl.setStyleSheet(f"color: {t['accent2']}; font-weight: bold;")
        else:
            # 0.0: 暗いグレー＋標準太さで背景に馴染ませ目立たせない
            self.val_lbl.setStyleSheet("color: #666666; font-weight: normal;")
        # 周波数: 主要はアクセント、他は淡色
        fc = t["accent"] if self.is_major else t["text_dim"]
        self.freq_lbl.setStyleSheet(f"color: {fc}; font-weight: bold;")

    def _on(self, v):
        db = v / 10.0
        active = (v != 0)
        self.val_lbl.setText(f"{db:+.1f}")
        state = (active, id(self._t))
        if state != self._last_active:
            self.slider.setStyleSheet(
                self._qss(self._t, self._handle_h, self._handle_m, active))
            self._apply_label_colors()
            self._last_active = state
        self.changed.emit(self.index, db)

    def set_theme(self, t):
        self._t = t
        self._last_active = None
        self._on(self.slider.value())

    def set_max(self, max_db):
        self.slider.setRange(int(-max_db * 10), int(max_db * 10))

    def reset(self):
        self.slider.setValue(0)


class EQRow(QtWidgets.QWidget):
    def __init__(self, centers, on_change, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(1)
        self.bands = []
        for i, c in enumerate(centers):
            b = EQBand(i, c, parent=self)
            b.changed.connect(on_change)
            self.bands.append(b)
            lay.addWidget(b, 1)


# ---------------------------------------------------------------------------
# メインウィンドウ
# ---------------------------------------------------------------------------
class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"UFX-MG  v{__version__}  —  EQ / Comp / Meter")
        self.engine = Engine()
        self._settings = QtCore.QSettings("Kanunsanun", "UFX-MG")
        # 背景画像の状態
        self._bg_pixmap = None
        self._bg_scaled = None
        self._bg_scrim = 96       # 背景の上に重ねる暗幕（0-255）。UIの可読性を確保
        # 記憶したテーマを復元
        saved = self._settings.value("theme", "dark")
        self._theme_name = saved if saved in THEMES else "dark"
        self._themed = []        # set_theme を持つカスタムウィジェット
        self._knobs = []
        self._build_ui()
        # 記憶した背景画像を復元（あれば）
        bgp = self._settings.value("bg_image", "")
        if bgp and os.path.exists(bgp):
            self._set_bg_image(bgp, save=False)
        self.apply_theme(self._theme_name)
        # テーマ選択を記憶値に合わせる
        idx = self.theme_combo.findData(self._theme_name)
        if idx >= 0:
            self.theme_combo.blockSignals(True)
            self.theme_combo.setCurrentIndex(idx)
            self.theme_combo.blockSignals(False)
        # プリセット読込＋前回状態の自動復元
        self._presets = {}
        self._last_state = None
        self._load_presets_file()
        self._save_timer = QtCore.QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._write_presets_file)
        if self._settings.value("auto_restore", True, type=bool) and self._last_state:
            self._apply_dsp(self._last_state)
        # デバイス列挙(重い・特にASIO)はウィンドウ表示後に遅延実行 → 起動を体感高速化
        QtCore.QTimer.singleShot(0, self._populate_audio_devices)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._refresh_meters)
        self.timer.start(33)

    def apply_theme(self, name):
        self._theme_name = name
        self._settings.setValue("theme", name)
        t = THEMES[name]
        has_bg = self._bg_pixmap is not None and not self._bg_pixmap.isNull()
        self.setStyleSheet(window_qss(t, has_bg))
        for wdg in self._themed:
            wdg.set_theme(t)
        self._update_big_button()   # 巨大ボタンはテーマ非依存色で再適用
        self.update()               # 地（背景）を描き直す

    # -- 背景画像 -----------------------------------------------------------
    def _rescale_bg(self):
        if self._bg_pixmap is not None and not self._bg_pixmap.isNull() and self.width() > 0:
            self._bg_scaled = self._bg_pixmap.scaled(
                self.size(), QtCore.Qt.KeepAspectRatioByExpanding,
                QtCore.Qt.SmoothTransformation)
        else:
            self._bg_scaled = None

    def _choose_bg_image(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "背景画像を選択", "",
            "画像ファイル (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path:
            self._set_bg_image(path)

    def _set_bg_image(self, path, save=True):
        pm = QtGui.QPixmap(path)
        if pm.isNull():
            if save:
                QtWidgets.QMessageBox.warning(self, "背景画像", "画像を読み込めませんでした。")
            return
        self._bg_pixmap = pm
        self._rescale_bg()
        if save:
            self._settings.setValue("bg_image", path)
        self.apply_theme(self._theme_name)   # 半透明パネルへ切替＋再描画

    def _clear_bg_image(self):
        self._bg_pixmap = None
        self._bg_scaled = None
        self._settings.setValue("bg_image", "")
        self.apply_theme(self._theme_name)

    def paintEvent(self, _ev):
        p = QtGui.QPainter(self)
        if self._bg_scaled is not None:
            x = (self.width() - self._bg_scaled.width()) // 2
            y = (self.height() - self._bg_scaled.height()) // 2
            p.drawPixmap(x, y, self._bg_scaled)
            p.fillRect(self.rect(), QtGui.QColor(0, 0, 0, self._bg_scrim))  # 暗幕
        else:
            p.fillRect(self.rect(), QtGui.QColor(THEMES[self._theme_name]["win_bg"]))

    # -- プリセット / DSP状態の保存・復元 -----------------------------------
    def _preset_path(self):
        base = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "UFX-MG")
        return os.path.join(base, "presets.json")

    def _capture_dsp(self):
        """現在の DSP 状態をまとめて dict に。"""
        return {
            "eq": [b.slider.value() / 10.0 for b in self.eq_bands],
            "eq_range": self.range_combo.currentData(),
            "comp": {
                "thr": self.c_thr.value(), "ratio": self.c_ratio.value(),
                "atk": self.c_atk.value(), "rel": self.c_rel.value(),
                "knee": self.c_knee.value(), "outgain": self.c_makeup.value(),
            },
            "eq_on": self.eq_toggle.isChecked(),
            "comp_on": self.comp_toggle.isChecked(),
        }

    def _apply_dsp(self, st):
        """dict から DSP 状態を復元（互換: 構造が合う項目のみ適用）。"""
        if not isinstance(st, dict):
            return
        eq = st.get("eq")
        if isinstance(eq, list) and len(eq) == len(self.eq_bands):
            for b, g in zip(self.eq_bands, eq):
                b.slider.setValue(int(round(float(g) * 10)))
        rng = st.get("eq_range")
        if rng is not None:
            i = self.range_combo.findData(rng)
            if i >= 0:
                self.range_combo.setCurrentIndex(i)
        c = st.get("comp", {})
        for key, knob in (("thr", self.c_thr), ("ratio", self.c_ratio),
                          ("atk", self.c_atk), ("rel", self.c_rel),
                          ("knee", self.c_knee), ("outgain", self.c_makeup)):
            if key in c:
                knob.setValue(float(c[key]))
        if "eq_on" in st:
            self.eq_toggle.setChecked(bool(st["eq_on"]))
        if "comp_on" in st:
            self.comp_toggle.setChecked(bool(st["comp_on"]))

    def _load_presets_file(self):
        try:
            with open(self._preset_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
            self._presets = data.get("presets", {}) or {}
            self._last_state = data.get("last")
        except (FileNotFoundError, ValueError, OSError):
            self._presets = {}
            self._last_state = None

    def _write_presets_file(self):
        """名前付きプリセット＋現在状態(last)をファイルへ。本体と分離した %APPDATA% に保存。"""
        data = {"schema": PRESET_SCHEMA, "presets": self._presets,
                "last": self._capture_dsp()}
        try:
            os.makedirs(os.path.dirname(self._preset_path()), exist_ok=True)
            with open(self._preset_path(), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
        except OSError:
            pass

    def _schedule_save(self):
        """DSP変更後、少し待ってから保存（ドラッグ連打で書きすぎない）。"""
        if hasattr(self, "_save_timer"):
            self._save_timer.start(800)

    def _reload_preset_combo(self):
        if not hasattr(self, "preset_combo"):
            return
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItem("（プリセットを選択）", "")
        for name in sorted(self._presets.keys()):
            self.preset_combo.addItem(name, name)
        self.preset_combo.blockSignals(False)

    def _on_preset_selected(self, idx):
        name = self.preset_combo.itemData(idx)
        if name and name in self._presets:
            self._apply_dsp(self._presets[name])

    def _save_preset_as(self):
        name, ok = QtWidgets.QInputDialog.getText(
            self._dev_dialog or self, "プリセット保存", "プリセット名:")
        name = (name or "").strip()
        if not ok or not name:
            return
        if name in self._presets:
            r = QtWidgets.QMessageBox.question(
                self._dev_dialog or self, "上書き確認",
                f"「{name}」を上書きしますか？")
            if r != QtWidgets.QMessageBox.Yes:
                return
        self._presets[name] = self._capture_dsp()
        self._write_presets_file()
        self._reload_preset_combo()
        i = self.preset_combo.findData(name)
        if i >= 0:
            self.preset_combo.setCurrentIndex(i)

    def _delete_preset(self):
        name = self.preset_combo.currentData()
        if not name or name not in self._presets:
            return
        r = QtWidgets.QMessageBox.question(
            self._dev_dialog or self, "削除確認", f"「{name}」を削除しますか？")
        if r == QtWidgets.QMessageBox.Yes:
            del self._presets[name]
            self._write_presets_file()
            self._reload_preset_combo()

    # -- UI 構築 ------------------------------------------------------------
    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 10, 6, 4)   # 上は IN/OUT タイトル分の余白
        root.setSpacing(5)

        # メイン: [IN] [中央 EQ/Comp] [OUT]
        main = QtWidgets.QHBoxLayout()
        main.setSpacing(5)
        main.addWidget(self._meter_panel("IN", "in", mirror=False))

        center = QtWidgets.QVBoxLayout()
        center.setSpacing(5)
        center.addWidget(self._eq_panel(), 3)    # EQ を大きく
        center.addWidget(self._comp_panel(), 2)
        main.addLayout(center, 1)

        main.addWidget(self._meter_panel("OUT", "out", mirror=True))
        root.addLayout(main, 1)

        # 下部: デバイス設定バー（折りたたみ）+ ステータス
        root.addWidget(self._device_bar())

    def _meter_panel(self, title, which, mirror=False):
        box = QtWidgets.QGroupBox(title)
        lay = QtWidgets.QVBoxLayout(box)
        lay.setContentsMargins(4, 6, 4, 4)   # 上はタイトル分の余白
        m = Meter(title, mirror=mirror)
        lay.addWidget(m)
        setattr(self, f"meter_{which}", m)
        self._themed.append(m)
        # 固定幅にして「目盛り＋L/Rバー」が常に収まる領域を保証（中央へ侵入しない）
        box.setFixedWidth(168)
        return box

    # Flat ボタン: 誤操作防止のアウトライン警告スタイル（赤枠・ホバーで薄赤）
    FLAT_QSS = (
        "QPushButton { background: transparent; color: #E0573A; "
        "border: 1px solid #C0392B; border-radius: 4px; padding: 4px 16px; "
        "font-weight: bold; } "
        "QPushButton:hover { background: rgba(211,47,47,0.18); } "
        "QPushButton:pressed { background: rgba(211,47,47,0.30); }")

    def _eq_panel(self):
        box = QtWidgets.QGroupBox("グラフィックEQ")
        self.eq_box = box
        outer = QtWidgets.QVBoxLayout(box)

        topbar = QtWidgets.QHBoxLayout()
        # ON/OFF（BYPASS）インジケータースイッチ
        self.eq_toggle = ToggleSwitch("EQ ON", "EQ BYPASS")
        self.eq_toggle.toggled.connect(self._on_eq_enable)
        self._themed.append(self.eq_toggle)
        topbar.addWidget(self.eq_toggle)
        topbar.addSpacing(14)
        topbar.addWidget(QtWidgets.QLabel("レンジ:"))
        self.range_combo = QtWidgets.QComboBox()
        self.range_combo.addItem("±12 dB", 12.0)
        self.range_combo.addItem("±6 dB", 6.0)
        self.range_combo.currentIndexChanged.connect(self._on_eq_range)
        topbar.addWidget(self.range_combo)
        topbar.addStretch(1)
        flat = QtWidgets.QPushButton("Flat")
        flat.setStyleSheet(self.FLAT_QSS)
        flat.setCursor(QtCore.Qt.PointingHandCursor)
        flat.clicked.connect(self._eq_flat)
        topbar.addWidget(flat)
        outer.addLayout(topbar)

        from .dsp import GraphicEQ
        tmp = GraphicEQ(int(self.sr_default()))
        self.eq_row = EQRow(tmp.centers, self._on_eq)
        self.eq_bands = self.eq_row.bands
        self._themed.extend(self.eq_bands)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.eq_row)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        outer.addWidget(scroll, 1)
        return box

    def sr_default(self):
        return 96000

    def _on_eq_range(self):
        max_db = self.range_combo.currentData()
        for b in self.eq_bands:
            b.set_max(max_db)
        self._schedule_save()

    def _comp_panel(self):
        box = QtWidgets.QGroupBox("コンプレッサー")
        self.comp_box = box

        v = QtWidgets.QVBoxLayout(box)
        v.setSpacing(6)
        # ヘッダー: ON/OFF（BYPASS）スイッチ
        header = QtWidgets.QHBoxLayout()
        self.comp_toggle = ToggleSwitch("COMP ON", "COMP BYPASS")
        self.comp_toggle.toggled.connect(self._on_comp_enable)
        self._themed.append(self.comp_toggle)
        header.addWidget(self.comp_toggle)
        header.addStretch(1)
        v.addLayout(header)

        outer = QtWidgets.QHBoxLayout()
        outer.setSpacing(14)

        # 左: グラフ + 直下に GRバー
        left = QtWidgets.QVBoxLayout()
        left.setSpacing(4)
        self.comp_graph = CompGraph()
        self.comp_graph.setMaximumWidth(420)
        self._themed.append(self.comp_graph)
        left.addWidget(self.comp_graph, 1)
        self.gr_bar = GRBar()
        self._themed.append(self.gr_bar)
        left.addWidget(self.gr_bar)
        outer.addLayout(left, 1)

        # 右: ノブ 2行×3列
        g = QtWidgets.QGridLayout()
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(8)

        def mk(label, lo, hi, val, suffix, row, col, decimals=1, step=1.0):
            k = Knob(label, lo, hi, val, suffix, decimals=decimals, step=step)
            self._knobs.append(k)
            self._themed.append(k)
            g.addWidget(k, row, col)
            return k

        self.c_thr    = mk("Threshold", -60,    0, -18, " dB", 0, 0, step=1.0)
        self.c_ratio  = mk("Ratio",       1,   20,   4, ":1",  0, 1, step=0.5)
        self.c_atk    = mk("Attack",    0.1,  200,  10, " ms", 0, 2, step=1.0)
        self.c_rel    = mk("Release",     5, 1000, 120, " ms", 1, 0, step=5.0)
        self.c_knee   = mk("Knee",        0,   24,   6, " dB", 1, 1, step=0.5)
        self.c_makeup = mk("OutGain",     0,   24,   0, " dB", 1, 2, step=0.5)

        for k in self._knobs:
            k.valueChanged.connect(self._on_comp)

        outer.addLayout(g, 2)
        v.addLayout(outer, 1)
        return box

    # 巨大トグルボタンのテキスト（配色はテーマ連動: run_bg/stop_bg 等）
    BIG_STOPPED_TXT = "▶  AUDIO START  (開始)"
    BIG_RUNNING_TXT = "■  AUDIO STOP  (停止)"

    def _device_bar(self):
        # デバイス選択コンボはダイアログ用に先に生成（状態を保持）
        self._build_dev_combos()

        bar = QtWidgets.QFrame()
        bar.setFrameShape(QtWidgets.QFrame.NoFrame)
        row = QtWidgets.QHBoxLayout(bar)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(12)

        # 設定変更ボタン（ギア）— 押した時だけダイアログ表示
        gear = QtWidgets.QPushButton("⚙ 設定")
        gear.setMinimumHeight(64)
        gf = gear.font(); gf.setPointSize(11); gear.setFont(gf)
        gear.clicked.connect(self._open_dev_settings)
        row.addWidget(gear)

        # テーマ切替
        tcol = QtWidgets.QVBoxLayout(); tcol.setSpacing(1)
        tcol.addWidget(QtWidgets.QLabel("テーマ"))
        self.theme_combo = QtWidgets.QComboBox()
        self.theme_combo.addItem("ダーク", "dark")
        self.theme_combo.addItem("ライト", "light")
        self.theme_combo.currentIndexChanged.connect(
            lambda: self.apply_theme(self.theme_combo.currentData()))
        tcol.addWidget(self.theme_combo)
        row.addLayout(tcol)

        # デバイス情報の常時表示（生存確認用の大きな読み取り専用テキスト）
        self.dev_info = QtWidgets.QLabel()
        self.dev_info.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        dif = self.dev_info.font(); dif.setPointSize(11); self.dev_info.setFont(dif)
        self.dev_info.setWordWrap(False)
        # 縮小を許可（最小幅小）→ 溢れたら elide。巨大ボタンは Fixed で保護される。
        self.dev_info.setMinimumWidth(120)
        self.dev_info.setSizePolicy(QtWidgets.QSizePolicy.Ignored,
                                    QtWidgets.QSizePolicy.Preferred)
        row.addWidget(self.dev_info, 1)

        # 巨大 START/STOP トグル
        self.start_btn = QtWidgets.QPushButton()
        self.start_btn.setMinimumSize(300, 64)
        self.start_btn.setSizePolicy(QtWidgets.QSizePolicy.Fixed,
                                     QtWidgets.QSizePolicy.Fixed)
        bf = self.start_btn.font(); bf.setPointSize(15); bf.setBold(True)
        self.start_btn.setFont(bf)
        self.start_btn.clicked.connect(self._toggle)
        row.addWidget(self.start_btn)

        # 各コンボ変更時にデバイス情報表示を更新
        for c in (self.in_combo, self.out_combo, self.sr_combo, self.block_combo):
            c.currentIndexChanged.connect(self._update_dev_info)
        self._update_dev_info()
        self._update_big_button()
        return bar

    def _build_dev_combos(self):
        # 軽量な静的コンボのみ即時生成。デバイス列挙(重い)は起動後に遅延実行。
        self.in_combo = QtWidgets.QComboBox()
        self.out_combo = QtWidgets.QComboBox()

        self.sr_combo = QtWidgets.QComboBox()
        for sr in (44100, 48000, 88200, 96000):
            self.sr_combo.addItem(str(sr), sr)
        self.sr_combo.setCurrentText("96000")

        self.block_combo = QtWidgets.QComboBox()
        self.block_combo.addItem("0 (ASIO/ドライバー既定)", 0)
        for b in (128, 256, 512, 1024):
            self.block_combo.addItem(str(b), b)
        self.block_combo.setCurrentText("512")

        self._dev_dialog = None
        self._devices_loaded = False

    def _populate_audio_devices(self):
        """重いデバイス列挙（特にASIO）を起動後に実行。ウィンドウは先に表示される。"""
        if self._devices_loaded:
            return
        try:
            devs = list_devices()
        except Exception as ex:
            self.dev_info.setText(f"デバイス列挙エラー: {ex}")
            return

        def is_asio(d):
            return "asio" in d["hostapi"].lower()

        devs_sorted = sorted(devs, key=lambda d: (0 if is_asio(d) else 1))
        # 列挙中の signal 連発を抑制
        self.in_combo.blockSignals(True)
        self.out_combo.blockSignals(True)
        in_sep = out_sep = False
        for d in devs_sorted:
            tag = f"[{d['index']}] {d['name']} ({d['hostapi']})"
            if d["max_in"] > 0:
                if not is_asio(d) and not in_sep and self.in_combo.count() > 0:
                    self.in_combo.insertSeparator(self.in_combo.count())
                    in_sep = True
                self.in_combo.addItem(tag + f"  in:{d['max_in']}", d["index"])
            if d["max_out"] > 0:
                if not is_asio(d) and not out_sep and self.out_combo.count() > 0:
                    self.out_combo.insertSeparator(self.out_combo.count())
                    out_sep = True
                self.out_combo.addItem(tag + f"  out:{d['max_out']}", d["index"])
        self.in_combo.blockSignals(False)
        self.out_combo.blockSignals(False)
        self._devices_loaded = True
        self._update_dev_info()

    def _open_dev_settings(self):
        if not self._devices_loaded:
            self._populate_audio_devices()   # 未読込なら即時読込
        if self._dev_dialog is None:
            dlg = QtWidgets.QDialog(self)
            dlg.setWindowTitle("設定")
            dlg.setMinimumWidth(600)
            g = QtWidgets.QGridLayout(dlg)
            r = 0
            # ── プリセット（DSP設定の保存・呼び出し）──
            g.addWidget(QtWidgets.QLabel("<b>プリセット</b>（EQ＋コンプ）"), r, 0, 1, 4); r += 1
            self.preset_combo = QtWidgets.QComboBox()
            self._reload_preset_combo()
            self.preset_combo.activated.connect(self._on_preset_selected)
            g.addWidget(self.preset_combo, r, 0, 1, 2)
            save_p = QtWidgets.QPushButton("名前を付けて保存…")
            save_p.clicked.connect(self._save_preset_as)
            del_p = QtWidgets.QPushButton("削除")
            del_p.clicked.connect(self._delete_preset)
            g.addWidget(save_p, r, 2); g.addWidget(del_p, r, 3); r += 1
            self.auto_restore_chk = QtWidgets.QCheckBox("前回の設定を起動時に復元する")
            self.auto_restore_chk.setChecked(
                self._settings.value("auto_restore", True, type=bool))
            self.auto_restore_chk.toggled.connect(
                lambda on: self._settings.setValue("auto_restore", on))
            g.addWidget(self.auto_restore_chk, r, 0, 1, 4); r += 1
            line0 = QtWidgets.QFrame(); line0.setFrameShape(QtWidgets.QFrame.HLine)
            g.addWidget(line0, r, 0, 1, 4); r += 1
            # ── デバイス / ルーティング ──
            hint = QtWidgets.QLabel(
                "💡 <b>低遅延で使うには ASIO ドライバー推奨</b><br>"
                "「Yamaha Steinberg USB ASIO」など <b>(ASIO)</b> 表記の機器を、"
                "<b>入力・出力とも同じもの</b>に選んでください。<br>"
                "MME / Windows WDM-KS は遅延が大きくなります。")
            hint.setWordWrap(True)
            hint.setTextFormat(QtCore.Qt.RichText)
            hint.setStyleSheet(
                "background: rgba(0,173,181,0.12); border:1px solid #00ADB5; "
                "border-radius:6px; padding:8px;")
            g.addWidget(hint, r, 0, 1, 4); r += 1
            self._dev_running_hint = QtWidgets.QLabel(
                "⚠ 動作中はデバイス変更できません（停止後に変更可）。プリセット・背景は変更可。")
            self._dev_running_hint.setStyleSheet("color:#E0573A;")
            g.addWidget(self._dev_running_hint, r, 0, 1, 4); r += 1
            g.addWidget(QtWidgets.QLabel("入力機器"), r, 0); g.addWidget(self.in_combo, r, 1, 1, 3); r += 1
            g.addWidget(QtWidgets.QLabel("出力機器"), r, 0); g.addWidget(self.out_combo, r, 1, 1, 3); r += 1
            g.addWidget(QtWidgets.QLabel("SR"), r, 0); g.addWidget(self.sr_combo, r, 1)
            g.addWidget(QtWidgets.QLabel("Block"), r, 2); g.addWidget(self.block_combo, r, 3); r += 1
            self._dev_widgets = [self.in_combo, self.out_combo, self.sr_combo, self.block_combo]
            line = QtWidgets.QFrame(); line.setFrameShape(QtWidgets.QFrame.HLine)
            g.addWidget(line, r, 0, 1, 4); r += 1
            # ── 背景画像 ──
            g.addWidget(QtWidgets.QLabel("背景画像"), r, 0)
            bg_choose = QtWidgets.QPushButton("画像を選択…")
            bg_choose.clicked.connect(self._choose_bg_image)
            bg_clear = QtWidgets.QPushButton("標準に戻す")
            bg_clear.clicked.connect(self._clear_bg_image)
            g.addWidget(bg_choose, r, 1, 1, 2); g.addWidget(bg_clear, r, 3); r += 1
            close = QtWidgets.QPushButton("閉じる")
            close.clicked.connect(dlg.accept)
            g.addWidget(close, r, 0, 1, 4)
            self._dev_dialog = dlg
        # 動作中はデバイス変更だけ不可（プリセット・背景は可）
        running = self.engine.running
        for wdg in self._dev_widgets:
            wdg.setEnabled(not running)
        self._dev_running_hint.setVisible(running)
        self._reload_preset_combo()
        self._dev_dialog.show()
        self._dev_dialog.raise_()

    def _short_dev(self, combo):
        """デバイス名を短く（"[i] 名前 (hostapi)" の名前部分のみ）。"""
        txt = combo.currentText()
        # "[0] Name (HostAPI)  in:2" → "Name (HostAPI)"
        if "] " in txt:
            txt = txt.split("] ", 1)[1]
        txt = txt.split("  in:")[0].split("  out:")[0]
        return txt.strip()

    def _update_dev_info(self):
        sr = self.sr_combo.currentData()
        blk = self.block_combo.currentData()
        blk_txt = "ドライバ既定" if blk == 0 else str(blk)
        if not getattr(self, "_devices_loaded", False):
            self.dev_info.setToolTip("")
            self._dev_info_full = f"デバイス読込中…    SR {sr}    Block {blk_txt}"
            self.dev_info.setText(self._dev_info_full)
            return
        info = (f"IN: {self._short_dev(self.in_combo)}    "
                f"OUT: {self._short_dev(self.out_combo)}    "
                f"SR {sr}    Block {blk_txt}")
        # ASIO 以外（MME/WDM等）が選ばれていたら高遅延の警告を先頭に（省略で隠れない）
        both = (self.in_combo.currentText() + self.out_combo.currentText()).upper()
        if both and "ASIO" not in both:
            info = "⚠ 高遅延：ASIO推奨    " + info
        if self.engine.running and self.engine.xrun:
            info += f"    ⚠ xrun={self.engine.xrun}"
        self._dev_info_full = info
        self.dev_info.setToolTip(info)
        self._apply_dev_elide()

    def _apply_dev_elide(self):
        """ラベル幅に収まらない場合は文末を三点リーダーに（巨大ボタンを押し出さない）。"""
        if not hasattr(self, "_dev_info_full"):
            return
        fm = self.dev_info.fontMetrics()
        avail = max(40, self.dev_info.width() - 4)
        self.dev_info.setText(
            fm.elidedText(self._dev_info_full, QtCore.Qt.ElideRight, avail))

    def _update_big_button(self):
        t = THEMES[self._theme_name]
        if self.engine.running:
            bg, fg, txt = t["run_bg"], t["run_fg"], self.BIG_RUNNING_TXT
        else:
            bg, fg, txt = t["stop_bg"], t["stop_fg"], self.BIG_STOPPED_TXT
        self.start_btn.setText(txt)
        self.start_btn.setStyleSheet(
            f"QPushButton {{ background: {bg}; color: {fg}; border: none; "
            f"border-radius: 6px; padding: 6px 18px; font-weight: bold; }} "
            f"QPushButton:hover {{ background: {bg}; }}")

    # -- コールバック -------------------------------------------------------
    def _on_eq(self, i, db):
        if self.engine.eq:
            self.engine.eq.set_gain(i, db)
        self._schedule_save()

    def _eq_flat(self):
        for b in self.eq_bands:
            b.reset()

    def _on_eq_enable(self, on):
        if self.engine.eq:
            self.engine.eq.enabled = on
        self._schedule_save()

    def _on_comp_enable(self, on):
        if self.engine.comp:
            self.engine.comp.enabled = on
        self._schedule_save()

    def _on_comp(self):
        thr = self.c_thr.value()
        ratio = self.c_ratio.value()
        knee = self.c_knee.value()
        makeup = self.c_makeup.value()
        c = self.engine.comp
        if c:
            c.threshold_db = thr
            c.ratio = ratio
            c.attack_ms = self.c_atk.value()
            c.release_ms = self.c_rel.value()
            c.knee_db = knee
            c.makeup_db = makeup
        self.comp_graph.set_params(thr, ratio, knee, makeup)
        self._schedule_save()

    def _toggle(self):
        if self.engine.running:
            self.engine.stop()
            self._update_big_button()
            self._update_dev_info()
            return
        if not self._devices_loaded:
            self._populate_audio_devices()   # 開始前にデバイスを確実に読込
        try:
            e = self.engine
            e.fs = int(self.sr_combo.currentData())
            e.blocksize = int(self.block_combo.currentData())
            e.in_device = self.in_combo.currentData()
            e.out_device = self.out_combo.currentData()
            e.start()
            for b in self.eq_bands:
                self._on_eq(b.index, b.slider.value() / 10.0)
            self._on_comp()
            self.engine.eq.enabled = self.eq_toggle.isChecked()
            self.engine.comp.enabled = self.comp_toggle.isChecked()
            self._update_big_button()
            self._update_dev_info()
        except Exception as ex:
            QtWidgets.QMessageBox.critical(self, "エラー", str(ex))

    def _refresh_meters(self):
        e = self.engine
        self.meter_in.set_values(*e.meter_in)
        self.meter_out.set_values(*e.meter_out)
        self.gr_bar.set_value(e.gr_db)
        if e.running and e.xrun:
            self._update_dev_info()   # xrun 警告を情報行に反映

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._rescale_bg()        # 背景画像をウィンドウサイズにカバー表示
        self._apply_dev_elide()   # 幅変化に応じてデバイス名を再省略

    def closeEvent(self, ev):
        self._write_presets_file()   # 終了時の状態を保存（次回 自動復元）
        self.engine.stop()
        super().closeEvent(ev)


def show_main(app):
    """MainWindow を生成し、ノートPCのフルスクリーン前提で最大化表示して返す。
    （resize→showMaximized だと Windows で最大化フラグだけ立って実サイズが小さい
    不具合が出るため、availableGeometry を明示してから最大化する。）"""
    w = MainWindow()
    scr = app.primaryScreen().availableGeometry()
    w.setGeometry(scr)
    w.showMaximized()
    return w


def main():
    app = QtWidgets.QApplication(sys.argv)
    w = show_main(app)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
