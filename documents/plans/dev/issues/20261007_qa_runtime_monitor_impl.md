# QA レポート: Runtime Monitor 実装品質チェック

- 日付: 2026-10-07
- 対象: Runtime Monitor 実装（`src/ai_adapter/runtime/` + `src/ai_adapter/commands/monitor.py`）
- 設計書: `documents/plans/dev/20261007_runtime_monitor_design.md`
- 実行環境: macOS / Python 3.10.4 / pytest 9.1.1
- 総合判定: **合格**

## 1. テスト実行の独立検証 — ✅ PASS

`bash scripts/run_tests.sh` を実行し、**1108 passed, 1 warning** を独立確認。
実装者の報告（既存 1003 + 新規 105 = 1108）と一致。

- 新規テスト内訳: `test_runtime_models.py` 34 + `test_runtime_adapters.py` 51 + `test_monitor_cli.py` 20 = 105 ✅
- warning は `tests/test_codex.py:326` の `TOMLDecodeError` DeprecationWarning（本機能と無関係、既存問題）。

## 2. コード品質 — ✅ PASS

| チェック | 結果 |
|----------|------|
| `uv run ruff format --check .` | ✅ 92 files already formatted |
| `uv run ruff check .` | ✅ All checks passed! |
| `uv run lizard ... -C 20` | ✅ No thresholds exceeded |

- 最大 CCN は `orca.py::_merge_sessions`（CCN 15）、閾値 20 未満。
- セキュリティスキャン: `runtime/` 配下にハードコードされた認証情報なし。
- 旧ワークスペースパス（`06_openclaw` 等）の残存なし。

## 3. Canonical Model 検証 — ✅ PASS

`src/ai_adapter/runtime/models.py`:

- `RuntimeStatus(str, Enum)` / `RuntimeConfidence(str, Enum)` / `RuntimeSource(str, Enum)` で定義 ✅
- 値は全て小文字（`working` / `high` / `cli` 等）✅
- シリアライザ `normalizer.py::runtime_session_to_dict` は `.value` を使用し JSON が lowercase ✅
- datetime は `.isoformat()` で ISO 8601。`epoch_millis_to_datetime` が aware UTC を返すため tz 保持 ✅
- テスト `test_iso8601_datetimes` が `+00:00` を検証 ✅

## 4. Adapter Contract 検証 — ✅ PASS

`runtime/adapters/base.py::RuntimeAdapter`（ABC）:

- メソッドは `discover` / `inspect` / `capabilities` / `host_name`(property) / `is_available` のみ。**書き込みメソッドなし（Read Only）** ✅
- `is_available()` が ABC に定義され、全 3 アダプタが実装 ✅
- `discover()` は各アダプタで `try/except Exception → []`、registry の `_safe_discover` でも二重に例外分離 ✅
- テスト `test_discover_never_raises_on_internal_exception`（3 アダプタ分）+ `test_discover_sessions_merges_and_isolates_failures` で検証 ✅

## 5. サブプロセス安全 — ✅ PASS

`base.py::run_host_command` が唯一のサブプロセスゲートウェイ:

- list 引数（例 `["orca", "terminal", "list", "--json"]`）✅
- `shell=False` を明示指定 ✅
- `timeout` 必須（デフォルト 10.0s / `ps` は 5.0s。全呼び出し経路で渡される）✅
- `src/ai_adapter/runtime/` 内に `shell=True` は存在しない ✅
- `subprocess` の import は `base.py` のみ（ゲートウェイ経由）✅
- テスト `test_uses_list_argv_and_no_shell` が `shell=False` を含む呼び出し引数を完全一致で検証 ✅
- タイムアウト / バイナリ不在 / OSError は例外ではなく `CommandResult.error` で報告 ✅

## 6. 並行実行・例外分離 — ✅ PASS

`registry.py`:

- `concurrent.futures.ThreadPoolExecutor` + `as_completed` で 3 ホストを並行 discovery ✅
- `_safe_discover` がアダプタ単位で例外を捕捉（1 アダプタ故障で全体をクラッシュさせない）✅
- `create_adapters` はコンストラクタ / `is_available()` 例外も分離 ✅
- テスト: `_FakeAdapter(explode=True)` でも他ホストのセッションが揃うことを検証 ✅

## 7. P2 導出規則 — ✅ PASS

`normalizer.py::derive_activity_state`:

