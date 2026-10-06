# QA: 設計書 02 実装（Claude native paths）

- 日付: 2026-10-06
- チェッカー: QA
- 対象: `documents/plans/dev/20261006_design_02_claude_native_paths.md` 対応実装
  （providers/claude.py / commands/agent.py / commands/skill.py / commands/mcp.py /
  scan.py / doctor.py / cli.py / tests）
- 前提: コードレビュー済み（Critical C1: 破壊的 JSON 上書き、Major M3: --fix 無視を修正済みと報告）、
  実装者は 748 テスト通過を報告（設計 01/02/03 の変更が混在した作業ツリー）
- 総合判定: **合格（条件付き）** — W1（--fix + --format claude 経路の回帰テスト欠落）を条件とする

---

## 1. テスト実行の独立検証 — ✅ PASS

`bash scripts/run_tests.sh` を独立実行:

- **748 passed in 14.82s**（実装者の報告と一致）
- C1 回帰テスト 2 件を確認・通過:
  - `tests/test_claude.py:468` `test_corrupt_json_aborts_merge`
    （corrupt JSON → `ClickException`、**ファイル非上書きを明示検証**: "File must NOT be overwritten."）
  - `tests/test_claude.py:478` `test_non_dict_top_level_aborts_merge`
    （`["not","a","dict"]` → `ClickException`、非上書きを検証）
- --fix テストを確認・通過:
  - `tests/test_agent.py:370` `test_agent_get_converts_tools_with_fix`
  - `tests/test_agent.py:416` `test_agent_get_all_converts_tools_with_fix`
  - `tests/test_agent.py:475` `test_agent_add_fix_flag`
- design-02 関連 5 ファイル限定の再実行（test_claude / test_agent / test_mcp / test_skill / test_scan）
  → **236 passed**

## 2. コード品質 — ✅ PASS

| コマンド | 結果 |
|---|---|
| `uv run ruff format --check .` | ✅ PASS（748 files already formatted） |
| `uv run ruff check .` | ✅ PASS（All checks passed!） |
| `uv run lizard src/ai_adapter/providers/claude.py src/ai_adapter/commands/agent.py src/ai_adapter/commands/skill.py src/ai_adapter/commands/mcp.py -C 20` | ✅ PASS（閾値超過なし。最大 CCN は agent.py の `agent_get_all` 系 9.4） |

## 3. C1 修正の検証 — ✅ PASS

`src/ai_adapter/providers/claude.py` の `merge_into_claude_json`（257-316 行目）:

| 検証項目 | 実装 | 結果 |
|---|---|---|
| JSON 読取失敗 → `ClickException` でエラー終了（上書きしない） | `claude.py:278-284` — `except (json.JSONDecodeError, OSError)` → `ClickException` raise。**write は validate の後**のため上書きされない | ✅ |
| トップレベル非 dict → エラー終了 | `claude.py:286-290` — `isinstance(existing, dict)` 検査 → `ClickException` raise | ✅ |
| 有効 JSON の場合のみ mcpServers マージ、他キー preserve | `claude.py:298-305` — `existing["mcpServers"] = new_servers` のみ操作、`projects` 等は verbatim 保持。未管理サーバーも preserve | ✅ |
| `.bak` バックアップ必須 | `claude.py:293-295` — `shutil.copy2(path, bak_path)`。新規ファイル時はバックアップなし（仕様どおり） | ✅ |
| テストが「abort する」側に更新されている | 上記 2 テストとも `assertRaises(click.ClickException)` + 非上書き検証。`test_preserves_unmanaged_keys`（399行目）も存在 | ✅ |

補足: `mcpServers: null` 等の非 dict 値も `test_non_dict_mcp_servers_treated_as_empty`（487行目）でカバーされ、クラッシュしない。

## 4. M3 修正の検証 — ⚠️ WARNING（W1）

### 4-1. コード実装は正しい — ✅

