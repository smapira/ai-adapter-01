# Issue #13: `scan` が未インストールのツールを成功記号付きで表示する

> **優先度**: 🟢 低
> **種類**: 表示・診断 UX
> **対象ファイル**: `src/ai_adapter/commands/scan.py`
> **対象行**: 72-88行目付近

---

## 問題

ツールが検出されなかった場合も、`scan` は成功を示す `✓` を付けて表示する。

```text
✓ Claude Code: 0 detected (not installed)
✓ Codex: 0 detected (not installed)
```

全ツールが未検出でも `No potential problems detected.` と表示されるため、成功・未検出・問題なしの
意味が視覚的に混在している。

## 影響

- ユーザーがツールを正しく検出できたと誤認する
- 一覧を流し読みしたときに未導入状態を把握しにくい
- `doctor` や他コマンドの `✓` と意味が一致しない

## 修正方針

状態ごとの表示記号を分離する。

| 状態 | 表示例 |
|---|---|
| 検出済み・正常 | `✓ Codex: installed` |
| 未検出 | `- Codex: not detected` |
| 警告 | `⚠ Codex: configuration issue` |
| エラー | `✗ Codex: invalid configuration` |

## 受け入れ条件

- [ ] 未検出ツールに `✓` を表示しない
- [ ] `installed` と `not detected` の意味がヘルプまたは文書で明確になっている
- [ ] JSON の `installed` とテキスト表示が一致する
- [ ] 各状態の出力テストが追加されている
- [ ] `bash scripts/run_tests.sh` が成功する
