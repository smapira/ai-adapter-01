# QA レポート: 設計書 07 実装（Cursor 拡張: .cursorrules + plugin package）

- 日付: 2026-10-07
- QA: Codex QA (直接検証)
- 対象: `documents/plans/dev/20261006_design_07_cursor_extensions.md`
- 前提: コードレビュー済み（Critical C1: パストラバーサル、Major M1: plugin 名サニタイズを修正済みと報告）、実装者は 995 テスト通過を報告
- 結果: **不合格（要修正）** — 項目 1, 2, 5, 6, 7 は PASS、項目 3（C1）は回帰テスト欠落で WARNING、項目 4（M1）は期待値不一致 + テスト不在で FAIL

---

## 1. テスト実行の独立検証 — ✅ PASS

`bash scripts/run_tests.sh` → **995 passed, 1 warning in 4.50s**（実装者の報告と一致）

- 設計書 07 関連テストも通過: `tests/test_cursor.py` 45 件、`tests/test_instruction.py` の `TestInstructionCursorrulesFormat`、`tests/test_skill.py` の `TestSkillCursorPlugin`
- 既知警告 1 件: `tests/test_codex.py:326` の `TOMLDecodeError` DeprecationWarning（今回範囲外・既存）

## 2. コード品質 — ✅ PASS

| コマンド | 結果 |
|---------|------|
| `uv run ruff format --check .` | ✅ 80 files already formatted |
| `uv run ruff check .` | ✅ All checks passed |
| `uv run lizard cursor.py instruction.py skill.py -C 20` | ✅ 閾値超過なし |

- 最大 CCN: `instruction_remove@300-350` = 18（閾値 20 に接近。設計 08 QA と同様、リファクタリング候補）
- `deploy_skills_plugin` CCN 8 / `_sanitize_plugin_name` CCN 4 — 問題なし

## 3. C1 修正の検証（パストラバーサル） — ⚠️ WARNING（コード修正は PASS、回帰テストが不在）

### コード修正 — ✅ PASS

`src/ai_adapter/providers/cursor.py:331-401` `deploy_skills_plugin()`:

