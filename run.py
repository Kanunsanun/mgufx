"""アプリ起動エントリポイント（PyInstaller のビルド対象 / 直接実行用）。

起動に数秒かかる場合に備え、重いインポート（numpy / scipy / アプリ本体）の前に
Qt のスプラッシュ（アイコン画像）を表示する。Qt 製なので透過や閉じ際の描画が
きれいで、表示タイミングも自前で制御できる。
"""

import os
import sys
import time

from PyQt5 import QtCore, QtGui, QtWidgets


def _resource(name):
    """同梱リソースのパス（フリーズ時は _MEIPASS、開発時は run.py と同階層）。"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def main():
    app = QtWidgets.QApplication(sys.argv)
    t0 = time.monotonic()

    splash = None
    pm = QtGui.QPixmap(_resource("splash.png"))
    if not pm.isNull():
        splash = QtWidgets.QSplashScreen(pm, QtCore.Qt.WindowStaysOnTopHint)
        splash.show()
        app.processEvents()

    # 重いインポート（numpy/scipy/アプリ本体）はスプラッシュ表示後に行う
    from mgfx.app import show_main
    w = show_main(app)

    if splash is not None:
        # 速い起動でもアイコンが視認できるよう最低 0.6 秒は表示
        rest = 0.6 - (time.monotonic() - t0)
        if rest > 0:
            time.sleep(rest)
        splash.finish(w)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
