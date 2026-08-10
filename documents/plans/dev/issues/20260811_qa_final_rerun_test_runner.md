# QA 最終再検証: run_tests.sh pytest 化修正の検証結果

## 優先度
🔴 高（1件） / 🟡 中（1件） / 🟢 低（3件） — **差し戻し**

## 対象
- 計画書: `README.md`（Running Tests セクション）
- 関連ファイル: `scripts/run_tests.sh`, `.github/workflows/ci.yml`, `.githooks/pre-commit`, `tests/conftest.py`, `README.md`

## 検証結果サマリ

### ✅ 確認済み（問題なし）

| # | チェック項目 | 結果 |
|---|------------|------|
| 1 | `bash scripts/run_tests.sh`（フル） | **337 passed**、汚染なし |
| 2 | `uv run pytest -q`（素の pytest） | **337 passed**、汚染なし |
| 3 | `bash scripts/run_tests.sh tests/test_env.py`（単一ファイル） | **14 passed**、汚染なし |
| 4 | `bash scripts/run_tests.sh tests/test_env.py -k add`（キーワード） | **2 passed / 12 deselected**、汚染なし |
| 5 | `zsh .githooks/pre-commit`（フック経由） | format / lint / **337 passed** / CCN すべて通過 |
| - | 実行前後で `.github/workflows/`・`.gitignore` の sha256 不変 | ✅ 全経路後に一致 |
| - | `grep -c "^/.testbox" .gitignore` | **0**（冗長エントリ復活なし） |
| - | `bash -n scripts/run_tests.sh` / `zsh -n .githooks/pre-commit` | ✅ 両方パス |
| - | `uv run ruff check .` | ✅ All checks passed |
| - | ROOT ガード（run_tests.sh L36） | ✅ 存在・機能 |
| - | PYTHONPATH 依存 | ✅ なし（`ai_adapter.*` は editable install で解決） |
| - | 並列実行競合（manifest） | ✅ pytest-xdist は pyproject/uv.lock に存在しない（revert 済み） |

**根本修正の目的（リポジトリ非汚染）は全経路で達成されている。**

---

## 発見項目

### 🔴 1. `run_tests.sh` のデフォルト対象追加が pytest フラグで無効化される（CI 直撃）

#### 対象
- `scripts/run_tests.sh` L62-64
- `.github/workflows/ci.yml` L42 → `run: bash scripts/run_tests.sh -v`
- `README.md` L726 / スクリプトヘッダ L24（`-v` を「full suite, verbose」として記載）

#### 指摘事項
フラグ付き実行でテストが 1 件も実行されない。

```bash
$ bash scripts/run_tests.sh -v; echo $?
# → 0 items / no tests ran, EXIT 5
```

**原因**: default 追加ロジックが「引数配列が完全に空か」で判定している。

```bash
if [[ ${#args[@]} -eq 0 ]]; then
    args+=("$ROOT/tests")
fi
```

`-v` は `tests/*` にも `tests\.*` にも一致しないため `args` に残り、配列が空でなくなり `$ROOT/tests` が追加されない。結果、cwd（`.testbox/` = 空）から pytest が実行され `exit 5`（no tests collected）。

**影響**: `.github/workflows/ci.yml` L42 が `bash scripts/run_tests.sh -v` を実行するため、**CI のテストステップが exit 5 で失敗する**。README L726・スクリプトヘッダ L24 の記載とも不一致。

（参考: 同一コマンドを直接実行した場合は `-v /repo/tests` となり 337 passed / exit 0 を確認）

#### 改善案
「path ターゲットが指定されたか」で判定し、フラグのみの場合はデフォルトを追加する:

```bash
target_given=0
for a in "$@"; do
    if [[ $a == tests/* || $a == tests\.* ]]; then
        target_given=1
        args+=("$ROOT/$a")
    else
        args+=("$a")
    fi
done
if [[ $target_given -eq 0 ]]; then
    args+=("$ROOT/tests")
fi
```

これで `-v`・`--tb=short`・`-k add`（ファイルなし）等のフラグ併用時もフルスイートが実行される。

---

### 🟡 2. ドット形式モジュール指定 `tests.test_env` が exit 4 で失敗（README の「module」表記と不一致）

#### 対象
- `scripts/run_tests.sh` L54（`tests\.*` 正規化）
- `README.md` L729「Single test file / module」

#### 指摘事項
```bash
$ bash scripts/run_tests.sh tests.test_env; echo $?
# → ERROR: file or directory not found: <ROOT>/tests.test_env, EXIT 4
```

`tests\.*` ブランチが `$ROOT/tests.test_env`（実在しないパス）を生成するため pytest が収集エラーになる。README の「module」表記は実動作で成立していない。

#### 改善案
- ドット形式をファイルパスに変換: `tests.test_env` → `$ROOT/tests/test_env.py`（ドットを `/` に置換 + `.py` 付与）
- またはドット形式のサポートをやめ、README から「module」の語を削除する

---

### 🟢 3. pytest-xdist 3.8.0 / execnet が .venv に残存（未管理の stale パッケージ）

#### 対象
- `.venv/lib/python3.10/site-packages/`（`pytest_xdist-3.8.0.dist-info`）
- 確認: `uv sync --dry-run` → `Would uninstall 2 packages: execnet, pytest-xdist`

#### 指摘事項
revert コミット（843c59f）で manifest からは除去済みだが、現行 .venv には残っており pytest 起動時に `plugins: xdist-3.8.0` と表示される。環境によっては `pytest -n auto` で並列実行が可能な状態（前回指摘の競合リスクがこの環境だけ残存）。ただし manifest・lock が正しいため、新規環境や CI では再現しない。

#### 改善案
`uv sync` を実行して stale パッケージを除去する（恒久修正は不要）。

---

### 🟢 4. ドキュメントの残存「unittest」表記

#### 対象
- `README.md` L810（Tech Stack テーブル）: `Testing | unittest (standard library)`
- `.github/workflows/ci.yml` ステップ名: `Test with unittest (sandboxed)`

#### 指摘事項
実行基盤が pytest に移行したため、残存する「unittest」表記は実態と不一致（動作には影響なし）。

#### 改善案
- README: `Testing | pytest (sandboxed via scripts/run_tests.sh into .testbox/)`
- ci.yml: ステップ名を `Test with pytest (sandboxed)` に変更

---

## 備考
- 前回 🟡 指摘の「冗長エントリ30個追加」の根本原因（unittest × conftest 非適用）は修正済み。全 5 経路で `.gitignore` 汚染ゼロを sha256 比較 + `grep -c "^/.testbox"` = 0 で確認。
- 上記 🔴 は修正ロジック（default-target 判定）と ci.yml の呼び出し方にのみ起因。`add_to_gitignore` / conftest の cwd 隔離そのものには問題なし。