| 検証項目 | 実装 | 結果 |
|---|---|---|
| `sub-agent get --fix --format claude` で `--fix` が `deploy_agent_file` に渡る | `agent.py:377` — `_claude_deploy_agent_file(src, target.path, force, fix=fix)` | ✅ |
| `sub-agent get-all --fix --format claude` で `--fix` が `deploy_agents` に渡る | `agent.py:450` — `_claude_deploy_agents(..., fix=fix)` | ✅ |
| plain `.md` の array tools も `--fix` 時に変換（staging 経由） | `claude.py:117` — `needs_conversion = ... or (fix and src.name.endswith(".md"))`。`claude.py:114-124` で staging（`.aiadapter-staging.agent.md`）にコピー → `convert_agent_file` → `replace`。`finally: staging.unlink(missing_ok=True)` で残留防止 | ✅ |
| 変換時の警告出力 | `claude.py:118` — `click.echo(f"  Warning: converted tools format in {dest.name}", err=True)`（stderr） | ✅ |

**実動検証（QA で独立実施）**:
- `deploy_agent_file(plain.md, fix=True)` → `tools:\n  read: true\n  grep: true` に変換、staging 残留なし、警告 stderr 出力 ✅
- `deploy_agent_file(plain.md, fix=False)` → array 形式のまま ✅
- `deploy_agents(..., fix=True)` / `fix=False)` → 同上 ✅

### 4-2. W1: --fix + --format claude の統合回帰テスト欠落 — ⚠️

**問題**: `tests/test_agent.py` の `TestAgentClaudeFormat`（495 行目〜）には `--fix` と `--format claude` の**組み合わせテストが存在しない**。既存の --fix テスト（`TestAgentToolsConversion`）は standard フォーマット（`.github/agents/`）のみを対象としている。`tests/test_claude.py` の `TestClaudeDeployAgentFile` も `fix=True` のテストがない。

**リスク**: M3 修正（--fix 無視の修正）が claude format 経路で再発しても、既存テストは検知できない。実装は正しい（実動検証済み）が、回帰検知網が不在。

**推奨**: `tests/test_agent.py` の `TestAgentClaudeFormat` に以下を追加:

```python
def test_get_claude_fix_converts_plain_md_array_tools(self):
    """--fix + --format claude: plain .md array tools converted via staging."""
    # store に plain .md（tools: [read, grep]）を配置
    # sub-agent get <name> --fix --format claude --project-dir <proj>
    # → .claude/agents/<name>.md に object 形式で配置
    # → "Warning: converted tools format" が出力される

def test_get_all_claude_fix_converts_tools(self):
    """--fix + --format claude (get-all): all plain .md array tools converted."""
```

あわせて `tests/test_claude.py` の `TestClaudeDeployAgentFile` に `fix=True` の単体テスト追加も推奨。

## 5. パス検証 — ✅ PASS

| 検証項目 | 実装 | 結果 |
|---|---|---|
| `resolve_scope_path()` を使用 | `claude.py:58, 68, 159, 201` — 全パス解決が `config.resolve_scope_path` 経由。独自マップなし | ✅ |
| `.claude/skills/` `.claude/agents/` のデプロイ先 | `config.py:183-184`（project）、`config.py:200-201`（user）— `("claude","agents"): ".claude/agents"` 等 | ✅ |
| `~/.claude.json`（user MCP） | `claude.py:72-73` — `resolve_user_json_path()` = `Path.home() / ".claude.json"` | ✅ |
| `.mcp.json`（project MCP） | `mcp.py:306-309` — `--format claude --scope project` は `_mcp_get_standard` を呼ぶ（`.mcp.json` 出力。設計どおり既存 standard で充足） | ✅ |
| 設計書のリスク対策「scope の独自実装しない」 | `claude.py:10-12` docstring でも明記。`_PROJECT_SCOPE_DIRS` / `_USER_SCOPE_DIRS` は design-01 で定義済みの単一マップを参照 | ✅ |

