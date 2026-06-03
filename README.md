# UFX-MG

YAMAHA MG シリーズ（MG12XU）+ Yamaha Steinberg USB ドライバーを用いた
ステレオバス用エフェクター（PC内挿入処理）。
*UFX = エフェクトスイート / -MG = MG シリーズ対応。*

## 信号フロー

```
MG12XU ST OUT → USB → PC
   ↓
[IN メーター] → グラフィックEQ → コンプレッサー → [OUT メーター]
   ↓
USB → 出力 11/12ch → Group OUT → メインスピーカー
```

※ 11/12ch は **ST アサインしない**こと（フィードバック防止）。
※ Group は ST バスへ混ぜず、独立してメインへ送る設定にすること。

## 機能

- **グラフィックEQ**: ISO標準 1/3オクターブ 31バンド（20Hz〜20kHz）。
  サンプルレートに応じてナイキスト未満のバンドのみ有効化。±12 / ±6 dB。ON/BYPASS。
- **コンプレッサー**: ステレオリンク / ソフトニー /
  Threshold・Ratio・Attack・Release・Knee・OutGain。伝達特性グラフ＋GRメーター。
  ロータリーノブUI。ON/BYPASS。
- **デジタルメーター**: 入力・出力の dBFS ピークメーター（色ゾーン・ピークホールド）。
- **テーマ**: ライト / ダーク（プロオーディオ風）。背景画像も任意に設定可。

## ⚡ 低遅延のために（重要）

**ASIO ドライバー（「Yamaha Steinberg USB ASIO」など）での接続を強く推奨します。**
MME / Windows WDM-KS は遅延が大きくなります（往復 40–50ms 以上）。
- ⚙設定 で、入力・出力とも **`(ASIO)` 表記の同じデバイス**を選んでください。
- 非ASIOを選ぶと、画面下部に「⚠ 高遅延：ASIO推奨」と表示されます。
- ASIO 接続なら往復遅延の目安は **15–20ms**（96kHz でさらに短縮）。

## プロジェクト構成

```
mgfx/                     ← プロジェクトルート（自己完結）
├── mgfx/                 ← Python パッケージ
│   ├── __init__.py       （__version__ / ASIO 有効化）
│   ├── app.py            （PyQt5 GUI）
│   ├── engine.py         （sounddevice ストリーム）
│   └── dsp.py            （EQ / コンプ / メーター検出：純DSP）
├── run.py                ← 起動エントリ（PyInstaller 対象）
├── mgfx.bat              ← 開発起動ランチャー
├── setup.bat            ← 開発環境セットアップ（.venv 作成＋依存導入）
├── build.bat            ← 配布用 単一exe ビルド
├── mgfx.spec            ← PyInstaller 設定（ASIO DLL 同梱）
├── requirements.txt     ← 実行時依存（numpy / scipy / sounddevice / PyQt5）
├── requirements-dev.txt ← ＋ pyinstaller
├── CHANGELOG.md         ← 変更履歴（セマンティックバージョニング）
└── attic/               ← 未使用コード退避
```

## 開発（ソースから起動）

```
setup.bat      :: 初回のみ。.venv を作成し依存を導入
mgfx.bat       :: 起動（.venv が無ければ親 ..\.venv にフォールバック）
```

## 配布（単一exe のビルド）

```
build.bat      :: PyInstaller で dist\MG12XU-StereoFX.exe を生成
```

- 生成された `dist\MG12XU-StereoFX.exe` **単体**を配布できる（受け取り側は Python 不要）。
- ASIO 対応 PortAudio DLL は exe に同梱される（`mgfx.spec` の `collect_all`）。

## バージョン管理・アップデート（手動 Releases 運用）

1. 変更後、`mgfx/__init__.py` の `__version__` を更新（例 `1.0.1`）。
2. `CHANGELOG.md` に変更点を追記。
3. `build.bat` で exe を再生成。
4. git でコミットし、リリースタグを打つ：
   ```
   git add -A
   git commit -m "release: v1.0.1"
   git tag v1.0.1
   git push && git push --tags
   ```
5. GitHub の **Releases** にタグ `v1.0.1` で `MG12XU-StereoFX.exe` を添付して公開。
6. 利用者はウィンドウタイトルの `vX.Y.Z` で自分の版を確認し、新しい Release を手動で差し替える。

## レイテンシー / ASIO

- 起動時に環境変数 `SD_ENABLE_ASIO=1` を立て、sounddevice 同梱の
  **ASIO 対応 PortAudio DLL** を自動で読み込む（`mgfx/__init__.py`）。
- **ASIO で使う手順**:
  1. MG12XU を接続（Yamaha Steinberg USB ドライバー）。
  2. 下部「⚙ 設定」を開き、「入力機器」「出力機器」の**両方で同じ ASIO デバイス**
     （`(ASIO)` 表記の Yamaha Steinberg USB）を選ぶ。ASIO は単一デバイスで
     入出力を扱うため、in/out は必ず同一にすること。
  3. Block は **`0 (ASIO/ドライバー既定)`** を推奨。
- Windows 共有ミキサーをバイパスし、往復遅延の目安は
  WASAPI 共有の 40–50ms → **ASIO で 15–20ms** 程度。96kHz 化でさらに短縮可。
- xrun（ドロップアウト）が出る場合は Block を 256/512 に上げる。

## ライセンス

MIT License — 詳細は [LICENSE](LICENSE) を参照。
© 2026 Kanunsanun
