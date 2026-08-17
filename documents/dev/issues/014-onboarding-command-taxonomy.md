# Issue #14: 初回導線とコマンド用語が一貫していない

> **優先度**: 🟢 低
> **種類**: 情報設計・オンボーディング
> **対象ファイル**: `README.md`, `src/ai_adapter/cli.py`, 各コマンドモジュール

---

## 問題

README 冒頭では `init` の後に `start` を実行する3コマンド構成を案内しているが、Quick Start は
`start` のみを初期化手順としている。また、CLI の主要用語が初見で理解しにくい。

- `agent`: ルートの `AGENTS.md` 等を管理
- `sub-agent`: `.github/agents/*.agent.md` を管理
- `add-all-rec` / `get-all-rec`: `rec` の意味とデータ方向が名前だけでは分かりにくい
- `setup`: 中央ストアへの登録であり、プロジェクトへの展開ではない

## 影響

- 初回ユーザーが `init` と `start` のどちらを使うべきか判断できない
- `agent` と `sub-agent` を誤って選択する
- import / register / deploy / sync のデータ方向を学習する負担が大きい
- ルートヘルプに多数のコマンドが並び、推奨ワークフローが埋もれる

## 修正方針

- README の最短導線を `scan -> init/start -> setup/import -> deploy -> doctor` のように一本化する
- `init` と `start` の責務を整理し、どちらかを推奨コマンドとして明示する
- `agent` / `sub-agent` の名称または説明をユーザーの配置先中心に見直す
- `*-rec` は `import-all` / `deploy-all` 等の方向が分かる名称を検討する
- 既存名を変更する場合は非推奨エイリアス期間を設ける

## 受け入れ条件

- [ ] README 冒頭と Quick Start の初期化手順が一致する
- [ ] 初回利用の推奨ワークフローが5ステップ以内で提示される
- [ ] `agent` と `sub-agent` の違いがルートヘルプだけで理解できる
- [ ] 一括操作コマンドのデータ方向が名称または説明から分かる
- [ ] 既存ユーザー向けの互換性方針が定義されている