| 要件 | 検証結果 |
|------|---------|
| `is_safe_store_name()` で skill 名を検証 | ✅ cursor.py:374-377。`/` `\` `.` `..` を含む名前を skip |
| `is_relative_to()` で dest_dir 外への解決を防止 | ✅ cursor.py:378-383。prefix-sibling escape（`../skills-evil` 等）も遮断 |
| ガードの順序 | ✅ `src.exists()` チェック後 → `is_safe_store_name()` → `dest.resolve()` + `is_relative_to()` → `shutil.rmtree`/`copytree`。破壊的操作の前に両ガードが成立 |
| `resolve_scope_path()` 経由の dest 決定 | ✅ cursor.py:313（item 7 参照） |

- 同種ガードの実装は `zed.py:216-223`（design 06 C2）と同一パターンで、コメントでも明記済み（cursor.py:370-372）。

### ❌ 回帰テストが不在

- QA チェック項目「パストラバーサル回帰テストが存在すること」を満たさない
- `tests/test_cursor.py` の `TestCursorPluginDeploy`（8 テスト）・`tests/test_skill.py` の `TestSkillCursorPlugin`（7 テスト）のいずれにも、`deploy_skills_plugin` に悪意ある skill 名（`../skills-evil` / `../../evil` 等）を渡すテストが存在しない
- `grep -rn "is_safe_store_name\|not a safe store name\|resolves outside" tests/` → **0 件**
- 参考: zed 版（design 06 C2）には回帰テストあり（`tests/test_zed.py:469-500` `test_deploy_skills_skips_traversal` 等）。cursor-plugin 版は同等テストなし
- 影響: コード上ガードは正しく機能するが、今後のリファクタリングでガードが外れても検出できない。config.json を手編集した際の防衛線（skill add 時の検証をすり抜けた不正名）が無保証

### 🟡 NEW-ISSUE-1 (Major): `_sanitize_plugin_name()` が Cursor 公式スキーマに反する名前を生成する（M1 修正が不完全）

- **場所**: `src/ai_adapter/providers/cursor.py:282-298`
  ```python
  name = re.sub(r"[^a-z0-9._-]+", "-", name)   # ← `_` が許可文字セットに含まれる
  ```
- **実測**（`uv run python` で直接実行）:

  | 入力 | QA チェック項目の期待値 | 実際の出力 | 判定 |
  |------|------------------------|-----------|------|
  | `My_Project` | `my-project` | `my_project` | ❌ アンダースコアが残る（**Cursor スキーマで無効**） |
  | `my project` | `my-project` | `my-project` | ✅ |
  | `proj-` | `proj-0` | `proj` | ❌ 期待値不一致（`proj` 自体はスキーマ上有効だが、レビュー指定の挙動と異なる） |

- **根拠（Cursor 公式スキーマ）**: `cursor/plugins` リポジトリ `schemas/plugin.schema.json` の name パターンは
  `^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$`
  — 許可文字は `a-z` `0-9` `.` `-` のみで、**アンダースコア `_` は不可**。
  したがってプロジェクトディレクトリが `My_Project` の場合、生成される plugin.json の `name: "my_project"` は公式スキーマで無効。Cursor がプラグインを読み込めない恐れがある。
- **自己矛盾**: 同関数の docstring（cursor.py:284-285）は「Cursor requires: lowercase kebab-case (alphanumerics, hyphens, periods)」と明記するが、正規表現は `_` を許可しており docstring と実装が食い違っている
- **`proj-` → `proj-0` 不達の原因**: cursor.py:288-290 の `name.strip("-._")` が末尾の `-` を先に除去するため、下段の `if not name[-1].isalnum(): name = name + "0"`（cursor.py:296-297）は**到達不能なデッドコード**になっている
  ```python
  name = name.strip("-._")          # "proj-" → "proj"（末尾ハイフン除去）
  if not name[0].isalnum():         # strip 後は先頭は必ず alnum → 常に False
      name = "a" + name
  if not name[-1].isalnum():        # strip 後は末尾は必ず alnum → 常に False
      name = name + "0"
  ```

### 🟡 NEW-ISSUE-2 (Major): `_sanitize_plugin_name` の回帰テストが 0 件

- `grep -rn "sanitize" tests/` → **0 件**。QA チェック項目「テストで検証されていること」を満たさない
- レビュー M1 の修正にテストが伴っておらず、NEW-ISSUE-1 のような期待値不一致が検出されていない状態
- 最低限、QA チェック項目の 3 ケース（`My_Project` / `my project` / `proj-`）+ エッジケース（空文字 → `ai-adapter`、`..` → `ai-adapter`、大文字、末尾ハイフン、先頭ハイフン）のユニットテストが必要

## 4. M1 修正の検証（plugin 名サニタイズ） — ❌ FAIL

| 要件 | 検証結果 |
|------|---------|
| `_sanitize_plugin_name()` が lowercase kebab-case に変換 | ❌ lowercase は達成するが kebab-case 未達。アンダースコアを残す（NEW-ISSUE-1） |
| `My_Project` → `my-project` | ❌ 実際は `my_project` |
| `my project` → `my-project` | ✅ |
| `proj-` → `proj-0` | ❌ 実際は `proj`（デッドコードにより `+ "0"` 分岐が不達） |
| テストで検証されていること | ❌ `_sanitize_plugin_name` のテストが 0 件（NEW-ISSUE-2） |

- 影響範囲: `resolve_plugin_root()`（cursor.py:314）と `generate_plugin_manifest()`（cursor.py:325）の両方がこの関数を経由するため、プラグインのディレクトリ名と plugin.json の `name` の両方が不正名になり得る
- 参考: Cursor 公式 scaffold（context7 `/cursor/plugins`）も「Validate plugin name format: lowercase kebab-case, starts and ends with an alphanumeric character」と規定。アンダースコアは有効文字に含まれない

## 5. cursorrules のセマンティクス — ✅ PASS

| 要件 | 検証結果 |
|------|---------|
| `get <name>` は指定 instruction のみ出力 | ✅ `instruction.py:278-282`。`_find_instruction_by_name` で特定した 1 件のみを `_deploy_cursorrules([(src.stem, content)])` に渡す。`tests/test_instruction.py:639-649` `test_get_cursorrules_single_instruction_only` で `# Style` が出力に含まれないことを検証 |
| `get-all` は全 instruction を連結 | ✅ `instruction.py:478-491`。`config.instructions` を反復し `export_cursorrules` が `# --- <name> ---` セパレータで連結。`tests/test_instruction.py:651-661` で両セパレータを検証 |
| `--format cursor` は Exit(2) のまま | ✅ `instruction.py:113-129` `_reject_cursor_format()` が `click.exceptions.Exit(2)` を送出。get / get-all 両方で維持。回帰テスト: `tests/test_instruction.py:691`（get）、`tests/test_cursor.py:514`（get-all）とも通過 |
| frontmatter 除去 | ✅ `cursor.py:236-253` `_strip_frontmatter()`。`tests/test_instruction.py:628-637` で検証 |
| 既存 .cursorrules + force なし → 確認プロンプト | ✅ `instruction.py:193-194`。`tests/test_instruction.py:674-681` で検証 |
| `--scope user` 拒否（project-root のみ） | ✅ `instruction.py:139-140`。`tests/test_instruction.py:683-686` で検証 |