- `ACTIVE_STATUSES = {WORKING, WAITING, BLOCKED}` ✅
- `INACTIVE_STATUSES = {IDLE, DONE}` ✅
- それ以外（UNKNOWN）は `"unknown"` ✅
- 小文字でシリアライズ、表表示は `.upper()` ✅
- テストが 6 ステータス全てを網羅 ✅

## 8. Host 未インストール — ✅ PASS

- ファイル: `tests/fixtures/runtime/`（`orca_terminal_list.json` / `orca_worktree_ps.json` / `vscode_ps.txt` / `zed_ps.txt`）✅
- `shutil.which` / `observe_processes` を mock し、ホスト不在でもスイートが失敗しない設計 ✅
- 統合テスト `test_no_hosts_installed_json` / `_plain_table` が exit 0 と空出力を検証 ✅

## 9. providers/ との分離 — ✅ PASS

- `runtime/` 配下に設定変換コードの混入なし（grep で `providers` 参照は docstring の区別説明のみ）✅
- `providers/` 配下に runtime 監視コードの混入なし ✅
- 各 adapter docstring に「Distinct from `ai_adapter.providers.*`（Configuration Plane）」と明記 ✅

---

## 発見事項（チェック外・補足）

### 🟡 WARNING 1: `watcher.py` / `--watch` / `--capabilities` / `--debug` が未実装

- 設計書 §2.2 / §13 は `src/ai_adapter/runtime/watcher.py` を変更対象ファイルとして列挙し、§6.2 / Phase P5 は `--watch`（3 秒周期・Ctrl+C 最終スナップショット）と `--capabilities` / `--debug` を規定。
- 実装には `watcher.py` が存在せず、`monitor.py` のオプションは `--json` のみ。
- **推奨アクション**: 実装スコープが P0–P4 で P5 を意図的に延期したなら、設計書に延期を明記して §13 の対象ファイル一覧を更新する。P5 も今回の依頼範囲なら別途実装タスク化する。

### 🟢 LOW 2: `needs_user` が全アダプタで常に `None`

- P4（Human Attention）未実装。Orca の capabilities は `needs_user="UNKNOWN"` と正直に宣言しており、矛盾はない（Phased な設計と整合）。PoC Report で「未観測」と記録すれば良い。

### 🟢 LOW 3: `runtime_session_to_dict` が naive datetime を防御的に変換しない

- `.isoformat()` を直接呼ぶため、外部連携側が tz なし datetime を `RuntimeSession` に渡すと tz なしで出力される。アダプタ経路は全て aware UTC なため現状リスクは低い（`_format_age` は naive を防御処理している点と非対称）。
- **改善案**: シリアライザ側で `if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)` を適用し、Renderer と同じ防御に揃える。

### 🟢 LOW 4: VS Code / Zed の `is_available()` が `ps` を毎回実行

- 一発実行モードでは問題ないが、P5 の watch モード実装時は設計 §6.2「availability チェック結果はサイクル内キャッシュ」を満たす必要がある。

### 🟢 LOW 5: 設計書 §7 の P0 サンプルデータに内部不整合

- §7 のサンプルは `source="orca-cli"` / `confidence="low"` だが、§2.3 の正規語彙に `orca-cli` は存在せず、§2.5 は Official CLI → HIGH とする。実装は §2.3 / §2.5 に従い `source=cli` / `confidence=high` で正しい。
- **推奨アクション**: 設計書側のサンプルを修正する（実装修正は不要）。

## 推奨アクション（優先度順）

1. 🟡 設計書へ P5（watch / capabilities / debug）の延期範囲を明記、または実装タスクを起票する。
2. 🟢 `runtime_session_to_dict` に naive datetime の防御を入れる（`_format_age` と揃える）。
3. 🟢 設計書 §7 のサンプルデータ（`source="orca-cli"`）を正規語彙に修正する。
4. 🟢 P5 実装時に `is_available()` のサイクル内キャッシュ要件を再確認する。
5. 🟢 `_merge_sessions`（CCN 15）は現状問題なし。将来フィールドが増える場合は分割を検討する。

## 結論

指定された QA チェック項目 9 件は**全て PASS**。テスト 1108 件の独立検証、コード品質ツール 3 種、Canonical Model / Adapter 契約 / サブプロセス安全 / 並行実行と例外分離 / P2 導出規則 / フィクスチャ依存 / レイヤ分離はいずれも設計書どおりに担保されている。発見事項は実装欠陥ではなく、スコープ明示（P5）と防御的ハードニング（naive datetime）の改善提案である。
