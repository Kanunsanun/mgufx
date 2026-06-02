"""mgfx パッケージ初期化。

sounddevice をインポートする前に SD_ENABLE_ASIO を立てることで、同梱の
ASIO 対応 PortAudio DLL を読み込ませる（共有ミキサーをバイパスし低遅延化）。
この設定は sounddevice の最初の import より前である必要があるため、ここで行う。
"""

import os

# バージョン（単一の真実源）。配布・アップデート判定はこの値を参照する。
__version__ = "1.0.0"
__license__ = "MIT"
__copyright__ = "Copyright (c) 2026 Kanunsanun"

os.environ.setdefault("SD_ENABLE_ASIO", "1")