## 6. plugin package の構造 — ✅ PASS

| 要件 | 検証結果 |
|------|---------|
| `~/.cursor/plugins/local/<name>/` に生成 | ✅ `resolve_plugin_root()`（cursor.py:301-315）→ `resolve_scope_path("cursor", "skills", "user", base)` → `config.py:246` `_USER_SCOPE_DIRS[("cursor", "skills")] = ".cursor/plugins/local"` |
| `.cursor-plugin/plugin.json` 生成 | ✅ cursor.py:388-393。`tests/test_cursor.py:388-396` `test_deploy_writes_manifest_and_skill` で検証 |
| `skills/<name>/SKILL.md` + 補助ファイル | ✅ `shutil.copytree` で scripts/ 等もコピー。`tests/test_cursor.py:398-402` で検証 |
| マニフェストが必ず生成される | ✅ skill ループ後に無条件で manifest を書き出し（cursor.py:386-393）。全 skill が skip された場合でも生成される。`tests/test_cursor.py:410-415` `test_deploy_skips_missing_skill_but_writes_manifest` で検証（AC2 満たす） |
| frontmatter 保持（Cursor が直接読むため） | ✅ `tests/test_cursor.py:404-408` で検証（AC3 満たす） |
| 既存 package + force なし → 確認プロンプト | ✅ cursor.py:334-335。`tests/test_cursor.py:417-422` で検証 |
| `skill get`（単数）にも `--format cursor-plugin` | ✅ `tests/test_skill.py:945-961` `test_skill_get_cursor_plugin_package` で検証（AC5 溜たす） |
| `--env` フィルタ | ✅ `tests/test_skill.py:1034-1063` で検証（タスク 07-3 AC2 満たす） |
| `--project-dir` 尊重（plugin 名決定に使用） | ✅ `resolve_plugin_root` が `base.name` を使用。`tests/test_skill.py` の全 CLI テストが `--project-dir` を指定して検証（タスク 07-3 AC3 満たす） |

## 7. `--scope` の再利用 — ✅ PASS（軽微な指摘あり）

| 要件 | 検証結果 |
|------|---------|
| `resolve_scope_path()` を使用 | ✅ 2 箇所で使用、独自パス実装なし |
| | `src/ai_adapter/providers/cursor.py:313` — `resolve_plugin_root()`: `resolve_scope_path("cursor", "skills", "user", base)` |
| | `src/ai_adapter/commands/instruction.py:190` — `_deploy_cursorrules()`: `resolve_scope_path("cursor", "instruction", "project", project_path)` |
| scope matrix への統合 | ✅ `config.py:246` に `("cursor", "skills"): ".cursor/plugins/local"` を追加（design 01 のマトリクスパターンに準拠）。未定義の tool × category 組み合わせは `ValueError` で拒否される |

### 🟢 軽微: `--scope` フラグと実配置先の意味的不整合

- `deploy_skills_plugin()` の docstring（cursor.py:312-313, 339-340）は「The destination is always user-scope regardless of `--scope`」と明記し、実装も user 固定（`resolve_scope_path(..., "user", ...)`）
- しかし `skill get-all --format cursor-plugin --scope user` は `validate_claude_scope()`（`src/ai_adapter/providers/claude.py:29-46`）に弾かれエラーになる。同関数の docstring は「cursor-plugin 等は固定 project-scope 所持」と仮定しているが、実際の配置先は user scope（`~/.cursor/plugins/local/`）であり仮定が崩れている
- 結果: `--scope project`（デフォルト）で user scope へ配置される（フラグ無視）、`--scope user`（意味的には正しい値）は拒否される。機能は壊れないが UX の混乱要因
- 提案: `validate_claude_scope` の対象外リストに `cursor-plugin` を追加するか、フラグ無視である旨を README / help に明記

---

## 発見事項サマリ

