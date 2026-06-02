"""オーディオエンジン: sounddevice ストリームで DSP チェーンを実行する。

信号フロー:
  USB入力(ST OUT) → メーター(in) → GraphicEQ → Compressor → メーター(out) → USB出力
"""

import os

os.environ.setdefault("SD_ENABLE_ASIO", "1")  # sounddevice import 前にASIOを有効化

import numpy as np
import sounddevice as sd

from .dsp import GraphicEQ, Compressor, block_peak_dbfs


class Engine:
    def __init__(self):
        self.fs = 96000
        self.blocksize = 512
        self.in_device = None
        self.out_device = None

        self.eq = None
        self.comp = None
        self.stream = None
        self.running = False

        # メーター値（GUIがポーリング）: dBFS
        self.meter_in = (-120.0, -120.0)
        self.meter_out = (-120.0, -120.0)
        self.xrun = 0

        self._x = None  # 入力バッファ（初回コールバックで確保、以後再利用）

    @property
    def gr_db(self):
        return self.comp.gain_reduction_db if self.comp else 0.0

    def build_dsp(self):
        self.eq = GraphicEQ(self.fs)
        self.comp = Compressor(self.fs)

    def _callback(self, indata, outdata, frames, time, status):
        if status:
            self.xrun += 1

        # 入力バッファを初回または blocksize 変化時のみ確保
        if self._x is None or self._x.shape[0] != frames:
            self._x = np.empty((frames, 2), dtype=np.float64)
        x = self._x
        x[:, 0] = indata[:, 0]
        x[:, 1] = indata[:, 1]

        self.meter_in = block_peak_dbfs(x)

        y = self.eq.process(x)
        y = self.comp.process(y)

        self.meter_out = block_peak_dbfs(y)

        # out_total=2 で両ch を常に書き込むため fill は不要
        np.clip(y[:, 0], -1.0, 1.0, out=y[:, 0])
        np.clip(y[:, 1], -1.0, 1.0, out=y[:, 1])
        outdata[:, 0] = y[:, 0]
        outdata[:, 1] = y[:, 1]

    def start(self):
        if self.running:
            return
        self.build_dsp()
        self.xrun = 0
        self._x = None  # 次のコールバックで正しい frames サイズで確保
        self.stream = sd.Stream(
            samplerate=self.fs,
            blocksize=self.blocksize,
            device=(self.in_device, self.out_device),
            channels=(2, 2),
            dtype="float32",
            callback=self._callback,
        )
        self.stream.start()
        self.running = True

    def stop(self):
        if not self.running:
            return
        self.stream.stop()
        self.stream.close()
        self.stream = None
        self.running = False


# --- デバイス列挙ユーティリティ -------------------------------------------
def list_devices():
    devs = []
    for i, d in enumerate(sd.query_devices()):
        ha = sd.query_hostapis(d["hostapi"])["name"]
        devs.append({
            "index": i,
            "name": d["name"],
            "hostapi": ha,
            "max_in": d["max_input_channels"],
            "max_out": d["max_output_channels"],
            "default_sr": d["default_samplerate"],
        })
    return devs
