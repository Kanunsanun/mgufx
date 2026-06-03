# 変更履歴 (Changelog)

本プロジェクトのバージョンは [セマンティック バージョニング](https://semver.org/lang/ja/)
（MAJOR.MINOR.PATCH）に従う。

## [1.0.3] - 2026-06-03
### 変更
- アプリ名称を **UFX-MG** に正式統一（ウィンドウタイトル・配布物名）。
- 専用アイコン（角丸）を追加。exe・ショートカット・アプリ一覧に表示。
### 追加
- **Windows インストーラー版**（Inno Setup）を提供。
  - スタートメニュー登録／デスクトップショートカット（任意）／アンインストーラー対応。
  - ユーザー単位インストール（管理者権限不要）。
  - アプリ一覧（設定→アプリ）に表示されるように。
- ビルドを onedir 方式に変更（起動高速化）。

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