| 優先度 | ID | 内容 | 状態 |
|--------|----|------|------|
| 🔴 高 | NEW-ISSUE-1 | `_sanitize_plugin_name` がアンダースコアを許可し Cursor 公式スキーマ（`^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$`）に反する名前を生成。`My_Project` → `my_project`（期待 `my-project`）、`proj-` → `proj`（期待 `proj-0`、`+ "0"` 分岐はデッドコード） | 未修正 |
| 🔴 高 | NEW-ISSUE-2 | `_sanitize_plugin_name` の回帰テストが 0 件。QA チェック項目「テストで検証されていること」を満たさない | 未修正 |
| 🟡 中 | C1-GAP | `deploy_skills_plugin` のパストラバーサル回帰テストが不在（コードガード自体は正しく実装済み。zed 版には同等テストあり） | 未修正 |
| 🟢 低 | SCOPE-1 | `validate_claude_scope` が cursor-plugin の `--scope user` を拒否するが実配置先は user scope。フラグと実態の不整合 | 検討 |
| 🟢 低 | DOC-1 | 設計書 07 に「タスク 07-3」が 2 つ存在し、後者が stale（`./skills/<name>/` へのコピーと記載。実装は正しい plugin package 生成に従っている） | 設計書側 |
| 🟢 低 | CCN-1 | `instruction_remove` の CCN 18 が閾値 20 に接近（設計 08 QA と同一指摘） | 検討 |

## 総合判定: **不合格（要修正）**

- 項目 1（テスト 995 件）、項目 2（ruff/lizard）、項目 5（cursorrules セマンティクス）、項目 6（plugin package 構造）、項目 7（`resolve_scope_path` 再利用）は PASS。実装の骨格は設計書 07 の仕様に沿っており、機能面は概ね完成している
- しかしレビュー M1「plugin 名サニタイズ」は**修正済みと報告されたが実際は不完全**: 期待値 3 ケース中 2 ケースが不一致（NEW-ISSUE-1）、かつ回帰テストが 0 件（NEW-ISSUE-2）。Cursor 公式スキーマに反する名前が生成される状態は、プラグインが Cursor に読み込まれないという実害に直結し得る
- C1（パストラバーサル）はコード修正自体は正しいが、回帰テストが欠落しており回帰防止の担保がない

## 推奨アクション

1. **【必須】NEW-ISSUE-1 の修正**: `_sanitize_plugin_name` を以下のように修正し、Cursor 公式スキーマ `^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$` に準拠させる
   - アンダースコアを許可文字セットから外す（`[^a-z0-9.-]+` に変更）または明示的に `name.replace("_", "-")` を実施 → `My_Project` → `my-project`
   - `proj-` → `proj-0` を実現するには、末尾の `-._` を `strip` する前に `isalnum` チェックを行って `+ "0"` を適用する。例:
     ```python
     name = re.sub(r"[^a-z0-9.-]+", "-", name)   # アンダースコア除去
     name = re.sub(r"-{2,}", "-", name)
     name = name.lstrip("-._")                    # 先頭のみ strip
     if not name:
         name = "ai-adapter"
     if not name[-1].isalnum():
         name = name + "0"                        # "proj-" → "proj-0"
     ```
   - 修正後、docstring（「alphanumerics, hyphens, periods」）と実装の整合も確認
2. **【必須】NEW-ISSUE-2 の解消**: `_sanitize_plugin_name` のユニットテストを追加（QA チェック項目の 3 ケース + 空文字/`..`/大文字/先頭末尾ハイフンのエッジケース）。あわせて `tests/test_config.py` に `is_safe_store_name` の直接テストも検討
3. **【必須】C1-GAP の解消**: `tests/test_cursor.py` に `deploy_skills_plugin` のパストラバーサル回帰テストを追加。`tests/test_zed.py:469-500` の模式を踏襲し、`Skill(name="../../evil")` 等を直接渡して「skip メッセージ出力」「dest 外へコピーされない」「decoy ファイルが無傷」を検証する
4. **【推奨】SCOPE-1 の整理**: `validate_claude_scope` の許可リストに `cursor-plugin` を追加するか、`--scope` が cursor-plugin では無視される旨を README / `skill get --help` に明記
5. **【推奨】DOC-1 の修正**: 設計書 07 の重複した「タスク 07-3」（stale な `./skills/<name>/` 記載）を削除
6. **【推奨】CCN-1**: `instruction_remove`（CCN 18）のリファクタリングを検討（設計 08 QA と同一指摘）

修正後、`bash scripts/run_tests.sh` / `ruff` / `lizard` の再実行と、NEW-ISSUE-1/2・C1-GAP の回帰確認をもって再 QA が必要。
