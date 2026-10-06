# QA レポート: 設計書 08 実装（VS Code エディタ設定 + .vscode/mcp.json + .github/instructions デプロイ）

- 日付: 2026-10-07
- QA: Codex QA (直接検証)
- 対象: `documents/plans/dev/20261006_design_08_vscode_editor_and_mcp.md`
- 前提: コードレビュー済み（Critical C1: extensions.json 破壊、Major M1-M4 を修正済みと報告）、実装者は 843 テスト通過を報告
- 結果: **不合格（要修正）** — チェック項目 1-4, 6, 7 は PASS、項目 5（M3）は主要ユースケースで FAIL、項目 5（M2）に新たな不整合を検出

---

## 1. テスト実行の独立検証 — ✅ PASS

`bash scripts/run_tests.sh` → **843 passed in 4.71s**（実装者の報告と一致）

- `tests/test_vscode.py` 32 件すべて通過（C1/M1/M4 回帰テスト含む）
- C1 回帰: `test_save_extensions_preserves_other_keys`, `test_save_extensions_corrupt_aborts`
- M1 回帰: `test_merge_mcp_list_top_level_no_crash`, `test_merge_mcp_servers_not_dict_no_crash`
- M4: `test_install_prompts_when_existing`（merge の confirm パス）
- 既知警告 1 件: `test_codex.py:326` の `TOMLDecodeError` DeprecationWarning（今回範囲外）

## 2. コード品質 — ✅ PASS

| コマンド | 結果 |
|---------|------|
| `ruff format --check` | ✅ 76 files already formatted |
| `ruff check` | ✅ All checks passed |
| `lizard -C 20`（vscode.py / instruction.py） | ✅ 閾値超過なし（max CCN 19: `instruction_remove@250-297`） |

⚠️ `instruction_remove` は CCN 19 で閾値 20 に接近。今回の M3 不具合もこの関数に含まれるため、リファクタリング候補。

🟢 軽微: `tests/test_vscode.py:370-371` に `if __name__ == "__main__": unittest.main()` がファイル中盤に配置。直接実行（`python tests/test_vscode.py`）すると、定義済みクラスしか収集されず `TestVscodeReviewFixes`（C1/M1/M4 回帰 5 件）が**実行されない**。pytest 経由（run_tests.sh）ではガードがスキップされるため全件実行されるが、ファイル直実行の安全性を損なう配置。末尾へ移動すべき。

## 3. C1 修正の検証（extensions.json 保護） — ✅ PASS

`src/ai_adapter/providers/vscode.py:172-198` `save_extension_recommendations()`:

| 要件 | 検証結果 |
|------|---------|
| トップレベル dict を読み `recommendations` のみ差し替え | ✅ `data["recommendations"] = recommendations` のみ。`unwantedRecommendations` 等の他キー保持（`test_save_extensions_preserves_other_keys` で実証） |
| 破損 JSON で `ClickException`（上書きしない） | ✅ `json.JSONDecodeError` → `ClickException` を送出。`test_save_extensions_corrupt_aborts` でファイル内容が不変であることを検証 |
| `.bak` バックアップ | ✅ `shutil.copy2(ext_path, bak_path)`（vscode.py:179-180）をパース前に実施 |

🟢 軽微: `.bak` はコード上取得されるが、`extensions.json.bak` の存在を断言するテストは未実装（`test_install_backup_created` は `mcp.json.bak` のみ検証）。

## 4. M1 修正の検証（merge 型検証） — ✅ PASS

`src/ai_adapter/providers/vscode.py:93-133` `merge_into_vscode_mcp_json()`:

| 要件 | 検証結果 |
|------|---------|
| トップレベル list/scalar で AttributeError クラッシュしない | ✅ `existing = loaded if isinstance(loaded, dict) else {}`（vscode.py:120）でガード。`test_merge_mcp_list_top_level_no_crash` で list 実動確認 |
| `servers` が非 dict でもクラッシュしない | ✅ `if not isinstance(existing_servers, dict): existing_servers = {}`（vscode.py:128-129）。`test_merge_mcp_servers_not_dict_no_crash` で実動確認 |

## 5. M2/M3 修正の検証 — ⚠️ WARNING（M2a/M2b PASS、M2 新規不整合 + M3 FAIL）

### M2a: `vscode install` が `add_to_gitignore` を呼び出さないこと — ✅ PASS

- `src/ai_adapter/providers/vscode.py:291-294`: `merge_into_vscode_mcp_json()` 呼び出し後に gitignore 呼び出しなし。コメントで意図明記（「VS Code docs recommend committing .vscode/mcp.json」）
- 実動確認: git リポジトリ内で `vscode install` 後も `.gitignore` 非作成

### M2b: `--target github-*` の instruction デプロイが `add_to_gitignore` を呼び出さないこと — ✅ PASS

- `src/ai_adapter/commands/instruction.py:243-244`: `if scope == "project" and target == "root": add_to_gitignore(dest)` で root ターゲットのみ
- 実動確認: `agent get S --target github-copilot` 後も `.gitignore` 変化なし

