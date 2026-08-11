# 開発者向け指示書「codebase-memory-mcp の UX を開発の参考にする設計指針」作成計画

- 日付: 2026-08-11
- 作成者: Product Manager
- 状態: **完了**（指示書作成・Reviewer 検収・QA 承認・`documents/dev/` へ移動済み）
- 根拠: `documents/plans/dev/issues/20260811_research_codebase_memory_mcp_ux.md`（Researcher 調査レポート）
- レビュー履歴: 1 回目（🔴1 / 🟡5 / 🟢3）反映済み → Plan Architect 承認 → Reviewer 検収（🟡2 / 🟢4 反映・承認）→ QA 承認（🟢5 任意提案のうち検証メタデータのみ反映）

## 目的（ユーザー意図の明確化）

ユーザーの意図は **codebase-memory-mcp の導入ではなく**、**その優れた UX（セットアップ UX・組織標準化 UX）を開発の参考にし、ai-adapter プロジェクトの開発者向け「UX 設計指針」を作成すること**である。

- ❌ 誤解: codebase-memory-mcp のセットアップ手順書・使い方ガイドを作る
- ✅ 正解: codebase-memory-mcp が実現した優れた UX パターン（単一バイナリ配布・自動構成・fail-open フック・AGENTS.md による規約化等）を**抽象化して原理・原則として抽出**し、ai-adapter の設計・開発に**適用するための指針（指示書）**を文書化する

## 成果物

- `documents/plans/dev/20260811_cbm_ux_reference_dev_guide.md`
- 想定読者: **ai-adapter を開発・改善する社内開発者**
- Markdown 形式、日本語
- 位置づけ: 「調査レポート（事実）」→「本指示書（UX 原理と適用指針）」→「開発者が各機能の設計時に参照」
- **配置の運用**: 本指示書は恒久参照ドキュメントの性質を持つ。承認・検収後、`documents/plans/dev/` から **`documents/dev/20260811_cbm_ux_reference_dev_guide.md`** へ移動する運用とする（plans/ は計画のステージング領域のため）。移動は検収後に実施し、本計画書には移動後パスを記録する（**移動後パス: `documents/dev/20260811_cbm_ux_reference_dev_guide.md`**）

## 受け入れ条件（全体）

- [ ] AC1 セットアップ UX 適用指針・組織標準化 UX 適用指針・適用チェックリストの 3 部構成である
- [ ] AC2 抽出された UX 原理・数値・URL は調査レポートの実測・事実と矛盾しない（捏造なし）
- [ ] AC3 ai-adapter の現状（pip/uv 配布・Agent Plugins 1.0.0・`~/.ai-adapter/` 一元管理・opencode.json/AGENTS.md 生成・sync/GitHub 共有）を踏まえた「適用検討ポイント」が具体的に記載されている
- [ ] AC4 「codebase-memory-mcp の導入手順書」ではなく「UX 参考・設計指針」である
- [ ] AC5 各原則に「自プロダクトへの適用検討ポイント」が付随し、開発者が 1 回読んで自身の設計に適用できる

## タスク一覧（BDD）

### タスク 1: 指示書の骨子・想定読者・目的・位置づけ・構成の定義
- **期待する振る舞い**: 冒頭に「本書は codebase-memory-mcp の導入ガイドではなく UX 設計指針である」「読者は ai-adapter 開発者」「調査レポート（`documents/plans/dev/issues/20260811_research_codebase_memory_mcp_ux.md`）を事実の一次ソースとして参照する」旨が明記されている。**本文を 3 部構成（①セットアップ UX 適用指針 ②組織標準化 UX 適用指針 ③適用チェックリスト）とし、構成見出しを定義する**
- **データ例**: 調査レポートのパス・リポジトリ URL（https://github.com/DeusData/codebase-memory-mcp）・検証バージョン v0.9.0

