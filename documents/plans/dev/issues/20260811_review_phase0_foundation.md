# フェーズ 0 計画レビュー（README・Cursor 対応・skill search・診断サマリー）

## 優先度
🟡 中（🔴 なし / 🟡 3 / 🟢 4）

## 対象
- 計画書: `documents/plans/dev/20260811_phase0_foundation.md`

## 指摘事項

### 🟡 0-1: タスク 0-4 の前提誤認 — `get-all-rec` は「取得一覧」ではなく「デプロイ」コマンド

計画は「入力: `ai-adapter get-all-rec` → 従来の取得一覧に加えて末尾に診断サマリー」と記述するが、
`get_all_rec.py` は `~/.ai-adapter/` → プロジェクト `.github/` への**デプロイ**コマンドであり
（`cmd_get_all_rec`、出力は「agents/: N deployed」等の進捗行）、「取得一覧」を表示しない。
さらにサンプル出力「Agents: 3 (1 in repo, 2 new)」は**デプロイ前**の差分状態を表すが、
実装順が「デプロイ → サマリー」になると `compare_all` は常に up-to-date を返す。

**改善案**:
- サマリーの算出タイミングを「デプロイ実行前（差分算出 → サマリー表示 → デプロイ）」と明記する。
- またはサマリーを `--dry-run` 相当（変更を加えず差分のみ表示）として分離し、従来のデプロイ動作と
  直列にしない設計を採る。
- BDD の「従来の取得一覧に加えて」を「従来のデプロイ結果に加えて」に修正。

### 🟡 0-2: テスト計画のファイル参照誤り — `tests/test_get_all_rec.py` は存在しない

計画のテスト計画表は「0-4 | `tests/test_get_all_rec.py`（拡張）」とするが、
現状 get-all-rec のテストは `tests/test_cli.py`（L620-702: `test_get_all_rec_*`）に存在し、
`test_get_all_rec.py` というファイルは無い。「拡張」という前提が成立しない。

**改善案**: 「`tests/test_get_all_rec.py`（新設・サマリー出力 Unit 5 件）または
`tests/test_cli.py`（拡張）」に修正する。

### 🟡 0-3: タスク 0-2 の `agent get --format cursor` — グループ名の曖昧さと Cursor の agent 概念欠如

CLI 上、`agent` グループは `instruction.py`（AGENTS.md 等のルート命令ファイル管理）であり、
サブエージェント（`.agent.md`）は `sub-agent` グループ（`agent.py`）。計画の「`ai-adapter agent get`」
はどちらを指すか曖昧。加えて Cursor にネイティブな「agent」概念は無く、`.cursor/rules/` への展開は
意味論（role/behavior）が失われる。

**改善案**:
- 0-2 のスコープを `skill get-all --format cursor` と `mcp get --format cursor` に限定し、
  agent は「変換不可エラー」に明確化する（計画 AC の「変換不可ならエラー表示」を主経路にする）。
- `sub-agent` を対象とする場合は、どの Cursor 形式にマップするかを仕様に明記する。

### 🟢 0-4: `providers/cursor.py` の関数名が openclaw と非対称

計画 §4 は `resolve_output_path` と書くが、openclaw の対称関数は `resolve_mcp_output_path`（openclaw.py L145）。

**改善案**: openclaw と対称に `resolve_mcp_output_path` へ統一（AC3 の記述も整合させる）。

### 🟢 0-5: タスク 0-2 の参照行番号「mcp.py L195-221」は実装時点でずれる

`--format` Choice は mcp.py L199-203、openclaw 分岐は L225-226。行番号固定参照は保守性が低い。

**改善案**: 「`mcp_get` の `--format` Choice と `_mcp_get_openclaw` 分岐」のようなシンボル参照に変更する。

### 🟢 0-6: 新コマンド・新ファイル追加時の cli.py 登録が計画に未記載

`providers/cursor.py` 新設・`--format cursor` 追加時に、`cli.py` の import / `main.add_command` や
`tests/test_cli.py` のスモークテスト追加が必要。

**改善案**: 各タスクの受け入れ条件に「`cli.py` 登録と CLI スモークテスト」を明記する。

### 🟢 0-7: タスク 0-1 のサムネイル受領待ちは適切に管理されている（良好）

プレースホルダー運用・AC3 の相対パス参照は妥当。受領後の組み込みはレビュー対象外でよい。

## 備考
既存コード参照（openclaw.py の deploy_skills / export_mcp / resolve_mcp_output_path、diff.py の
compare_all L202、skill.py の `_deploy_skills_standard` L406、mcp.py の `--tool cursor` フィルタ）は
すべて実在確認済みで、再利用マップの核は正確。上記 🟡3 件の修正（0-4 の意味論・テストファイル参照・
0-2 の agent スコープ）を条件に承認可能と判断。

## 判定
修正必要（軽微）— 🟡3 件の修正を条件に承認可
