# codebase-memory-mcp が開発者に提供する UX の調査レポート

## 優先度
🔴 高（調査結論の核となる発見）→ 🟡 中（使いこなし上の注意点）→ 🟢 低（QoL・情報）

## 調査目的
コードベース知識グラフ MCP サーバー「codebase-memory-mcp」（本環境 v0.9.0 稼働）が開発者に提供する UX を構造化して報告する。ユーザーの関心は「インストールやスキルの用意が AI 時代の先端、どのような UX を開発者に提供しているか」。

## 調査方法
- **一次情報**: 公式 GitHub リポジトリ `DeusData/codebase-memory-mcp` の README（raw 取得・全文読解）、arXiv preprint 2603.27277、docs/llms.txt、npm/PyPI のランディング情報
- **ローカル検証**:
  - `~/.local/bin/codebase-memory-mcp --version` / `--help`（CLI トップの UX）
  - `cli list_projects`（全インデックス実績の列挙）
  - `cli search_graph --project ai-adapter-01 --query "run tests"`（BM25 自然言語検索を実測）
  - `cli search_graph --semantic-query '["checkout","commit"]'`（セマンティック検索を実測）
  - `cli trace_path --function-name _run_git --direction inbound --depth 1`（呼び出し元追跡を実測・応答時間計測）
  - `cli detect_changes`（影響分析を実測・0 変更時の挙動確認）
  - `cli get_architecture`（アーキテクチャ概要を実測）
  - `cli search_graph --help` / `config list`（フラグ設計・設定 UX）
  - `~/.claude/hooks/` 3 ファイル・`~/.claude/skills/codebase-memory/SKILL.md`・`opencode.json`・`~/.claude/.mcp.json` の読解
- **エビデンス**: 各主張に README 記述・SKILL.md 引用・実コマンド実行結果を添付

---

## 結果

### 1. インストール〜セットアップ UX

#### 1-1. 配布手段: 単一静的バイナリ + 9 チャネル（🔴 高）
- 公式（`DeusData/codebase-memory-mcp`）は「download → run `install` → done」の 1 行インストールを看板にする:
  ```bash
  curl -fsSL https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/main/install.sh | bash
  ```
- 配布手段は `npm` / `PyPI` / `Homebrew` / `Scoop` / `Winget` / `Chocolatey` / `AUR` / `go install` / GitHub Releases の 9 系統。本環境は `~/.local/bin` に配置されたネイティブバイナリ（`--version` = `0.9.0`）
- README は「Single static C binary, zero dependencies」を強調。macOS/Linux/Windows の 4 アーキテクチャ分のアーカイブ + 各リリースに `checksums.txt`
- **UX 上の設計判断点**:
  - アップデートは**バイナリ内では行わない**。`update` コマンドは「実行すべき install スクリプトのパスを表示するだけ」（Windows では稼働中バイナリが自己置換できないため構造的に必然。macOS/Linux でも「アップデータは本質的にダウンローダ」という判断で意図的に分離）。ネットワーク要求は一切自発しない（phoning home なし）
  - `uninstall` は「所有が証明できないファイルは消さない」（install スクリプトを残しパスを報告）。インデックス削除も確認付き
- 実測: `--help` で MCP サーバ / CLI / install / uninstall / update / config / UI の 7 用途が一覧され、サポートするエージェント 9 種（Claude Code・Codex・Gemini CLI・Zed・OpenCode・Antigravity・Aider・KiloCode・Kiro）を自動検出と明記。初回 UX が「1 つのコマンド」に凝縮されている

#### 1-2. `install` による自動構成: 43 client surfaces（🔴 高）
- README の Multi-Agent Support 節に 43 面（37 自動検出 + 6 条件付き）の行列がある。Claude Code では Skill + 3 つの graph agent + SessionStart/SubagentStart/PreToolUse フック + post-Read カバレッジまで自動構成する
- **セキュリティ・UX の両立設計**: 「実験的フラグを切り替えたり、プラグインを有効化したり、YOLO モードやグローバル権限バイパスやサードパーティ命令の信頼化はしない」。Codex では hooks の trust hash 変更で再承認が必要になる旨も明記（＝監査可能性を担保）
- OpenAI 系エージェントでは Scout / Verify / Auditor の 3 段階ツールプロファイル（Tier 1: 約3-4ツールの軽量探索 / Tier 2: タスク指向のエビデンス検証 / Tier 3: 限定スコープの監査）を正の許可リストで配布する設計——「全ツール開放」ではなく段階的権限という細かい UX