### タスク 2: セットアップ UX 適用指針 — 配布・インストール戦略
- **期待する振る舞い**: codebase-memory-mcp の配布/導入 UX から以下を抽出し、ai-adapter への適用検討ポイントを各原則に添えて記載する:
  - 原則 A「導入は 1 コマンド」: curl 1 行インストールの UX 価値 → ai-adapter は pip/uv 配布なので「uv tool install ai-adapter」等の 1 コマンド体験の明文化を検討。**`uv tool install` は README に未記載の提案である旨を明示し、既存の `pip install ai-adapter` / `uv pip install ai-adapter` を併記する**
  - 原則 B「配布チャネルの多様化」: 9 チャネル配布 → ai-adapter（Python 製）での対応チャネル検討
  - 原則 C「検証の仕組み」: checksums.txt（+ SLSA3・VirusTotal 公開）→ ai-adapter 側の配布物検証方法の検討
  - 原則 D「phoning home なし」: ネットワーク要求を自発しない設計 → ai-adapter の利用データ収集方針の検討
  - 例外・注意: codebase-memory-mcp は単一静的 C バイナリだが、ai-adapter は Python パッケージという**実装差分を踏まえた適用**（原理としての抽出）である旨を明記
- **データ例**: `curl -fsSL https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/main/install.sh | bash`、`pip install ai-adapter`

### タスク 3: セットアップ UX 適用指針 — 自動構成・権限・更新/アンインストール
- **期待する振る舞い**: 以下の UX 原理を抽出し、ai-adapter への適用検討ポイントを添えて記載する:
  - 原則 E「install による自動構成」: 43 クライアント面（37 自動検出 + 6 条件付き）の自動構成 → ai-adapter の `opencode.json` 生成・`.opencode` → `.github` symlink・`codex install` 等の既存自動化への拡張検討
  - 原則 F「段階的ツール権限」: Scout / Verify / Auditor の 3 段階権限（全開放しない）→ ai-adapter が生成する設定の権限設計への示唆。**実例として、ai-adapter は `opencode.json` 生成時に全ツール `permission: "ask"`（`_DEFAULT_PERMISSION`）で全開放を回避していることを記述し、cbm の段階的プロファイル（Tier 1/2/3）はさらに粒度が細かいと比較する**
  - 原則 G「安全な更新・アンインストール」: update はパス表示のみ・uninstall は所有確認付き → ai-adapter のアップグレード/削除 UX への示唆
  - 原則 H「セキュリティ監査を前面に」: `--dry-run`・hooks trust hash・fail-open フックの説明 → **ai-adapter には現状 dry-run 機能は存在しない。cbm の `--dry-run` を参考に、将来 `get-all-rec` 等に変更プレビュー手段の導入余地を検討する**という提案文脈にする。**既存の検証系コマンド（`opencode validate` / `plugin validate`）との関連にも言及**。なお H は「監査・透明性」の観点で fail-open を扱い、原則 L（「誘導・習慣化」の観点）とは切り分ける
- **データ例**: ai-adapter の既存コマンド（`ai-adapter codex install`・`ai-adapter sync`・`plugin build`・`plugin validate`）

### タスク 4: 組織標準化 UX 適用指針 — 知識グラフ優先ルールとツール優先順
- **期待する振る舞い**: 組織標準化の UX 原理を抽出し、ai-adapter への適用検討ポイントを添えて記載する:
  - 原則 I「使い方の規約化」: AGENTS.md に「構造クエリは知識グラフ優先、grep は文字列リテラルのみ」と明文化 → ai-adapter が生成・管理する AGENTS.md / CLAUDE.md に同様の規約パターンを織り込む検討
  - 原則 J「ツール優先順の明文化」: search_graph → trace_path → get_code_snippet → query_graph → get_architecture → detect_changes の優先順 → 生成する指示書に「どのツールを先に使うか」の順序を明記するパターン
  - 原則 K「クイック参照表」: Quick Decision Matrix（質問→ツール対応表）→ ai-adapter のスキル/プロンプト生成に同様の 1 枚対応表パターンを適用する検討
  - トークン効率の根拠: 実測 BM25 1,137 chars / trace 17ms・1,699 chars・回答品質 83% を「規約化する理由」として引用
- **データ例**: AGENTS.md の既存記述（fan-in 16 の `_run_git`）、SKILL.md の Quick Decision Matrix

