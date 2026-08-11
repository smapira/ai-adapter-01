# ai-adapter グランドデザイン 再レビュー（指摘 10 件反映確認）

## 優先度
🟢 低（承認 — 軽微な改善提案のみ）

## 判定
**承認** — 前回指摘 10 件（🔴3 / 🟡5 / 🟢2）はすべて計画書に反映済み。コードベース実態との照合も完了し、再利用マップで言及された既存資産（`diff.py::compare_all` / `agent_plugins.py::ValidationIssue` / `git.py::_run_git` / `mcp.py::--tool` / `Config.remote` 等）はすべて実在を確認。新たな 🔴/🟡 レベルの矛盾・不整合は見つからなかった。

## 対象
- 計画書: `documents/plans/dev/20260811_ai_adapter_grand_design.md`
- 前回 issue: `documents/plans/dev/issues/20260811_review_ai_adapter_grand_design.md`

---

## 指摘 10 件の反映確認

| # | 指摘 | 判定 | 反映箇所 |
|---|------|:----:|---------|
| 🔴1 | マネタイズ矛盾 | ✅ | 冒頭 L21-22・6.1 L263-266・6.2 ティア表（Free 列に scan/setup/doctor/optimize）・3-2/3-4 の「ローカル実行のみ無料」 |
| 🔴2 | scan 粒度過大 | ✅ | 1-1a（Claude）/1-1b（Codex/Cursor）/1-1c（OpenCode/プロジェクト）/1-1d（統合表示）に分割、11 章とも整合 |
| 🔴3 | Cursor 分散 | ✅ | 0-2 で skills+mcp+agent を一本化。`mcp.py` の `--tool cursor`（L27・L62）と `--format openclaw`（L198-204）を土台と明記（ソース実在確認済み）。旧 1-5 は削除 |
| 🟡4 | doctor と validate 群 | ✅ | 1-2/1-4/3-1 に `ValidationIssue` / severity 統合を明記。8 章再利用マップにも追記 |
| 🟡5 | テスト計画欠落 | ⚠️ 大部分 | フェーズ 0〜3 にテストファイル名（test_cursor/test_scan/test_setup/test_doctor/test_optimize）・種別（Unit/Integration）・追加数を明記。技術指標に run_tests.sh ゲート追記。※ conftest.py 言及のみ欠落（🟢1） |
| 🟡6 | skill search 重複 | ✅ | 0-3 はローカル検索強化に限定、パブリックは 4-3 に分離 |
| 🟡7 | cloud スコープ | ✅ | 4-1a（CLI 側）/4-1b（サーバー側 API）に分割。GitHub Sync（`Config.remote` + `_run_git`）を既定バックアップ手段として位置付け |
| 🟡8 | scan セキュリティ | ✅ | UX②に「ファイル名・frontmatter のみ・auth 系ブラックリスト」追記。フェーズ 1 テスト計画に認証ファイル除外テスト必須化。リスク表に追加 |
| 🟢9 | 価格根拠 | ✅ | 6.2 に「参考値・競合調査 + Star 1,000 到達前後で確定」と明記 |
| 🟢10 | 再利用マップ | ✅ | 第 8 章を新設。7 タスク × 既存資産の対応表あり |

---

## 新たな発見（🟢 軽微 — フェーズ 0 の BDD 分解時に反映を推奨）

### 1. 🟢 技術指標に conftest.py の cwd 隔離の言及がない
- **指摘**: 反映申告では「conftest.py の cwd 隔離を技術指標に追記」とあるが、L366 は `scripts/run_tests.sh`（sandbox 方式・`.github` 保護）のみで、conftest.py への言及がない。
- **改善案**: 技術指標に「`tests/conftest.py` の per-test cwd 隔離を維持し、scan テストは tmp ディレクトリで実行（実ホームディレクトリをスキャンしない）」を 1 行追記する。

### 2. 🟢 フェーズ 4/5 のテスト計画にファイル名・種別の明記がない
- **指摘**: フェーズ 4 は「追加 20〜30 テスト（CLI 側）」のみで、テストファイル名・種別（Unit/Integration）が未記載。フェーズ 5 はテスト計画自体がない。
- **改善案**: フェーズ 4 に `test_cloud.py` の CLI 側 Unit テスト（API 契約のモック検証）を明記。フェーズ 5 はサーバー側 API テストと分離する方針を 1 行追記する。

### 3. 🟢 Skill Registry の課金境界が曖昧
- **指摘**: 6.2 表で「Skill marketplace（パブリック）」は Pro 有料だが、4-3 の CLI からのパブリックレジストリ検索・`skill install` が無料対象（CLI 機能）か有料対象（Cloud サービス）かが未定義。
- **改善案**: 4-3 に「CLI からのレジストリ検索・取得は無料。有料は Web UI・公開・組織管理などのサーバーサービス」と 1 行明記し、6.1 の課金境界原則との整合を取る。

### 4. 🟢 再利用マップに frontmatter パース系が未記載
- **指摘**: 前回指摘 10 で挙げた `agent_format.py` の `parse_frontmatter` と `skill.py` の `_parse_skill_metadata` が 8 章の対応表に含まれていない。1-1a〜c の scan は frontmatter 読み取りが核心であり、再利用資産として明記すべき。
- **改善案**: 8 章の 1-1 scan 行に「`agent_format.py` の `parse_frontmatter`・`skill.py` の `_parse_skill_metadata`」を追記する。

### 5. 🟢 タイポ 2 箇所
- **指摘**: L233・L248「期待する振る働き」→「期待する振る舞い」
- **改善案**: 修正する。

### 6. 🟢 4-1b（サーバー API）と 4-2（login）の依存順序
- **指摘**: サーバー側 API（4-1b）の前に OAuth 認証（4-2）が実装上必要だが、ロードマップの並びが 4-1a → 4-1b → 4-2 となっている。
- **改善案**: フェーズ 4 内の実装順として「4-1a CLI → 4-2 login → 4-1b API」または 4-1b に認証基盤を含める旨を 1 行追記する。

---

## 備考

- 前回指摘の本質（課金境界・タスク粒度・Cursor 一本化・セキュリティ）はすべて解決されており、本再レビューの発見はすべて 🟢 軽微な改善提案。
- 上記 🟢 6 件はフェーズ 0 の BDD タスク分解時に取り込めばよく、計画書の再修正を待つ必要はない。
- 次のアクション: ユーザー承認 → フェーズ 0 の BDD タスク分解（0-1 README 刷新を最初に）→ Implementer 実装。
