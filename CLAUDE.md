# mgfx プロジェクト固有ルール（Claude 行動ルール）

`asobiba/mgfx/` は自己完結した配布プロジェクト
（GitHub 公開リポジトリ `Kanunsanun/mgufx`、MIT ライセンス）。
親 `asobiba/CLAUDE.md` とグローバルルールを継承しつつ、本プロジェクトでは
以下を**追加で許可なしに実行可能**とする。

## このプロジェクトで許可なしに実行可能（追加分）

- **git のバージョン管理操作全般（外部通信を含む）**
  - ローカル操作: `git add` / `commit` / `tag` / `branch` / `checkout` /
    `merge` / `log` / `status` / `diff` など
  - **リモート通信**: `git push`（`git push --tags` 含む）/ `pull` / `fetch` /
    `clone`。GitHub `Kanunsanun/mgufx` への push 等の外部通信を許可する。
- **GitHub リリース操作（`gh` CLI、認証済みの場合）**
  - `gh release create` / `gh release upload` / `gh release view` /
    `gh release list` など、バージョン公開に必要なコマンド。
- **配布ビルド**: `python -m PyInstaller` / `build.bat`（dist/ への単一exe生成）。

## 引き続き許可制（変更なし）

- 上記（git / gh のバージョン管理・リリース、配布ビルド）**以外**の、
  外部 API・外部サービスへのデータ送受信を伴うコマンド・スクリプトの実行。
- プロジェクトディレクトリ外への操作。
- **API キーの受け渡し**（Claude は API キーを受け取らない）。

## 補足

- リリース手順は `README.md`「バージョン管理・アップデート」を参照
  （`__version__` 更新 → CHANGELOG 追記 → build → commit → tag → push →
  Releases に exe 添付）。