### タスク 5: 組織標準化 UX 適用指針 — プロアクティブ誘導・文書パターン・知識永続化
- **期待する振る舞い**: 以下の UX 原理を抽出し、適用検討ポイントを添えて記載する:
  - 原則 L「非ブロッキング誘導フック」: SessionStart / SubagentStart / PreToolUse フックが全て fail-open・context-only（決してブロックしない）→ **ai-adapter は現状 hooks を生成しない（`opencode install` 生成の opencode.json に hooks セクションなし）。将来 `opencode.json` 生成に hooks セクションを組み込む場合の設計指針として検討する**と提案文脈であることを明記。なお L は「誘導・習慣化」の観点で fail-open を扱い、原則 H（「監査・透明性」の観点）とは切り分ける
  - 原則 M「教育型ドキュメント」: SKILL.md の Gotchas 5 件（失敗の形を先に知らせる）→ ai-adapter が配布するスキル/ドキュメントの構成パターン
  - 原則 N「知識の永続化・共有」: ADR（manage_adr）・persistence（`.codebase-memory/graph.db.zst`・merge=ours）→ ai-adapter の sync/GitHub 共有と組み合わせた知識共有の検討
- **データ例**: 3 フックの実ファイルパス（`~/.claude/hooks/`）、`manage_adr` ツール

### タスク 6: 適用チェックリスト編（開発者が設計時に確認する DoD）
- **期待する振る舞い**: 指示書の最後に、開発者が新機能・新コマンドを設計するときに確認するチェックリストがある:
  - □ 導入は 1 コマンドで完了するか（A）
  - □ 配布チャネルは利用者の環境に合った選択肢があるか（B）
  - □ 配布物に検証手段（checksums 等）があるか（C）
  - □ phoning home（自発的なネットワーク要求）がないか（D）
  - □ 自動構成には dry-run / プレビュー手段があるか（E/H）
  - □ 権限は段階的で、全開放になっていないか（F）
  - □ 使い方の優先順が生成物（AGENTS.md / README / スキル）に明文化されているか（I/J/K）
  - □ 変更・更新・削除が安全で、所有確認があるか（G）
  - □ プロアクティブ誘導はブロックせず、コンテキスト付加に留まっているか（L）
  - □ ドキュメントは「失敗の形を先に知らせる」構成になっているか（M）
  - □ 知識（設計判断・設定）がチームで共有・永続化できるか（N）
  - 各項目に「確認方法」と「codebase-memory-mcp の該当原則」が付記されている
- **データ例**: 原則 A〜N との対応表

### タスク 7: 検証 — 事実整合チェック
- **期待する振る舞い**: 指示書内の全原理・数値・URL・ai-adapter 現状記述が、調査レポートの実測および ai-adapter の実際のコード/README と一致することを**対応表方式**で確認する:
  - 指示書内の全数値・URL・ai-adapter 現状記述を列挙した**対応表**を作成し、調査レポートのエビデンス列・README Features/Installation 節・`src/ai_adapter/` と 1:1 で突合して一致確認
  - **バージョン差リスク**（例: SKILL.md の「200-row cap」vs ツール説明「100k ceiling」）が指示書の数値引用に影響する場合、どちらを採用するか判断して注記
  - **不一致を検出した場合**、Implementer が成果物を修正し、再度タスク 7 を実行（フィードバックループ）
- **データ例**: 調査レポートのエビデンス列（--version / trace_path 実測値 / リポジトリ URL）・ai-adapter README の Features/Installation 節・`src/ai_adapter/providers/opencode.py`

## 制約

- コード・設定ファイル（opencode.json・AGENTS.md 等）は変更しない。**ドキュメント作成のみ**
- 指示書は調査レポートの事実を忠実に反映し、新しい事実（実測値・数値）を捏造しない
- **導入ガイドにしない**: コマンド実行手順そのものよりも「原理・原則」と「ai-adapter への適用検討ポイント」を主眼とする
- 実行コマンド・URL はそのまま実行・参照可能な完全な形で記載する
- アイデアとしての「適用検討」は提案に留め、実装・設定変更を指示しない

## 引き継ぎ先

- Plan Architect: 計画レビュー
- Implementer: 指示書作成実装
- Reviewer: 検収レビュー（受け入れ条件との突合）
- QA: 品質チェック（リンク・パス・事実整合・ai-adapter 現状との矛盾）