#### 1-3. `index_repository` のモード選択 UX（🟡 中）
- 本環境で確認できるモード: `full` / `moderate` / `fast` / `cross-repo-intelligence`、`persistence`（`.codebase-memory/graph.db.zst` を書くか）
- UX の意味: 「速度 vs 網羅性」のトレードオフと「チーム共有」を 1 ツールの引数で選べる。`fast` は類似/セマンティック辺なしで手早く、`full` は semantic_query や SEMANTICALLY_RELATED 辺込み。ただしこの選択肢の意味が初見の開発者に伝わるかは SKILL.md 等の誘導次第で、本環境の SKILL.md にはモードの説明がない（→ 改善余地）

#### 1-4. 未登録リポジトリへの誘導（🟡 中）
- 3 つのフックと SKILL.md が「まだインデックスされていなければ `index_repository` を先に実行」と明示:
  - `cbm-session-reminder` の 3 項「If a project is not indexed yet, run index_repository FIRST.」
  - SKILL.md の Exploration Workflow 1 番「`list_projects` — check if project is indexed」
- さらに `config set auto_index true`（セッション開始時の自動インデックス）と背景 watcher（git ポーリングによる自動再同期）が用意され、「index を忘れて grep に逃げる」を根絶する層構造。本環境では `auto_index=false` のため、誘導はフック/SKILL/AGENTS.md の 3 層に依存している

### 2. 検索・探索ツールの UX 設計（🔴 高）

「コードを名前で探す」以外の入り口を大量に用意している。実測で検証したもの:

| 入り口 | ツール/引数 | 実測結果（ai-adapter-01, 1,807 nodes） |
|--------|------------|--------------------------------------|
| 自然言語 BM25 | `search_graph --query` | `"run tests"` → `_run_git`（AGENTS.md が「fan-in 16 の唯一の窓口」と記す関数）が 1 位ヒット。total=482, has_more=true。全ペイロード 1,137 chars |
| ベクトル検索 | `--semantic-query '["checkout","commit"]'` | 名前に checkout/commit を含まない `discover_skills` / `compare_all` / `get_github_bins_dir` がヒット＝語彙ブリッジを実証 |
| 正規表現 | `--name-pattern '.*Handler.*'` | README の標準例。camelCase/snake_case 分割トークナイザ搭載 |
| 構造フィルタ | `--label` / `--min-degree` / `--max-degree` / `--relationship` | デッドコード（degree=0, entry point 除外）や high fan-in/out の発見に直結 |
| grep 派生 | `search_code` | グラフでエンリッチされた grep（インデックス済みファイルのみ対象、重複除去・構造的重要性でランク・tests 除外） |
| 完全修飾名 | `get_code_snippet` | 事前に `search_graph` で名前解決が必要（→ 下記 Gotchas） |

- BM25 は「Functions/Methods +10, Routes +8, Classes/Interfaces +5」の構造的ブースティングとノイズラベル（File/Folder/Module/Variable）除外という、**「定義を探す」行動を最適化したランキング設計**
- ページネーションは `limit`/`offset` + レスポンス内 `total`/`has_more` で、CLI フラグ説明にも「increment offset by limit and re-call while has_more is true」と使い方が書かれている（API 仕様がそのままヘルプ文章になる UX）
- `trace_path` は calls / data_flow / cross_service の 3 モード + `risk_labels`（CRITICAL/HIGH/MEDIUM/LOW）によるリスク分類。実測: `_run_git` の inbound depth 1 で **16 callers を 17ms・1,699 chars** で返却（AGENTS.md の記載と完全一致）
- `get_code_snippet` の完全修飾名制約（`<project>.<path_parts>.<name>`）は SKILL.md の Gotchas#3 と Tracing Workflow（1 番で `search_graph` により名前解決）に明記され、「exact name が必要」を探索ワークフローの一部として回収している

### 3. 分析・品質系ツールの UX（🟡 中）

