# QA: 設計書 03 実装（Codex native paths）

- 日付: 2026-10-06
- チェッカー: QA
- 対象: `documents/plans/dev/20261006_design_03_codex_native_paths.md` 対応実装
  （providers/codex.py / commands/mcp.py / commands/skill.py / scan.py / doctor.py / tests）
- 前提: コードレビュー済み（Critical C1: tomli 依存、C2: inline table/dotted key 検出、M4: TOML 検証を修正済みと報告）、
  実装者は 761 テスト通過を報告
- 総合判定: **合格（条件付き）** — W1（M4 失敗パスの非破壊テスト欠落）・W2（N1 の doctor テスト欠落）を条件とする

---

## 1. テスト実行の独立検証 — ✅ PASS

`bash scripts/run_tests.sh` を独立実行:

- **761 passed in 3.81s**（実装者の報告と一致）
- `tests/test_codex.py` の新規 TOML マージテスト **8 件** を個別実行で確認・通過
  （`TestCodexTOMLMerge` クラス）:
  - `test_merge_preserves_comments_and_key_order`
  - `test_merge_creates_bak_backup`
  - `test_merge_refuses_inline_table_form`
  - `test_merge_refuses_dotted_key_form`
  - `test_merge_output_is_valid_toml`
  - `test_merge_preserves_unmanaged_servers`
  - `test_merge_does_not_touch_auth_json`
  - `test_scan_never_reports_auth_json`

## 2. コード品質 — ✅ PASS

| コマンド | 結果 |
|---|---|
| `uv run ruff format --check .` | ✅ PASS（74 files already formatted） |
| `uv run ruff check .` | ✅ PASS（All checks passed!） |
| `uv run lizard src/ai_adapter/providers/codex.py src/ai_adapter/commands/mcp.py src/ai_adapter/commands/skill.py -C 20` | ✅ PASS（閾値超過なし。最大 CCN は skill.py `install_skill_core` の 14） |

## 3. C1 修正の検証（tomli 依存） — ✅ PASS

| 検証項目 | 実装 | 結果 |
|---|---|---|
| `pyproject.toml` dependencies に `"tomli>=2.0; python_full_version < '3.11'"` | `pyproject.toml:15` — regular dependency（extras から昇格、marker で 3.11+ では不要） | ✅ |
| `codex.py` の tomllib フォールバック | `codex.py:23-28` — `try: import tomllib / except ModuleNotFoundError: import tomli as tomllib` | ✅ |
| Python 3.10 環境でフォールバックが実際に動作 | 実行環境が Python 3.10.4（`tomllib` なし）で `tomli 2.4.1` がインストール済み。761 テストすべてが tomli 経由で通過（`tests/test_codex.py:265-266` も同じフォールバックを使用） | ✅ |

補足: 設計書 350 行は `except ImportError` と記載、実装は `except ModuleNotFoundError`。
`ModuleNotFoundError` は `ImportError` のサブクラスのため動作は同等、実装の方が意図的に狭い例外に絞っており問題なし。

## 4. C2/M4 修正の検証（TOML 安全性） — ✅ PASS（ただし W1 あり）

### 4-1. C2: inline table / dotted key 検出 — ✅

`src/ai_adapter/providers/codex.py:230-253` `_has_non_table_mcp_servers()`:

- inline table: `re.match(r"^mcp_servers\s*=", stripped)` で `mcp_servers = { … }` を検出
- dotted key: `re.match(r"^mcp_servers\.", stripped)` で `mcp_servers.foo = …` を検出
- `_splice_mcp_servers()`（276-281 行）で検出時に `ValueError` raise
- `merge_into_config_toml()`（366-368 行）で `ValueError` → `click.ClickException` に変換しエラー終了
- テスト `test_merge_refuses_inline_table_form` / `test_merge_refuses_dotted_key_form` で担保

### 4-2. M4: 書き出し前 tomllib 検証 — ✅（実装のみ）

`src/ai_adapter/providers/codex.py:370-376`:

```python
try:
    tomllib.loads(new_text)          # 書き出し前に検証
except tomllib.TOMLDecodeError as exc:
    raise click.ClickException(...)  # エラー終了
path.write_text(new_text, ...)       # 検証成功時のみ書き出し
```

`write_text` が検証の**後**にあるため、実装上は検証失敗時に元ファイル非破壊。

⚠️ **W1（🟡）**: 検証失敗時に `ClickException` が投げられ、元ファイルが書き換わらないことを
**直接検証するテストが存在しない**。
`test_merge_output_is_valid_toml`（成功パス）は tomllib で再パースできることのみ検証しており、
失敗パス（無効な splice 結果 → 非破壊）のテストが欠落。
Claude 側の設計 02 で `test_corrupt_json_aborts_merge` が「File must NOT be overwritten.」を
明示検証しているのと比較して担保が弱い。

