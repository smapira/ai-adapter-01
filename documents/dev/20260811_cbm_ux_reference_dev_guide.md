# codebase-memory-mcp の UX を開発の参考にする設計指針（開発者向け指示書）

- 作成日: 2026-08-11
- 対象バージョン: codebase-memory-mcp **v0.9.0**（2026-08-11 検証）
- 想定読者: **ai-adapter を開発・改善する社内開発者**
- 一次ソース: `documents/plans/dev/issues/20260811_research_codebase_memory_mcp_ux.md`（Researcher 調査レポート）・公式リポジトリ https://github.com/DeusData/codebase-memory-mcp

> **本書の位置づけ**
>
> 本書は codebase-memory-mcp の**導入手順書ではありません**。codebase-memory-mcp が実現した優れた UX（セットアップ UX・組織標準化 UX）を**原理・原則（A〜N）として抽象化**し、ai-adapter の設計・開発に**適用するための指針**を記します。各原則には「ai-adapter への適用検討ポイント」を添えています。
>
> - 事実の一次ソースは調査レポート（本リポジトリ内）と公式 README
> - 実行可能な詳細（コマンド例・マトリクス等）は本指示書末尾リンク先を参照
> - 適用検討は**提案**であり、本書だけでは実装・設定変更を指示しません

---

## 目次