## 6. セキュリティ — ✅ PASS

### 6-1. `--scope user` 時に `add_to_gitignore` が呼ばれない

| 場所 | 実装 | 結果 |
|---|---|---|
| `claude.py:170-171`（deploy_agents） | `if target.use_gitignore: add_to_gitignore(dest)` | ✅ |
| `claude.py:219-220`（deploy_skills） | 同上ガード | ✅ |
| `agent.py:378-379`（agent get claude 分岐） | 同上ガード | ✅ |
| `config.py:255`（判定元） | `use_gitignore = scope == "project"` — user scope は常に False | ✅ |
| `agent.py:392, 466`（standard 分岐） | `.github/agents/` は常に project スコープのため無条件呼び出しで問題なし | ✅ |

**実動検証**: `deploy_agents(..., scope="user")` を mock で検証し、`add_to_gitignore` 呼び出し回数 0 を確認。project scope では呼び出しあり。

### 6-2. scan が `is_ignored()` を適用

| 場所 | 実装 | 結果 |
|---|---|---|
| `scan.py:190`（_scan_agents） | `is_ignored(f"{scan_rel}/{f.name}")` | ✅ |
| `scan.py:211`（_scan_skills） | `is_ignored(f"{scan_rel}/{d.name}/SKILL.md")` | ✅ |
| `scan.py:230`（_scan_user_instruction） | `is_ignored(scan_rel)` | ✅ |
| `scan.py:243`（_scan_mcp_servers） | `is_ignored(scan_rel)` | ✅ |
| project `.claude/` 検出（scan.py:288-291） | `_scan_agents` / `_scan_skills` を再利用 → `is_ignored` も適用される | ✅ |
| `SCAN_IGNORE_PATTERNS` | `scan.py:39` — `.claude/.credentials.json` を含む | ✅ |
| テスト | `tests/test_scan.py` — `test_scan_project_claude_applies_ignore_patterns`、`test_scan_ignores_generic_secrets` が存在し PASS | ✅ |

## 補足: 仕様どおりの未実装項目（FAIL ではない）

| 項目 | 設計書の記載 | 実装状況 | 判定 |
|---|---|---|---|
| `cli.py` の `claude_group` 登録 | §4: 「Phase A では空グループ。将来の claude install 用。**実装は後続**」 | 未登録（`main.add_command` に claude_group なし） | ✅ 仕様どおり |
| `doctor.py` の `~/.claude.json` mcpServers 検証 | §2.3: 「Phase B（将来）」 | `doctor.py:214-246` で `_claude_user_mcp_issues` として**実装済み**（mcpServers 形状検証） | ✅ 計画より先行実装（過剰品質） |
| README の Claude Code セクション | §7 完了定義 | `README.md:585-591` に Claude Code Integration セクションあり | ✅ 完了 |

---

## 総合判定: **合格（条件付き）**

実装は設計書 02 に準拠し、Critical C1 と Major M3 の修正は**コードレベルで正しい**ことを確認した。748 テスト全パス、ruff/lizard 全パス、C1/M3 の実動検証もすべて通過。パス解決・gitignore セキュリティ・scan の認証情報除外も設計どおり。

**条件**: W1（--fix + --format claude 経路の回帰テスト欠落）を解消すること。実装自体は正しいため、リリースを止めずにテスト追加のみで対応可能。

## 推奨アクション

1. **W1（中・必須）**: `tests/test_agent.py` の `TestAgentClaudeFormat` に `--fix` + `--format claude` の組み合わせテストを追加（plain .md の array→object 変換 + 警告出力の検証）。あわせて `tests/test_claude.py` の `TestClaudeDeployAgentFile` に `fix=True` の単体テストを追加。
2. 追加後 `bash scripts/run_tests.sh` で再検証し、設計書 02 の完了定義チェックリストを更新。
