# Runtime Monitor 設計書レビュー: --watch モードの更新周期・ポーリング戦略・終了処理が未設計

## 優先度
🟡 Major

## 対象
- 計画書: `documents/plans/dev/20261007_runtime_monitor_design.md`（§6.2 lines 266-276 / §7 P5 / §9 依存ポリシー）
- 上位仕様書: `documents/plans/user/AI Adapter Runtime Monitor.md`（§21 Watch Mode / §27 Dependency Policy）
- 関連ファイル: `src/ai_adapter/runtime/watcher.py`（未作成）

## 指摘事項
1. **1–3 秒周期の現実的検証が設計書にない。** 「更新周期: 1–3 秒」「標準ライブラリで実現」とはあるが、既定周期（1 秒か 3 秒か）、1 サイクルで何をどこまで実行するか、Host ごとのポーリングコスト予算が未設計。
2. **実地確認によるコスト問題:** Orca の discovery は複数の CLI サブプロセス起動を要する（例 `orca terminal list --json` は Electron アプリ側 IPC 経由で数十〜数百 ms 級）。1 秒周期 × 全 discovery コマンド全量実行は非現実的。VS Code / Zed はファイルメタデータ監視になり、コスト構造が大きく異なることも設計書に書かれていない。
3. **実装方法が明確か — ではない。** 「TUI Framework 導入は PoC では不要（標準ライブラリで実現）」とあるが、`click.clear()` + `time.sleep` + 再描画ループという既定解が設計書に書かれていない。
4. **終了処理・フラグ併用が未定義:** Ctrl+C 時の挙動（画面復帰、最終スナップショット表示）、`--watch` と `--json` / `--capabilities` / `--debug` の併用規則（併用契約自体は issue 03 と対）。

## 改善案
§6.2 に実装契約を追記する:

- **実装方式:** `while True: sessions = collect(); _render_table(sessions); time.sleep(interval)` + `click.clear()` + `shutil.get_terminal_size()`（幅合わせ）。TUI フレームワーク不使用（§9 どおり）。
- **既定周期: 3 秒。** 1 秒周期は semantic event ソース（issue 06 案 A）が有効な場合のみ。
- **1 サイクルのコスト予算:** Host ごとに discovery コマンドを最小化。Orca は `orca terminal list --json` を主経路とし（agentIdentity / worktreePath / lastOutputAt を一度に取得できる）、`worktree ps` は必要時のみ。availability 判定（issue 04 の `is_available()`）は初回に実行しキャッシュし、毎サイクル再プローブしない。
- **終了:** `KeyboardInterrupt` で最終スナップショット表示 + 通常終了（exit 0）。アダプタ例外は 1 サイクル分の欠損として表示を続ける（crash しない — P5 AC1）。
- **フラグ併用:** `--watch` + `--json` / `--capabilities` は usage error。`--debug` は stderr 併用可（issue 03 に整合）。
- **テスト追加:** watcher レンダラを純粋関数化し、実 sleep なしの単体テストを §8 に追加。

## 備考
1–3 秒という目標周期自体は上位仕様 §21 準拠で妥当。問題は到達手段の記述不足のみ。Orca 側は `orca terminal list --json` 1 発で P0–P2 の主要フィールドが取れるため、3 秒周期なら十分現実的。