- `get_architecture`: 1 コールで languages / packages / entry_points / routes / hotspots / boundaries / layers / **clusters（Leiden コミュニティ検出）** / file_tree を返す。実測: 12 clusters・10 hotspots を 15,878 chars の単一ペイロードで取得。**「フォルダ配置とは異なる実態のモジュール境界」を可視化する**という、grep では絶対に得られない価値
- `query_graph`: 読み取り専用 openCypher サブセット（`MATCH`/`WHERE`/`WITH`/`RETURN`/`UNION`/variable-length path `[*1..3]`/`EXISTS` 等）。**範囲外構文は「空を返す」のではなく明確な `unsupported …` エラーを返す**設計＝サイレント失敗による誤解を防ぐ UX。complexity プロパティ（cyclomatic / cognitive / loop_depth / linear_scan_in_loop / alloc_in_loop / recursion_in_loop / unguarded_recursion / param_count / max_access_depth）が Function/Method ノードに載っており、ホットパス検出 Cypher が README に例示されている
- `detect_changes`: git diff → 影響シンボル + blast radius のマッピング。実測では未コミット変更ゼロでも**エラーにせず空配列 77 chars で戻る**（グレースフル UX）
- `manage_adr`: 設計判断を get / update / sections で永続化。「破棄されやすい設計判断メモ」をチーム資産にする。本リポジトリの AGENTS.md も「主要な設計判断は ADR として永続化」と運用を標準化済み

### 4. スキル層・プロアクティブ UX（フック）（🔴 高）

#### 4-1. SKILL.md の Quick Decision Matrix
「質問 → ツール呼び出し」の 9 行対応表（Who calls X? → `trace_path(inbound)` 等）。**「構造的な疑問」を自然言語のままツールに写像する最短経路**を提供し、学習コストを下げる。さらに Dead code / High fan-out / High fan-in のレシピ、Edge Types 一覧、Cypher 例 3 件、**Gotchas 5 件**（落とし穴と回避策）まで 63 行に圧縮。

#### 4-2. 3 フックの「非ブロッキング誘導」設計思想（🔴 高・本調査の核）
- `cbm-session-reminder`（SessionStart）: 「グラフツールをコード探索の FIRST に使え」というプロトコルを毎セッション注入
- `cbm-subagent-reminder`（SubagentStart）: サブエージェント生成時に `hookSpecificOutput.additionalContext` としてコンテキスト注入（JSON 形式で正規のインターフェースに乗せる）
- `cbm-code-discovery-gate`（PreToolUse）: **名前は legacy だが「決してブロックしない」**。`hook-augment` で grep/glob にグラフコンテキストを付加し、失敗時は `exit 0` でサイレント
- README も「Hooks installed by this project are **fail-open and context-only**… It never denies or replaces the requested tool call」と明記。PreToolUse での「ゲート」でありながら拒否をしない、という**安全第一のプロアクティブ UX**。Grep/Glob が呼ばれた瞬間にグラフシンボルを `additionalContext` として横から差し込む

#### 4-3. AGENTS.md 統合による標準化
本リポジトリの AGENTS.md は「構造クエリは知識グラフ優先（grep/glob は文字列リテラル・設定値・非コードファイルのみ）」と**組織としての使い方を文書化**し、優先順（search_graph → trace_path → get_code_snippet → query_graph → get_architecture → detect_changes）と ADR 永続化まで定めている。ツールの提供する「使い方」をプロジェクト規約に昇華させる UX の完成形。

### 5. 知識永続化・ランタイム連携 UX（🟡 中）

