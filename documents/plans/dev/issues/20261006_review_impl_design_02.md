# コードレビュー: 設計書 02 実装

- 日付: 2026-10-06
- レビュアー: Codex Reviewer
- 対象: 設計書 02 実装（providers/claude.py 新規、skill/agent/mcp/scan/doctor 拡張）
- 結果: **要修正** — Critical 1 件、Major 3 件

---

## 検証結果

| 検証 | 結果 |
|------|------|
| テストスイート | **747 passed** |
| ruff format / ruff check | 全パス（74 files formatted） |
| lizard -C 20 | 閾値超過なし（claude.py 等 CCN 最大 21.3 は既存 doctor.py） |
| 仕様→実装トレーサビリティ | AC1-AC5 とも主要 AC は概ね満たす |

---

## 🔴 Critical

### C1: `~/.claude.json` が壊れている/非 dict だと「非管理キーごと」上書きされる（AC2 違反）

- **箇所**: `src/ai_adapter/providers/claude.py:248-288`
- **内容**: `merge_into_claude_json` は `json.loads` 失敗またはトップレベル非 dict を `existing = {}` として扱い、ファイル全体を `{"mcpServers": …}` のみで書き換える。
- **問題**: 設計書 02 タスク 02-3 AC2 は「管理対象外のキー（プロジェクト履歴等）は絶対に変更しない」と明記。`~/.claude.json` は Claude Code 自身のユーザーデータ置き場であり、`projects` 等が消える。
- **再現**: 不正 JSON を `~/.claude.json` に置き `mcp get --format claude --scope user --force` → `projects` 等が消えたファイルに置換される。
- **確認済み**: テスト `test_corrupt_json_treated_as_empty` がこの破壊挙動を規定している。
- **修正方針**: JSON 読取失敗・非 dict トップレベルを「上書き継続」から「エラー終了（ClickException）」へ変更。

---

## 🟡 Major

| ID | 指摘 |
|----|------|
| M1 | 設計書内矛盾: §3 タスク 02-1 は `skill get <name> --format claude` を期待するが、実装は get-all のみ。§4/完了定義は get-all で整合。§3 のみ修正して確定すべき |
| M2 | project `.claude/settings.json` / `settings.local.json` の scan 検出が未実装（§2.3「scan 検出のみ追加」との乖離） |
| M3 | `sub-agent get/get-all --fix --format claude` で `--fix` が黙って無効。plain `.md` の array tools も変換されない（`convert_agent_file` は `.agent.md` 制約のため） |

---

## 🟢 Minor

| ID | 指摘 |
|----|------|
| m1 | `claude_group` 登録の要否明記（設計書は「Phase A では空グループ、実装は後続」） |
| m2 | deploy ヘルプ文の修正 |
| m3 | merge 書き込み例外の `ClickException` 化 |
| m4 | `find_agent_file` の決定的順序 |
| m5 | 実装者報告の doctor パス修正（`commands/doctor.py` ではなく `doctor.py`） |
| m6 | 設計書の状態表記更新 |

---

## 総合判定

**要修正**。主要 AC そのものは概ね満たしており、修正範囲は限定的。
Critical C1（`~/.claude.json` 非管理キー消失経路）の修正完了後に再確認が必要。
