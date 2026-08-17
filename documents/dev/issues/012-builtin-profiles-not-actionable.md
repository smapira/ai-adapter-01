# Issue #12: 組み込みプロファイルが実用的な構成を適用できない

> **優先度**: 🟡 中
> **種類**: オンボーディング・プリセット品質
> **対象ファイル**: `src/ai_adapter/profiles/python.yaml`, `src/ai_adapter/profiles/web-development.yaml`

---

## 問題

`setup list` では `python` と `web-development` が利用可能な推奨プロファイルとして表示されるが、
実際の適用結果が説明から期待される内容と一致しない。

- `python` は skills / MCP / agents / commands がすべて空
- `web-development` の Skill と Agent は取得元を持たず、標準環境では `source not found (skipped)` になる
- `python` の適用は何も変更しなくても `Profile applied.` と表示される

## 影響

- 初回ユーザーが `setup` の価値を確認できない
- 「推奨構成を適用した」という誤認が生じる
- スキップ後に何を準備すべきか案内されない

## 修正方針

- 組み込みプロファイルには自己完結したリソース、または明示的な取得元を含める
- 空プロファイルは削除するか、テンプレート・未実装であることを表示する
- 適用前に解決可能性を検証し、適用予定・スキップ予定をプレビューする
- 変更件数が `0` の場合は `Profile applied` ではなく no-op と表示する

## 受け入れ条件

- [ ] `python` が有用な構成を適用するか、利用可能一覧から除外される
- [ ] `web-development` の全リソースに解決可能な取得元がある
- [ ] `--dry-run` が実適用時と同じ解決結果を表示する
- [ ] 変更 `0` 件を成功適用として表示しない
- [ ] 組み込みプロファイルの適用結果を検証するテストがある
- [ ] `bash scripts/run_tests.sh` が成功する