- **SQLite ローカル永続化**: `~/.cache/codebase-memory-mcp/*.db`。本環境では 5 プロジェクト（my-life-dash 402/511, docker-office 3,047/4,944, symphony_workspaces 152,716/546,940, ai-adapter-01 1,807/5,996, jimlux 2,669/5,128）を確認。WAL モード + 自動 watcher（git ポーリング・XXH3 コンテンツハッシュによる差分再インデックス）
- **`ingest_traces`**: ランタイムトレース（caller/callee/count）を HTTP_CALLS 辺の検証に取り込む——**静的分析（ツリーシッター）と実行実態の融合**。本環境の関数シグネチャ `ingest_traces(traces, project)` が確認できる
- **persistence オプション**: `.codebase-memory/graph.db.zst`（zstd 圧縮 SQLite スナップショット、8-13:1 圧縮）。コミットしてチーム共有すればクローン初回のフル再インデックスを回避。`.gitattributes` に `merge=ours` を自動作成してマージ争いも防止。ただし**任意オプション**であり、`.gitignore` に入れれば全員再インデックス、という選択肢も残す
- バックグラウンドで実行される**セッション調整デーモン**（複数クライアント間で watcher/インデックス/UI を共有、最終セッション終了でシャットダウン）と、CLI モードはデーモンに触れない（1 コマンド完結・常駐プロセスを残さない）という使い分け

### 6. 総合評価（開発者体験の観点）（🔴 高）

#### 6-1. 「~500 トークン vs ~80K」の主張の検証（実測で概ね裏付け）
- README は「5 構造クエリ = ~3,400 トークン vs ファイル探索 ~412,000（99.2% 削減）」、SKILL.md は「~500 vs ~80K」を主張。arXiv は 31 リポジトリ評価で「10× 少ないトークン・2.1× 少ないツール呼び出し・回答品質 83%（ファイル探索 92%）」を報告
- 本環境での実測:
  - BM25 検索（1,807 ノードプロジェクト）: 全ペイロード **1,137 chars ≈ 300–500 トークン**。grep で同回答（`_run_git` の発見 + 呼び出し構造把握）を得るには通常 10 ファイル超の読み込みになる
  - `trace_path` 16 callers: **17ms・1,699 chars**。grep で 16 呼び出し元を集めるには全ファイル横断 + コンテキスト読解が要る
- **検証結論**: 「構造的疑問」に限ればトークン削減は桁違いに実現。ただし「トークン削減」は**質問の構造性に依存**する（文字列リテラル検索・設定値探索は grep が正解——SKILL.md もフックも「text/config/non-code は Grep」と明示し、使い分けを教育している）

#### 6-2. 学習コストと Gotchas の設計意図
- 主な落とし穴 5 件を SKILL.md に明文化: ①`relationship=` は degree フィルタで辺を見ない（Cypher を使え）②`query_graph` には行数キャップ ③`trace_path`/`get_code_snippet` は exact name 必須（先に search_graph）④`direction="outbound"` は cross-service 呼び出し元を見逃す（`both` を使え）⑤結果は 1 ページ 10 件デフォルト（`has_more`/`offset` を確認）
- **意図の読み取り**: 「失敗させるより先に失敗の形を知らせる」教育型ドキュメント。exact-name 制約は「曖昧名検索は検索ツールで、正確な操作は trace/snippet で」という責務分離を強制し、逆に誤操作を減らす設計

#### 6-3. リスク・懸念点（🟡 中〜🟢 低）
1. **ドキュメントと実装のバージョン差リスク**: SKILL.md の「`query_graph` has a 200-row cap」は、本環境ツール説明の「hard 100k row ceiling」と一致しない。installed skill が 0.9.0 付属の最新版か不明で、Gotchas の陳腐化が学習コストの罠になる
2. **自動インストーラの書き込み範囲**: 43 client surfaces への自動構成は利便性が高い反面、agent 設定ファイルを多数書き換える。README 自身が監査方法（source review / hooks trust hash / VirusTotal 0/N・SLSA3・checksums）を前面に出すほど信頼設計に依存。本環境の `~/.claude/.mcp.json` は最小構成（command のみ）で、過剰書き込みは実測されていない
3. **巨大化した DB**: 本環境の symphony_workspaces は **553 MB** の SQLite。単一バイナリで自動 watcher が常駐する前提のため、リソース観点の長期監視は要る
4. **セマンティック検索のブラックボックス性**: 11 シグナル統合スコア（TF-IDF/RRI/API 署名/AST/データフロー/Halstead-lite/MinHash/モジュール近接/グラフ拡散）は説明可能だが、ユーザーに「なぜこれがヒットしたか」の可視化が薄い。エビデンス提示（Verify プロファイルの path coverage 義務）である程度補完されている
5. **トークン効率の対価**: 「83% vs 92% の回答品質」という arXiv の数値は、構造クエリに最適化したツール群の品質トレードオフを正直に開示している——「グラフが万能」ではないことの明示は UX として健全