### 🟡 NEW-ISSUE-1 (Major): `mcp get --format vscode` が同一ファイルに対して gitignore する（M2 系の不整合）

- **場所**: `src/ai_adapter/commands/mcp.py:256-266` `_mcp_get_vscode()`
  ```python
  _merge_vscode_mcp(vscode_path, data, force=force)
  _config.add_to_gitignore(vscode_path)   # ← ここで .vscode/mcp.json を gitignore
  ```
- **実動で再現**（git リポジトリ内）:
  1. `ai-adapter vscode install` → `.gitignore` **非作成**（M2a どおり）
  2. `ai-adapter mcp get --format vscode --path . --force` → `.gitignore` に `/.vscode/mcp.json` **追記**
- **矛盾**:
  - README.md:629 は `mcp get --format vscode` を「same as install」と記載するが、実際は gitignore 挙動が異なる
  - VS Code 公式ドキュメント（Context7 `microsoft/vscode-docs` / docs/agent-customization/mcp-servers.md）は "Include workspace configuration in source control to share MCP servers with your team" と明記 — `vscode.py` の M2 修正理由は `mcp get --format vscode` にも同じく妥当
- **影響**: 同一出力ファイル `.vscode/mcp.json` を生成する 2 コマンドで git 追跡可否が二分。チーム共有 VS Code MCP 設定を意図してコミットする運用で `mcp get --format vscode` を使うと無効化される
- **回帰テスト不在**: `tests/test_vscode.py` / `tests/test_mcp.py` ともに `add_to_gitignore` の呼び出し有無を検証するテストなし
- **修正案**: `mcp.py:266` の `_config.add_to_gitignore(vscode_path)` を削除（`vscode install` と同じく非 gitignore に揃える）。あわせて「gitignore しない」回帰テストを `tests/test_vscode.py`（`vscode install`）と `tests/test_mcp.py`（`mcp get --format vscode`）に追加

### M3: `instruction remove` が `.github/instructions/` と `.github/copilot-instructions.md` も削除すること — ❌ FAIL（部分的）

`src/ai_adapter/commands/instruction.py:284-295`:

```python
github_instructions = Path.cwd() / ".github" / "instructions"
if github_instructions.is_dir():
    for f in github_instructions.iterdir():
        if f.is_file() and (f.stem == name or f.name == name):
            ...
copilot_instructions = Path.cwd() / ".github" / "copilot-instructions.md"
if copilot_instructions.is_file() and copilot_instructions.stem == name:
    copilot_instructions.unlink()
```

| デプロイ先 | 実動結果 |
|-----------|---------|
| `.github/instructions/STYLE.md`（`--target github-instructions` で STYLE デプロイ → `agent remove STYLE`） | ✅ 削除される（`f.stem == "STYLE"` が一致） |
| `.github/copilot-instructions.md`（`--target github-copilot` で **AGENTS** デプロイ → `agent remove AGENTS`） | ❌ **削除されない**（`copilot_instructions.stem` は `"copilot-instructions"` で `"AGENTS"` と不一致 → ファイルが残存することを実動確認） |
| `.github/copilot-instructions.md`（指示名が `copilot-instructions` の場合） | ✅ 削除される（stem 一致。実動確認済み） |

- **根本原因**: 設計書 08 タスク 08-2 の仕様は「任意の instruction を固定名 `copilot-instructions.md` としてデプロイ」。しかし remove 側は `copilot-instructions.md` の stem と**登録 instruction 名の一致**を条件にしており、README 記載の主要ユースケース（`agent get AGENTS --target github-copilot` → `agent remove AGENTS`）でファイルが残り続ける
- instruction.py:283-284 のコメント自体が「get/remove lifecycle must match, otherwise files linger forever」と警告しているが、copilot-instructions.md 経路でこの原則が守られていない
- **関連**: `instruction get` は `--project-dir` 対応だが `instruction remove` はオプションなし（`Path.cwd()` 固定）。`--project-dir X --target github-*` でデプロイしたファイルは、cwd が異なれば remove では掃除できない
- **回帰テスト不在**: `tests/test_instruction.py` / `tests/test_agent.py` に `remove` + `.github` 配置ファイルの削除テストが 0 件
- **修正案**:
  ```python
  # copilot-instructions.md は固定名ファイル。指示名に依存せず削除する
  # （デプロイで常にこの名前になるため、lifecycle が一致する）
  copilot_instructions = Path.cwd() / ".github" / "copilot-instructions.md"
  if copilot_instructions.is_file():
      copilot_instructions.unlink()
      click.echo("Removed copilot-instructions.md from .github/.")
  ```
  ただし誤削除リスク（手書きの copilot-instructions.md を登録外 instruction の remove で消す）を避けるため、削除前に「この instruction が github-copilot へデプロイされた記録」を store に持つか、確認プロンプトを挟む方針も検討。いずれにせよ M3 の回帰テスト（github-instructions / github-copilot 両経路）を追加すること。

