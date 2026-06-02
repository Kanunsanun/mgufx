# 変更履歴 (Changelog)

本プロジェクトのバージョンは [セマンティック バージョニング](https://semver.org/lang/ja/)
（MAJOR.MINOR.PATCH）に従う。

## [1.0.1] - 2026-06-02
### 修正
- 配布exeが起動時に `ModuleNotFoundError: No module named 'importlib.resources'`
  でクラッシュする問題を修正（scipy.stats._sobol の動的importをPyInstallerが
  拾えていなかったため、importlib.resources/metadata を明示同梱）。

## [1.0.0] - 2026-06-02
### 初回リリース
- 31バンド グラフィックEQ（ISO 1/3オクターブ、scipy sosfilt、ON/BYPASS）
- ステレオリンク コンプレッサー（Threshold/Ratio/Attack/Release/Knee/OutGain、
  伝達特性グラフ＋GRメーター、ロータリーノブUI）
- 入出力ピークメーター（色ゾーン、ピークホールド）
- ASIO対応（SD_ENABLE_ASIO、96kHz、低遅延）
- プロオーディオ風GUI（ライト/ダーク両テーマ、QPixmapキャッシュ描画）