## 5. M1/M2 テストカバレッジ — ✅ PASS（ただし W2 あり）

| カバレッジ項目 | テスト | 結果 |
|---|---|---|
| TOML マージ時のコメント・キー順保持 | `tests/test_codex.py:211` `test_merge_preserves_comments_and_key_order` | ✅ |
| `.bak` バックアップ | `tests/test_codex.py:232` `test_merge_creates_bak_backup` | ✅ |
| auth.json 非アクセステスト（mtime 検証含む） | `tests/test_codex.py:283` `test_merge_does_not_touch_auth_json` — `st_mtime_ns` 比較で書き換えなしを検証 | ✅ |
| scan の auth.json 除外 | `tests/test_codex.py:298` `test_scan_never_reports_auth_json` + `tests/test_scan.py:198` `test_scan_codex_auth_json_excluded` | ✅ |

⚠️ **W2（🟡）**: N1 修正（home==project 時の二重検証回避）の**テストが欠落**。
`tests/test_doctor.py` に codex config.toml を扱うテストが 0 件
（`pytest tests/test_doctor.py -k codex` → 25 deselected）。

## 6. N1 修正の検証 — ⚠️ WARNING（W2）

`src/ai_adapter/doctor.py:195-215` `_codex_config_toml_issues()`:

```python
project_config = project_dir / ".codex" / "config.toml"
if project_config.resolve() != (home / ".codex" / "config.toml").resolve():
    targets.append(...)   # home==project 時はスキップ → 二重検証なし
```

実装は正しい（`resolve()` で正規化して比較）。
ただし `tests/test_doctor.py` に該当ケースのテストがなく、
N1 の回帰が検出されない状態。

## 7. セキュリティ — ✅ PASS

| 検証項目 | 結果 |
|---|---|
| `codex.py` で auth.json への read/write がない | ✅ `codex.py` 内の `auth.json` 参照はコメント/docstring（348 行）のみ。`read_text`/`write_text` は `config.toml` / `AGENTS.md` / スキルファイルのみ |
| `doctor.py` で auth.json を開かない | ✅ `_codex_config_toml_issues` は `config.toml` のみ検証。189 行コメント「auth.json is never opened」 |
| `scan.py` の auth.json 除外 | ✅ `SCAN_IGNORE_PATTERNS` に `.codex/auth.json`（38 行）+ `_GENERIC_SECRET_COMPONENTS` に `"auth"`（85 行）で二重ガード |
| テストで非アクセス担保 | ✅ `test_merge_does_not_touch_auth_json`（mtime 検証）+ `test_scan_codex_auth_json_excluded` + `test_scan.py:499-501`（`is_ignored` 直接検証） |

## その他の発見

### 🟢 W3: codex.py docstring の記述が C1 修正前後で不整合

`src/ai_adapter/providers/codex.py:24`:

```python
# tomli package (install via ``pip install 'ai-adapter[py310]'``).
```

C1 修正により `tomli` は **regular dependency** に移行済み（`pyproject.toml:15`）。
docstring の「py310 extras 経由でインストール」という説明は古いままで、
実態と異なる。修正は 1 行のドキュメント更新のみ。

### 🟢 W4: 設計書のチェックボックスが未更新

`documents/plans/dev/20261006_design_03_codex_native_paths.md:357-365` の
実装チェックリスト（8 項目）がすべて `[ ]`（未完了）のまま。
QA で確認した範囲では実装・テストとも完了しており、
ドキュメント更新の漏れと判断（QA 対象は実装コード、ドキュメント更新は別作業）。

---

## 総合判定: **合格（条件付き）**

全 761 テストが独立実行で通過し、C1/C2/M4 の修正実装はコード・テストの両面で確認。
セキュリティ（auth.json 非アクセス）もコード・テスト両面で担保されている。

**条件**: W1（M4 失敗パスの非破壊テスト）と W2（N1 の doctor テスト）を追加すること。

## 推奨アクション

| 優先度 | 項目 | 内容 |
|---|---|---|
| 🟡 中 | W1 | `tests/test_codex.py` に「無効な splice 結果 → `ClickException` → 元ファイル非破壊」のテストを追加（例: `_splice_mcp_servers` をモックして `TOMLDecodeError` 相当を発生させ、元 `config.toml` の内容が変更されないことをアサート） |
| 🟡 中 | W2 | `tests/test_doctor.py` に `_codex_config_toml_issues` のテストを追加（home==project 時に issue が 1 件のみ生成されること、無効な TOML で warning が付くこと） |
| 🟢 低 | W3 | `codex.py:24` の docstring を「tomli は regular dependency（Python 3.10 用）」に更新 |
| 🟢 低 | W4 | 設計書のチェックリストを実装・QA 完了状態に更新 |
