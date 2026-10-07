# Runtime Monitor 設計書レビュー: normalizer.py の責務分担が未定義（discover() 契約との関係が不明）

## 優先度
🟡 Major

## 対象
- 計画書: `documents/plans/dev/20261007_runtime_monitor_design.md`（§2.2 line 55 / §3 `discover() -> list[RuntimeSession]` / §13 line 507）
- 上位仕様書: `documents/plans/user/AI Adapter Runtime Monitor.md`（§8 Canonical Model / §12 Runtime Architecture / §13 Providers vs Runtime Adapters）

## 指摘事項
1. **契約とファイルの役割が噛み合わない:** ABC 契約（§3）では `discover()` がすでに `list[RuntimeSession]`（Canonical Model）を返す。つまり raw → canonical 変換は adapter 内で行われるはずなのに、`runtime/normalizer.py`（「raw → canonical 変換」）が別ファイルとして計画されている。normalizer が何を正規化するのか（raw 型が adapter 外に出てこない以上）設計書に記述がない。
2. **曖昧さのまま実装すると2つの失敗パターンがある:**
   - (a) normalizer がデッドコード化する
   - (b) status / confidence の正規化表が adapter ごとに 3 重複製される（§2.5 Confidence 表、§2.4 Status 表がコピペされ、後から表を揃え直すのが効かなくなる）
3. §8 の必須テストに「Status Normalization」があるが、そのテスト対象（normalizer.py か、各 adapter か）が §13 のテストファイル（test_runtime_models.py / test_runtime_adapters.py / test_monitor_cli.py）のどこに対応するのかも未記述。

## 改善案
設計書に責務分担を明記する（推奨案）:

- **Adapter（`adapters/*.py`）**: Host 固有 raw データの取得と、その raw → `RuntimeSession` マッピング。Host 差分はここに閉じる（§3「Host 差分を Core へ漏らさない」の解釈として自然）。
- **`normalizer.py`**: 3 アダプタ共通の正規化語彙とヘルパーの**単一情報源**:
  - status 値定数（`working` / `waiting` / `blocked` / `done` / `idle` / `unknown`）
  - confidence マッピング（§2.5 の Source → Confidence 表の実体）
  - イベント名定数（§5 — issue 06 の帰結に依存）
  - datetime パースヘルパー、`runtime_session_to_dict()`（JSON シリアライザ = §6.3 契約の実体）
- 各 adapter は normalizer の定数 / ヘルパーを import して使用し、§2.4 / §2.5 の表を adapter 内にコピーしない
- §8 の「Status Normalization」テストの対象ファイルを §13 で明示する（新規 `tests/test_runtime_normalizer.py` を追加、または既存 3 ファイルのどれかに含めると明記）

## 備考
上位仕様 §12 と設計書 §13 の双方が normalizer.py を列挙しているため、ファイル自体は維持しつつ役割を確定させるのが差分最小。issue 03（JSON シリアライズ契約）と対にして `runtime_session_to_dict()` を normalizer に置けば、シリアライズの実装が 1 箇所に集約される。