---

## 推奨事項

1. **（推奨・即効）SKILL.md の継続更新を仕組み化する**: DoD に「`codebase-memory-mcp update` 後に installed skill の Gotchas とツール一覧の整合を確認」を追加。行数キャップ等の値がバージョンで変わるため、検証対象にする
2. **（推奨）`config set auto_index true` を検討**: 本環境は false のため index 漏れリスクをフック/SKILL/AGENTS.md の 3 層誘導に依存している。auto_index を有効化すればセッション開始時の未登録問題を根絶できる（デメリット: 巨大リポジトリでの初回インデックス時間。`auto_index_limit` で 50k 件まで調整可）
3. **（推奨）チーム共有の場合は `--persistence` を活用**: `.codebase-memory/graph.db.zst` をリポジトリにコミット（.gitattributes は自動生成）すれば、メンバーの初回クローン時のフル再インデックスを回避できる。任意オプションなので gitignore 方針とセットで決定
4. **（留意）`detect_changes` をコミット前チェックに組み込む**: 変更の blast radius を可視化するユースケース（AGENTS.md でも推奨）を pre-commit ワークフローや QA ゲートで実践する価値が高い
5. **（留意）巨大プロジェクトのインデックスは `fast` モードで開始 → 必要時に `full`**: `index_repository(mode="fast")` → `index_status` で確認 → セマンティック検索が必要になった時点で `full` に更新、がリソース効率の良い順序

## エビデンス

- **リポジトリ**: https://github.com/DeusData/codebase-memory-mcp（MIT, 初回リリース 2026-02-25, 4 週間で 900+ stars / arXiv 報告）
- **研究論文**: https://arxiv.org/abs/2603.27277（31 実リポジトリ評価: 83% 回答品質 / 10× 少トークン / 2.1× 少ツール呼び出し）
- **公式ドキュメント**: README（raw 取得）・docs/llms.txt・BENCHMARK.md・SECURITY.md（VirusTotal 0/N 公開・SLSA 3・checksums）
- **実測コマンド出力**:
  ```
  $ codebase-memory-mcp --version → 0.9.0
  $ cli list_projects → 5 プロジェクト（ai-adapter-01: 1,807 nodes / 5,996 edges 含む）
  $ cli search_graph --project ai-adapter-01 --query "run tests"
      → total: 482, has_more: True, 1 位 = _run_git, payload 1,137 chars
  $ cli search_graph --semantic-query '["checkout","commit"]'
      → discover_skills / compare_all / get_github_bins_dir（語彙ブリッジ実証）
  $ cli trace_path --function-name _run_git --direction inbound --depth 1
      → 16 callers, 0.017s, payload 1,699 chars
  $ cli detect_changes → 変更ゼロでもエラーなし（77 chars 空配列）
  $ cli get_architecture → 12 clusters / 10 hotspots / payload 15,878 chars
  ```
- **ローカル構成（既読の再確認）**: `~/.claude/skills/codebase-memory/SKILL.md`（63 行: Quick Decision Matrix・14 ツール・Edge Types・Cypher 例・Gotchas 5 件）、`~/.claude/hooks/{cbm-session-reminder, cbm-subagent-reminder, cbm-code-discovery-gate}`（全て fail-open・context-only）、`opencode.json`（type: local, command: `/Users/bookair18/.local/bin/codebase-memory-mcp`）、`~/.claude/.mcp.json`（command のみの最小構成）

## 備考
- 調査のみ実施。コード・設定の変更は行っていない
- 本レポートで観測した SKILL.md の「query_graph 200-row cap」とツール説明の「100k row ceiling」の差は、installed skill の版数確認（`codebase-memory-mcp update` の適用有無）を推奨する根拠とした
- サマリ: 「単一バイナリ + 自動インストーラ（43 surfaces）+ 3 段階ツール権限 + fail-open フック + SKILL/AGENTS.md による教育層」という**「インストールから習慣化まで」をワンストップで設計した先端 UX**。核となる価値は「構造的疑問を ~500 トークンに圧縮する」（実測で裏付け）と「grep に逃げさせないための多層誘導」