## 6. M4 テストカバレッジ — ✅ PASS（軽微な空白あり）

| ケース | テスト | 結果 |
|--------|--------|------|
| C1 回帰（unwantedRecommendations 保持） | `test_save_extensions_preserves_other_keys` | ✅ |
| C1 回帰（破損ファイル） | `test_save_extensions_corrupt_aborts` | ✅ |
| M1 回帰（list トップレベル） | `test_merge_mcp_list_top_level_no_crash` | ✅ |
| M1 回帰（servers 非 dict） | `test_merge_mcp_servers_not_dict_no_crash` | ✅ |
| M4（merge の confirm パス） | `test_install_prompts_when_existing`（click.confirm を Abort にモック） | ✅ |

🟢 空白:
- `extensions.json.bak` の存在断言テストなし（C1 の `.bak` 要件は実装のみ）
- M2/M3 の回帰テストが不在（項目 5 参照）
- `src/ai_adapter/doctor.py:199` `_vscode_config_issues()`（.vscode 設定の doctor 診断）は実装されているが、`tests/test_doctor.py` に vscode テストが 0 件
- `tests/test_vscode.py` の `TestMcpGetVscodeFormat` は `tests/test_mcp.py` の `TestMcpVscodeFormat` と内容が重複

## 7. VS Code MCP 形式 — ✅ PASS

| 要件 | 検証結果 |
|------|---------|
| `servers` キー | ✅ `export_mcp()`（vscode.py:52-90）が `{"servers": {...}}` を返す。`test_export_format` で `assertNotIn("mcpServers", data)` |
| `type: "stdio"` | ✅ 各エントリに `"type": "stdio"` を付与。非 stdio（command 空）は警告付きスキップ（AC4 一致） |
| `${env:KEY}` 形式 | ✅ `entry["env"] = {k: f"${{env:{k}}}" for k in s.env_keys}`。VS Code 公式ドキュメント（Context7 `microsoft/vscode-docs`）の stdio サーバー仕様（`servers` トップレベル + `type` 必須 + env は `${...}` 変数構文）と整合 |
| TOOL_ORDER が append のみ | ✅ `TOOL_ORDER[:-1] + ("vscode",) + TOOL_ORDER[-1:]`（scan.py:70-74）で既存タプルを再定義せず vscode を project 直前に挿入。マスター設計の「自ツールのみ append、全体再定義禁止」を満たす |
| TOOL_LABELS にラベル | ✅ `TOOL_LABELS["vscode"] = "VS Code"`（scan.py:76-83）。`test_tool_order_includes_vscode` / `test_tool_labels_include_vscode` で検証済み |
| scan 登録 | ✅ `scan_all` に `items.extend(scan_vscode(project))`（scan.py:447）。`.github/copilot-instructions.md` 検出も `scan_project`（scan.py:389-392）で実装・テスト済み |

---

## 総合判定: **不合格（要修正）**

843 テスト全パス、ruff/lizard 全パス、Critical C1 と Major M1/M4 の修正は**コード・テスト・実動のすべてで確認**された。VS Code MCP 形式・TOOL_ORDER・scan 拡張も設計どおり。

しかし QA で以下を検出した:

1. **❌ M3 修正が主要ユースケースで機能しない**: `agent get AGENTS --target github-copilot` → `agent remove AGENTS` で `.github/copilot-instructions.md` が残存（instruction.py:292-295 の stem 一致条件が原因）。M3 が目指した「get/remove lifecycle 一致」が copilot 経路で未達
2. **🟡 M2 系の新たな不整合**: `mcp get --format vscode`（mcp.py:266）が `.vscode/mcp.json` を gitignore し、`vscode install` と挙動が逆。README「same as install」の記述とも矛盾。VS Code 公式の「commit 推奨」方針とも相反
3. **🟢 テスト網の空白**: M2/M3 回帰テスト、`extensions.json.bak` 断言、doctor の vscode 診断テストが不在

## 推奨アクション

1. **[P0] M3 修正の再実装**（instruction.py:292-295）: `copilot-instructions.md` は固定名ファイルなので指示名 stem への依存を外す。誤削除対策（store へのデプロイ記録 or 確認プロンプト）を方針として決定したうえで実装し、`--project-dir` 非対称も含めて lifecycle を揃える
2. **[P0] M3 の回帰テスト追加**（tests/test_instruction.py）: github-instructions / github-copilot 両経路の deploy → remove → ファイル消失を検証
3. **[P1] mcp.py:266 の `add_to_gitignore` 削除**（vscode install と統一）+ README.md:629 の「same as install」記述を正確化 + 「gitignore しない」回帰テスト追加
4. **[P2] テスト網補強**: `extensions.json.bak` 断言、doctor の `_vscode_config_issues` テスト、`tests/test_vscode.py` 内の `__main__` ガードを末尾へ移動
5. **[P2] `instruction_remove` のリファクタリング検討**（CCN 19、閾値接近。M3 修正時に分割を推奨）

修正 1-3 完了後に再 QA を実施すること。
