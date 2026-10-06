# QA レポート: 設計書 04 実装（OpenCode 拡張）

- 日付: 2026-10-06
- QA: Copilot (直接検証)
- 対象: `documents/plans/dev/20261006_design_04_opencode_extensions.md`
- 結果: **合格**

---

## 1. テスト実行の独立検証 — ✅ PASS

`bash scripts/run_tests.sh` → **838 passed in 4.21s**
- `tests/test_opencode.py` の jsonc テスト含む
- `tests/test_agent.py` の `TestAgentOpencodeFormat`（.md リネーム後）含む

## 2. コード品質 — ✅ PASS

| コマンド | 結果 |
|---------|------|
| `ruff format --check` | ✅ 76 files already formatted |
| `ruff check` | ✅ All checks passed |
| `lizard -C 20` | ✅ 閾値超過なし（max CCN 18.8） |

## 3. M1 修正の検証（.agent.md → .md 正規化）— ✅ PASS

- `agent.py:137-139` で `dest_name = src.name[: -len(".agent.md")] + ".md"` を確認
- OpenCode 公式ドキュメント（https://opencode.ai/docs/agents/）の「The markdown file name becomes the agent name」に基づく
- テストが `.md` パスを期待していることを確認（`test_agent.py` / `test_cli.py` 更新済み）

## 4. jsonc パーサの安全性 — ✅ PASS

- `_strip_json_comments()`（opencode.py:375）がトークナイザ方式を使用（正規表現でなく文字列状態管理）
- 文字列内の `//` を保護（in_string 状態管理 + エスケープ処理）
- `opencode.jsonc` 単独でも valid と判定（"not found" エラーにしない）
- `opencode validate` が `.json` → `.jsonc` の順で探索

## 5. Minor 修正の検証 — ✅ PASS

| ID | 検証結果 |
|----|---------|
| m1 | `_find_opencode_config()` が `.is_file()` を使用（ディレクトリを拾わない）✅ |
| m2 | uninstall メッセージが `"opencode.json / opencode.jsonc not found."` ✅ |
| m3 | `_load_json_file()` のエラーメッセージが `path.name` を使用 ✅ |
| m4 | `--with-compat-skills` の help が "Only effective when skills are registered in ai-adapter." ✅ |
| m5 | 既存 `opencode.jsonc` への上書き時にプロンプト `"overwriting will discard hand-written comments. Generate anyway?"` ✅ |

## 6. セキュリティ — ✅ PASS

- `--scope user` 時に `add_to_gitignore` が呼ばれないこと（`use_gitignore` ガードを agent.py:167, 435, 443 で確認）

---

## 総合判定: **合格**

全 838 テストが独立実行で通過し、M1（.agent.md → .md 正規化）と Minor m1-m5 の修正はコード・テストの両面で確認。jsonc パーサのエスケープ処理・文字列境界管理は堅牢。セキュリティ（gitignore スキップ）も担保されている。
