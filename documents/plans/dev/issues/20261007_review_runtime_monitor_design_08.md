# Runtime Monitor 設計書レビュー: テスト計画の穴（capabilities / debug / watch / registry 未カバー、normalizer のテストファイル不在）

## 優先度
🟢 Minor

## 対象
- 計画書: `documents/plans/dev/20261007_runtime_monitor_design.md`（§8 lines 418-445 / §13 lines 492-520）
- 上位仕様書: `documents/plans/user/AI Adapter Runtime Monitor.md`（§30 Testing）
- 関連ファイル: `scripts/run_tests.sh`（サンドボックス実行）、`tests/conftest.py`（pytest chdir プラグイン）、`pyproject.toml`（pytest testpaths）

## 指摘事項
1. **網羅性の所見（良い点）:** §8 必須テスト表は上位仕様 §30 の必須項目（Canonical Model / Status Normalization / Adapter Interface / 3 ホスト raw→canonical / UNKNOWN fallback / JSON output）を過不足なくカバーしており、「Host 未インストール」テストの追加も上位仕様より一歩踏み込んでいる。`scripts/run_tests.sh` 経由という方針も本リポジトリの規約どおり。
2. **P5 成果物へのテスト不足:** 設計書自身が課す成果物のうち `--capabilities` 出力、`--debug` 出力、watch レンダラ、registry の可用性 / 例外分離に対応するテストがない。
3. **normalizer のテスト先が不在:** §13 のテストファイルは `test_runtime_models.py` / `test_runtime_adapters.py` / `test_monitor_cli.py` の 3 つだが、§8 に挙がる「Status Normalization」を `normalizer.py` に紐づける先（`tests/test_runtime_normalizer.py`、または既存ファイルのどれかに含めることの明記）がない。
4. **モック境界の明文化:** 「Host がインストールされていない環境でも test suite が失敗しない」は mock 方針で満たせるが、「単体テストから実 Host CLI（orca / code / zed）を呼ばない。adapter 境界で mock / fixture raw data を注入する」ことを明文化すると CI 再現性が安定する。`scripts/run_tests.sh` はサンドボックス実行（`.testbox/`）で本番ファイルを触らない仕組みであり、monitor テストもこの前提に従う必要がある。

## 改善案
1. §8 表に 4 行追加: Capability output（fixture adapter → テーブル / JSON 値の検証）、Debug output（判定根拠行の決定的検証）、Watch render（純粋関数の単体テスト、実 sleep なし）、Registry availability / isolation（1 アダプタが例外を投げても他が列挙される）。
2. §13 に `tests/test_runtime_normalizer.py`（または対応先の明記）を追加。
3. テスト方針に「単体テストから実 Host CLI を呼ばない。adapter 境界で mock / fixture raw data を注入する」と明記。
4. フラグ併用時の usage error テスト（`--watch --json` 等）を `test_monitor_cli.py` の対象に含める。

## 備考
既存テストの命名規則（`tests/test_cli.py` / `test_scan.py` 等の flat ファイル）に `test_runtime_*.py` / `test_monitor_cli.py` は整合し、pytest 設定（`[tool.pytest.ini_options] testpaths = ["tests"]`）にもそのまま収まる。CLI テストは既存 `tests/test_cli.py` の `CliRunner` パターンを踏襲すればよい。