1. [第 1 部: セットアップ UX 適用指針](#第-1-部-セットアップ-ux-適用指針)
   - 原則 A: 導入は 1 コマンド
   - 原則 B: 配布チャネルの多様化
   - 原則 C: 検証の仕組み
   - 原則 D: phoning home なし
   - 原則 E: install による自動構成
   - 原則 F: 段階的ツール権限
   - 原則 G: 安全な更新・アンインストール
   - 原則 H: セキュリティ監査を前面に
2. [第 2 部: 組織標準化 UX 適用指針](#第-2-部-組織標準化-ux-適用指針)
   - 原則 I: 使い方の規約化
   - 原則 J: ツール優先順の明文化
   - 原則 K: クイック参照表
   - 原則 L: 非ブロッキング誘導フック
   - 原則 M: 教育型ドキュメント
   - 原則 N: 知識の永続化・共有
3. [第 3 部: 適用チェックリスト（設計時 DoD）](#第-3-部-適用チェックリスト設計時-dod)
4. [付録: 事実整合チェック対応表](#付録-事実整合チェック対応表)

---

# 第 1 部: セットアップ UX 適用指針

## 原則 A: 導入は 1 コマンド

### codebase-memory-mcp の実現
- 公式は「download → run `install` → done」の **1 行インストール**を看板にしている:

  ```bash
  curl -fsSL https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/main/install.sh | bash
  ```

- 単一静的 C バイナリ・ゼロ依存。macOS / Linux / Windows の 4 アーキテクチャ分のアーカイブ + 各リリースに `checksums.txt` を同梱。初回セットアップが「1 つのコマンド」に凝縮されている

### なぜ良い UX か
- 導入の意思決定コストがほぼゼロ。「試してみる」障壁が下がり、評価→採用の導線が短い

### ai-adapter への適用検討ポイント
- ai-adapter は Python パッケージであり、現在の README 記載のインストール方法は `pip install ai-adapter` / `uv pip install ai-adapter`（※ `documents/dev/plans/20260720a.md` の計画中に言及はあるが README には未記載 = **提案**）
- 検討: README の冒頭に「最も短い 1 コマンド」を提示する（例: `uv tool install ai-adapter`）
  - ✅ 既存の `pip install ai-adapter`・`uv pip install ai-adapter` を併記し、選択肢を隠さない
  - 実装差分の注記: cbm は単一バイナリだが ai-adapter は Python 依存パッケージ。**原理（導入を 1 コマンドにする）** で適用し、実行環境の前提（Python 3.10+・uv）は明記する

## 原則 B: 配布チャネルの多様化

### codebase-memory-mcp の実現
- 配布手段が **9 系統**: npm / PyPI / Homebrew / Scoop / Winget / Chocolatey / AUR / `go install` / GitHub Releases
- 利用者が自分の環境・慣れたパッケージマネージャで導入できる

### なぜ良い UX か
- 「自分の環境にないツール」への抵抗を消す。チャネルごとに検証（checksums / 署名）が揃っているため、どの導線でも信頼を損なわない

### ai-adapter への適用検討ポイント
- Python 製という特性上、**PyPI（pip/uv）が本命チャネル**。GitHub Releases での wheel/sdist 公開も現状に近い
- 検討: Homebrew（`brew install`）対応は macOS 利用者への導線として有効。チャネル追加時は「どれが正導線か」を README 冒頭で明示し、選択肢の並列提示にしない

## 原則 C: 検証の仕組み

### codebase-memory-mcp の実現
- 各リリースに `checksums.txt` を同梱。**SLSA 3** ビルド保証、**VirusTotal 0/N** の公開（SECURITY.md に明記）を前面に出し、配布物の検証方法を提供している

### なぜ良い UX か
- 自動インストーラ・バイナリ配布に対する「信頼してよいか」という最大の不安を、**検証可能な形で解消**する。監査のハードルを下げる

### ai-adapter への適用検討ポイント
- ai-adapter は既に **Agent Plugins 1.0.0** 対応（`plugin build` / `plugin validate`・exit codes・`--json` / `--strict`）を持つ。cbm の checksums / SLSA 公開と組み合わせることで、**配布物検証 UX の土台として拡張**できる
- 検討: リリース時に `checksums.txt` / 署名を同梱・公開する。PyPI は hash 検証が標準だが、GitHub Releases 経由の配布物には明示的な検証手段を用意する
- SLSA 相当の生成物保証（sdist/wheel の再現ビルド）は可能な範囲で計画に含める

## 原則 D: phoning home なし

### codebase-memory-mcp の実現
- ネットワーク要求を**自発しない**。アップデートもバイナリ内では行わず、`update` コマンドは「実行すべき install スクリプトのパスを表示するだけ」に分離している（macOS/Linux でも同様のポリシー）

### なぜ良い UX か
- 企業内・オフライン環境でも動作保証できる。利用データの収集懸念がなく、セキュリティ監査が通しやすい

### ai-adapter への適用検討ポイント
- ai-adapter は `sync`（GitHub との同期）が主機能であり、**利用者が明示的に実行した通信**のみを行う設計を維持する
- 検討: 起動時の自動チェック（アップデート確認等）は phoning home と受け取られるため、「手動コマンドでのみ通信」を README・CLI ヘルプに明文化する

## 原則 E: install による自動構成

### codebase-memory-mcp の実現
- `install` コマンドが **43 クライアント面（37 自動検出 + 6 条件付き）** を自動構成
- 対応エージェント 9 種: Claude Code / Codex / Gemini CLI / Zed / OpenCode / Antigravity / Aider / KiloCode / Kiro
- Claude Code では **Skill + 3 フック + Post-Read カバレッジ**まで自動構成。OpenAI 系では Scout / Verify / Auditor の 3 段階ツール権限を自動配置

### なぜ良い UX か
- 手動設定（MCP 登録・スキル配置・フック作成）の「やり方調べ→書き写し→ミス」を全廃し、**環境を検出して正しく構成する**。導入後の「動かない」を最小化する

### ai-adapter への適用検討ポイント
- ai-adapter は既に「生成・自動化」を持っている: `opencode.json` 生成・`.opencode` → `.github` symlink・`codex install`（AGENTS.md 生成）・`sync`（GitHub 共有）
- 検討: 各生成物の「どのクライアントの設定か」を自動検出して生成対象を切り替える（cbm のクライアント検出に相当）。`ai-adapter codex install` 等を「環境を検出して何を書くか決める」方向に拡張する余地

## 原則 F: 段階的ツール権限

### codebase-memory-mcp の実現
- OpenAI 系エージェント向けに **Scout / Verify / Auditor の 3 段階ツールプロファイル**を正の許可リストで配布:
  - **Tier 1 (Scout)**: 軽量探索（約 3〜4 ツール）
  - **Tier 2 (Verify)**: タスク指向のエビデンス検証
  - **Tier 3 (Auditor)**: 限定スコープの監査
- 「全ツール開放」ではなく**段階的権限**でリスクを制御

### なぜ良い UX か
- 能力を絞るほど誤操作・事故の範囲が限定される。読み取り主体のタスクに書き込み権限が漏れない

### ai-adapter への適用検討ポイント（実例あり）
- ai-adapter は `opencode.json` 生成時に**全 10 ツールに `permission: "ask"`**（`_DEFAULT_PERMISSION`、`src/ai_adapter/providers/opencode.py` L130-141）を設定し、**すでに全開放を回避している**（read / edit / glob / grep / list / bash / task / webfetch / websearch / todowrite）
- 比較: cbm の段階的プロファイル（Tier 1/2/3）は「ask か allow か」の 2 択より**さらに粒度が細かい**。検討: 生成オプションとして「最小権限」と「開発用」プロファイルを用意する余地

## 原則 G: 安全な更新・アンインストール

### codebase-memory-mcp の実現
- `update`: 自己更新せず「実行すべき install スクリプトのパスを表示」
- `uninstall`: **所有が証明できないファイルは消さない**。インストールスクリプトを残しパスを報告。インデックス削除も確認付き

### なぜ良い UX か
- 「壊れたら直せない」不安を消す。更新・削除が失敗しても元の状態に戻れる（フォールバックがある）

### ai-adapter への適用検討ポイント
- 検討: `uninstall` 相当のコマンド実装時は、削除対象ファイルが自製のものか（所有確認）をチェックしてから削除する。更新は破壊的変更（env の値・生成物の差分）を事前に表示する方式を取る

## 原則 H: セキュリティ監査を前面に

### codebase-memory-mcp の実現
- 自動インストーラの作る範囲（agent 設定・フック・Skill）を事前に把握できる手段を提供
  - `--dry-run` での事前確認
  - hooks trust hash による再承認（Codex で設定変更時に再承認を要求）
  - **フックは全て fail-open・context-only**（決してブロックしない）
  - 「実験的フラグ・YOLO・権限バイパス・サードパーティ命令の信頼化はしない」という設計方針を README に明記
- **観点**: 監査・透明性（→ 原則 L の「誘導・習慣化」とは切り分け）

### なぜ良い UX か
- 「何が書き換わるか事前に見える」+「失敗しても静かに通過（fail-open）」の両立により、安全性と使いやすさのトレードオフを解消する

### ai-adapter への適用検討ポイント
- **注記: ai-adapter には現在 dry-run 機能は存在しない**（`src/ai_adapter/` に `dry_run` 関連実装なし）
- 検討: cbm の `--dry-run` を参考に、将来 `ai-adapter get-all-rec` 等の変更系コマンドに**変更プレビュー手段の導入余地**を検討する
- 既存の関連機能: `opencode validate`（`src/ai_adapter/providers/opencode.py`）・`plugin validate`（`src/ai_adapter/commands/plugin.py`）という検証系は既存。ここから「変更前に検証（dry-run）」への拡張が近い

---

# 第 2 部: 組織標準化 UX 適用指針

## 原則 I: 使い方の規約化

### codebase-memory-mcp の実現
- 事実としてこのリポジトリ（ai-adapter 自身）の `AGENTS.md` が「コードベース知識グラフ（codebase-memory-mcp）」節を設け、**「構造クエリは知識グラフ優先（grep/glob は文字列リテラル・設定値・非コードファイルのみ）」** と明文化している。使い方を**プロジェクト規約**に昇華している

### なぜ良い UX か
- 個人の「好きなツール」ではなく**組織としての標準**になる。新人が迷わず、コードレビューの指摘基準（規約準拠）になる

### ai-adapter への適用検討ポイント
- ai-adapter は生成物として `AGENTS.md` / `CLAUDE.md` を管理・配布できる（Root-Level Agent Management・`codex install`）
- 検討: **生成する AGENTS.md に同種の「ツール優先規約」節を織り込むテンプレート**を提供する。cbm 固有ではなく「自プロジェクトの知識基盤 × 使い方の優先順」を書ける汎用パターンにする

## 原則 J: ツール優先順の明文化

### codebase-memory-mcp の実現
- `AGENTS.md` に優先順を明記: **search_graph → trace_path → get_code_snippet → query_graph → get_architecture → detect_changes**
- 「構造クエリは知識グラフ、テキスト検索は grep」という使い分けを含めて文章化している

### なぜ良い UX か
- 「どのツールを最初に使うか」が悩みどころ。優先順が決まっていることで、エージェントの探索行動が確定し、トークン消費が最小化される

### ai-adapter への適用検討ポイント
- 検討: 生成する指示書テンプレートに「ツール優先順」のセクションを標準搭載する。順序は対象ツールに合わせて（例: `get` → `list` → `search` 等）書き換え可能な変数にしておく
- **規約化する理由（トークン効率の根拠）**: 実測（BM25 検索: 1,137 chars / trace_path: 16 callers を 17ms・1,699 chars）と研究論文の回答品質 83%（arXiv 2603.27277）という独立したデータを「なぜ優先順が要るか」の根拠として引用できる

## 原則 K: クイック参照表

### codebase-memory-mcp の実現
- インストール済み SKILL.md（`~/.claude/skills/codebase-memory/SKILL.md`）が **Quick Decision Matrix**（質問→ツール対応表）を提供:
  - 「誰が X を呼ぶ?」→ `trace_path(direction="inbound")`
  - 「X は何を呼ぶ?」→ `trace_path(direction="outbound")`
  - 「デッドコード」→ `search_graph(max_degree=0, exclude_entry_points=true)`
  - 「変更の影響」→ `detect_changes()`
  - 全 14 ツール・Edge Types・Cypher 例・**Gotchas 5 件**（失敗の形を先に知らせる）を 63 行に圧縮

### なぜ良い UX か
- 自然言語の「質問」を最短で「ツール呼び出し」に写像できる。ドキュメントを読まなくても 1 枚で動ける

### ai-adapter への適用検討ポイント
- 検討: ai-adapter が配布するスキル/プロンプトに**「質問 → コマンド対応表」の 1 枚表**を同梱する。コマンドリファレンス全体を渡すのではなく「この場面ではこの 1 コマンド」を先に提示する構成にする

## 原則 L: 非ブロッキング誘導フック

### codebase-memory-mcp の実現
- 3 つのフックが**全て fail-open・context-only**（README も「It never denies or replaces the requested tool call」と明記）:
  - `cbm-session-reminder`（SessionStart）: グラフツール優先プロトコルを毎セッション注入
  - `cbm-subagent-reminder`（SubagentStart）: サブエージェント生成時に追加コンテキスト注入
  - `cbm-code-discovery-gate`（PreToolUse）: 名前は legacy だが**決してブロックしない**。grep/glob にグラフコンテキストを付加（失敗時 `exit 0` でサイレント）
- **観点**: 誘導・習慣化（→ 原則 H の「監査・透明性」とは切り分け）

### なぜ良い UX か
- 「使え」と強制しない。**横からコンテキストを注入して気づかせる**方式なので、既存ワークフローを壊さない。失敗しても呼び出しを妨げない（レジリエント）

### ai-adapter への適用検討ポイント
- **注記: ai-adapter は現状 hooks を生成しない**（`opencode install` が生成する `opencode.json` は `$schema` / `lsp` / `instructions` / `permission` / `mcp` / `skills` / `command` のみで hooks セクションなし。※ `mcp` / `skills` / `command` は config が存在する場合に追加される条件付き）
- 検討: 将来 `opencode.json` 生成に hooks セクションを組み込む場合の**設計指針**として、「ブロックしない・コンテキスト付加のみ」の fail-open 原則を採用する。誘導系フックは「拒否」でなく「追加コンテキスト」で行う

## 原則 M: 教育型ドキュメント

### codebase-memory-mcp の実現
- SKILL.md の **Gotchas 5 件**が失敗パターンを先に開示:
  1. `search_graph(relationship=...)` は degree フィルタであり辺を見ない → Cypher を使え
  2. `query_graph` には行数キャップがある
  3. `trace_path` / `get_code_snippet` は exact name 必須 → 先に `search_graph`
  4. `direction="outbound"` は cross-service 呼び出し元を見逃す → `direction="both"`
  5. 結果は 1 ページ 10 件デフォルト → `has_more` / `offset` を確認
- 「失敗させるより先に失敗の形を知らせる」教育型設計

### なぜ良い UX か
- ユーザーが同じ罠に何度も落ちない。フィードバックループを短縮し、ツールへの信頼が育つ

### ai-adapter への適用検討ポイント
- 検討: ai-adapter が配布するドキュメント・スキルに **Gotchas 節（この操作ではこう失敗する→回避策）** を標準装備する。特に設定ファイル（opencode.json / AGENTS.md）の生成物に特有の落とし穴（意図しない上書き・フォーマット差分等）を先に明記する

## 原則 N: 知識の永続化・共有

### codebase-memory-mcp の実現
- **ADR 永続化**: `manage_adr`（get / update / sections）で設計判断をチーム資産として記録（このリポジトリの AGENTS.md も「主要な設計判断は ADR として永続化」と運用標準化済み）
- **チーム共有**: `index_repository(persistence=true)` で `.codebase-memory/graph.db.zst`（zstd 圧縮 SQLite）を生成し、コミットすれば**初回クローンのフル再インデックスを回避**。`.gitattributes` に `merge=ours` を自動作成しマージ争いも防止（任意オプション・gitignore 方針はチームで決定）

### なぜ良い UX か
- 個人のローカルにしかない知識・インデックスを**チームの資産**にし、再計算コストと知識喪失を防ぐ

### ai-adapter への適用検討ポイント
- ai-adapter は `~/.ai-adapter/` 一元管理 + `sync`（GitHub 共有）を持つ
- 検討: 共有対象に「設定の実体」だけでなく「**設計判断・使い方のナレッジ**（ADR 相当）」を含める運用を `sync` と組み合わせて提案する。`.gitattributes` の `merge=ours` パターンは、生成物（opencode.json 等）をリポジトリに置く場合のコンフリクト回避策として流用できる

---

# 第 3 部: 適用チェックリスト（設計時 DoD）

新機能・新コマンド・新生成物を設計するとき、以下の項目を確認する。各項目に「確認方法」と「該当原則」を添える。

| # | チェック項目 | 確認方法 | 原則 |
|---|-------------|---------|------|
| 1 | 導入は 1 コマンドで完了するか | README 冒頭に最短コマンド 1 行があるか | A |
| 2 | 配布チャネルは利用者の環境に合った選択肢があるか | 主要チャネル + 正導線の明示があるか | B |
| 3 | 配布物に検証手段（checksums 等）があるか | リリースに checksums.txt / 署名が同梱されているか | C |
| 4 | phoning home（自発的なネットワーク要求）がないか | 起動時・バックグラウンド通信がないか（`sync` 等は明示実行のみ） | D |
| 5 | 自動構成には dry-run / プレビュー手段があるか | 変更系コマンドに `--dry-run` 相当の**事前確認手段**があるか（**現状なし**。`opencode validate` / `plugin validate` は事後検証のみ） | E/H |
| 6 | 権限は段階的で、全開放になっていないか | 生成する設定の permission が最小化されているか（現状: 全ツール `ask`） | F |
| 7 | 使い方の優先順が生成物（AGENTS.md / README / スキル）に明文化されているか | 生成テンプレートに「優先順＋使い分け」節があるか | I/J/K |
| 8 | 変更・更新・削除が安全で、所有確認があるか | 削除が自製ファイルのみ対象か・更新が破壊的でないか | G |
| 9 | プロアクティブ誘導はブロックせず、コンテキスト付加に留まっているか | hooks 相当を生成する場合、fail-open・context-only か | L |
| 10 | ドキュメントは「失敗の形を先に知らせる」構成になっているか | Gotchas 節・既知の落とし穴が配布物にあるか | M |
| 11 | 知識（設計判断・設定）がチームで共有・永続化できるか | sync 対象にナレッジ/ADR が含まれるか・生成物の merge 方針があるか | N |

---

# 付録: 事実整合チェック対応表

本書の主要な事実・数値・URL を一次ソースと突合した結果。

| 本書の記述 | 一次ソース | 一致 |
|-----------|-----------|------|
| 単一静的 C バイナリ・ゼロ依存 / v0.9.0 | 調査レポート 1-1（--version = 0.9.0）/ 公式 README | ✅ |
| curl 1 行インストール | 調査レポート 1-1（install.sh 例） | ✅ |
| 9 チャネル（npm/PyPI/Homebrew/Scoop/Winget/Chocolatey/AUR/go install/GitHub Releases） | 調査レポート 1-1 | ✅ |
| checksums.txt / SLSA3 / VirusTotal 0/N | 調査レポート 1-2・6-3-2 / SECURITY.md | ✅ |
| phoning home なし・update はパス表示のみ | 調査レポート 1-1 / 公式 README | ✅ |
| 43 クライアント面（37 自動検出 + 6 条件付き） | 調査レポート 1-2 | ✅ |
| 対応エージェント 9 種 | 調査レポート 1-1（--help 実測） | ✅ |
| Claude Code: Skill + 3 フック + Post-Read | 調査レポート 1-2 | ✅ |
| Scout / Verify / Auditor の 3 段階 | 調査レポート 1-2 | ✅ |
| 実測: BM25 検索 1,137 chars / trace 16 callers 17ms・1,699 chars | 調査レポート 6-1（実測コマンド） | ✅ |
| 回答品質 83% / arXiv 2603.27277 | 調査レポート 6-1・エビデンス | ✅ |
| フック 3 種は fail-open・context-only | 調査レポート 4-2 / フック実ファイル | ✅ |
| SKILL.md の Quick Decision Matrix・Gotchas 5 件 | 調査レポート 4-1・6-2 / `~/.claude/skills/codebase-memory/SKILL.md` | ✅ |
| ai-adapter の README は pip / uv pip のみ（uv tool install は提案） | README L55/L58 / `documents/dev/plans/20260720a.md` L272 | ✅ |
| ai-adapter は Agent Plugins 1.0.0 対応（`plugin build` / `plugin validate`） | README（L6・L9-22・L367-397） | ✅ |
| ai-adapter は全 10 ツール `permission: "ask"`（_DEFAULT_PERMISSION） | `src/ai_adapter/providers/opencode.py` L130-141 | ✅ |
| ai-adapter は現在 dry-run 機能なし | `src/ai_adapter/` に `dry_run` 実装なし（grep 0 件） | ✅ |
| ai-adapter は hooks を生成しない | `src/ai_adapter/providers/opencode.py`（生成 config に hooks セクションなし） | ✅ |
| `opencode validate` / `plugin validate` が実在 | `src/ai_adapter/providers/opencode.py` / `commands/plugin.py` | ✅ |
| AGENTS.md に知識グラフ優先ルール・優先順が文書化済み | 本リポジトリ `AGENTS.md`（コードベース知識グラフ節） | ✅ |
| バージョン差リスク（SKILL.md「200-row cap」vs 実環境「100k ceiling」） | 調査レポート 6-3-1 | ✅（注記採用） |

> **バージョン差の注記**: インストール済み SKILL.md の「`query_graph` has a 200-row cap」は、実環境のツール説明（硬い 100k 行上限）と一致しない。本書は実際のツール仕様（100k ceiling）を正として扱い、SKILL.md 側の記述はバージョン更新対象として注記した。

> **対応表の検証メタデータ**: 検証日 2026-08-11 / 検証者: Reviewer・QA / 方法: 調査レポート・README・`src/ai_adapter/`・SKILL.md の実ファイルおよび外部 URL（HTTP 200）との突合。バージョン更新時は本対応表を再検証すること。

---

## 参照リンク

- 調査レポート: `documents/plans/dev/issues/20260811_research_codebase_memory_mcp_ux.md`
- 公式リポジトリ: https://github.com/DeusData/codebase-memory-mcp
- 研究論文: https://arxiv.org/abs/2603.27277
- インストール済み SKILL.md: `~/.claude/skills/codebase-memory/SKILL.md`
- 本リポジトリ規約: `AGENTS.md`（コードベース知識グラフ節）