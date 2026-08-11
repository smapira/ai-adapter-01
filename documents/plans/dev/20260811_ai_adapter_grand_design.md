# ai-adapter グランドデザイン & ロードマップ

- 日付: 2026-08-11
- 作成者: Product Manager（外部プランナーの提言 + コードベース実態調査に基づく）
- 状態: ドラフト（Plan Architect レビュー反映済み・ユーザー承認待ち）
- 対象バージョン: v0.21.1 時点の実態から将来像まで
- レビュー履歴: Plan Architect 1 回目（🔴3 / 🟡5 / 🟢2）反映済み

---

## 1. エグゼクティブサマリー

ai-adapter は「AI エージェント設定の管理 CLI」から、**「AI 開発環境のパッケージマネージャ + dotfiles + App Store + Dependabot」** を兼ねるプロダクトへ進化させる。

**ポジショニング（最終形）**:

> **Your AI development environment, everywhere.**
> One configuration for all your AI coding agents.
> Manage, sync and deploy AI agent configuration across Claude Code, Codex, Cursor, VS Code, OpenCode and more.

**事業モデル**: OSS CLI は**無料・無制限**（CLI 機能すべてを無料提供）。**ai-adapter Cloud（Pro / Team / Enterprise）** と **Skill/Pack Registry** から収益化する。
課金の境界は「CLI の機能」ではなく「**Cloud サービス（再現性・共有・組織管理）**」に置く。CLI 側で実装される `doctor` / `optimize` の診断・適用機能も**ローカル実行に限り無料**とし、クラウド同期・チーム共有などのサーバーサービスだけが有料となる（🔴1 反映）。

**提供価値の 4 段階**: `Install → Discover → Configure → Maintain`
ユーザーが「何を設定すればいいか」を考えなくても、AI 開発環境が自動的に構築・診断・改善・維持される体験を提供する。

---

## 2. 現状分析（v0.21.1 実態との突合）

### 2.1 既に実装済みの資産（強み）

| 領域 | 現状 | 状態 |
|------|------|------|
| Agent / Sub-agent | `agent` / `sub-agent` コマンド（add/list/get/remove、`--env` 対応） | ✅ 実装済み |
| Skills | `skill` コマンド（add/list/get/get-all/remove/search/link-agent、SKILL.md 形式） | ✅ 実装済み |
| MCP | `mcp` コマンド（add/list/get、`--file` / `--format openclaw` / `--path`） | ✅ 実装済み |
| Prompts / Commands | `prompt` / `command` コマンド（add/list/get/remove、`--env`） | ✅ 実装済み |
| Bins（スクリプト） | `bin` コマンド（add/list/get/remove、`add-path`、`--env`） | ✅ 実装済み |
| Env（環境分離） | `env` コマンド（add/list/set-default/link-agent/remove-all） | ✅ 実装済み |
| 一元管理 | `~/.ai-adapter/` に集約、`add-all-rec` / `get-all-rec` | ✅ 実装済み |
| GitHub Sync | `sync`（rebase 継続/中断/スキップ対応）・`init --remote`・`start <URL>` | ✅ 実装済み |
| OpenCode | `opencode` コマンド（install/uninstall/validate/alias、opencode.json 生成） | ✅ 実装済み |
| Codex CLI | `codex` コマンド（install/uninstall、AGENTS.md 生成） | ✅ 実装済み |
| OpenClaw | `--format openclaw` エクスポート | ✅ 実装済み |
| Agent Plugins 1.0.0 | `plugin build` / `plugin validate`（exit codes / `--json` / `--strict`） | ✅ 実装済み |
| テスト基盤 | 337 テスト・CI（Python 3.10-3.12 matrix）・sandbox 方式 | ✅ 実装済み |

### 2.2 ギャップ（プランナー提言との差分）

| プランナー提言 | 現状 | 差分 |
|--------------|------|------|
| `ai-adapter scan`（環境診断） | なし（`get-all-rec` が近いが診断ではない） | 🔴 未実装 |
| `ai-adapter setup <profile>`（一括セットアップ） | なし | 🔴 未実装 |
| `ai-adapter doctor` / `optimize`（環境ヘルス/自動改善） | なし（`opencode validate` / `plugin validate` の検証系は既存） | 🔴 未実装 |
| `ai-adapter cloud`（バックアップ/復元/マルチデバイス） | GitHub Sync のみ（CLI レベル） | 🔴 未実装 |
| Skill Registry / Packs | `skill search` はローカル検索のみ | 🟡 部分 |
| Cursor / Continue 対応 | wiki 上 "Planned" | 🟡 未対応 |
| README ファーストビュー刷新 | 機能一覧が先・抽象的（"Common management infrastructure"） | 🟡 要改善 |
| マーケティング（AI dotfiles カテゴリー） | 未着手 | 🔴 未着手 |

---

## 3. プロダクトアーキテクチャ（最終像）

```
                    ai-adapter
                         │
             ┌───────────┴───────────┐
             │                       │
          OSS CLI                  Cloud
             │                       │
       ┌─────┼─────┐          ┌──────┼──────┐
       │     │     │          │      │      │
     Scan  Setup  Sync      Backup  Registry Team
       │     │     │          │      │      │
       └─────┴─────┘          └──────┴──────┘
             │                       │
             └──────────┬────────────┘
                        ↓
              AI Environment Management
                        │
            ┌───────────┼───────────┐
            ↓           ↓           ↓
         Personal      Team     Enterprise
```

### レイヤー構造

| レイヤー | 役割 | 主な構成要素 |
|---------|------|-------------|
| **L0: コア基盤** | 既存の一元管理・同期基盤 | `~/.ai-adapter/`・GitHub Sync・env・models/config |
| **L1: 発見（Discover）** | 環境の可視化・診断 | `scan`・`doctor`・`get-all-rec` 強化 |
| **L2: 構成（Configure）** | 一括セットアップ・プリセット | `setup <profile>`・Packs・skill install |
| **L3: 維持（Maintain）** | 監視・更新・最適化 | `doctor --fix`・`optimize`・バージョン追跡 |
| **L4: 共有（Cloud）** | バックアップ・チーム・マーケット | Cloud sync・Registry・Team workspace |
| **L5: 組織（Enterprise）** | ガバナンス | RBAC・Audit・SSO/SAML・On-premise |

---

## 4. UX 原則（4 段階）

### ① Install —「入れたらすぐ便利」

```bash
uvx ai-adapter        # または pipx run ai-adapter
```

初回実行時に環境を自動検出し、「何を設定すればいいか」を考えさせない。

**期待する振る舞い（BDD シナリオ）**:
- 入力: `ai-adapter`（初回起動・引数なし）
- 応答: Claude Code / Codex / Cursor / MCP / AGENTS.md の検出結果 + `[Set up my environment]` 導線
- 入力: `ai-adapter init`（新規）
- 応答: `~/.ai-adapter/` 初期化 + 検出済み設定の取り込み提案

### ② Discover —「自分が何を持っているか分かる」

```bash
ai-adapter scan
```

散らばった AI 設定（`~/.claude/` `~/.codex/` `~/.cursor/` `~/.config/opencode/` 等）を一覧化し、問題点を診断する。

**期待する振る舞い**:
- 入力: `ai-adapter scan`
- 応答: Agents / Instructions / Skills / MCP の検出一覧 + `Potential problems`（重複・不一致・古い Skill）
- **セキュリティ方針**: scan は**ファイル名・frontmatter（name/description/tags）のみ**を読み取り、内容全文は表示しない。認証情報を含むファイル（`~/.codex/auth.json` 等）はブラックリストで除外（🟡8 反映）

### ③ Configure —「自分で設定する」から「選ぶ」へ

```bash
ai-adapter setup web-development
```

推奨構成（Skills / MCP / Agents / Commands）を提示し、1 コマンドで導入。

**期待する振る舞い**:
- 入力: `ai-adapter setup web-development --dry-run`
- 応答: 推奨パッケージ構成（Skills: frontend/react/typescript…、MCP: github/playwright…）のプレビュー
- 入力: `ai-adapter setup web-development`
- 応答: 選択した構成の一括デプロイ + 適用後の `scan` 結果

### ④ Maintain —「一度設定したら終わり」にしない

```bash
ai-adapter doctor
```

環境ヘルスを監視し、更新・互換性問題を検出して修正を提案する（AI 環境の Dependabot）。

**期待する振る舞い**:
- 入力: `ai-adapter doctor`
- 応答: ヘルスサマリー（✓ 23 skills / ✓ 8 MCP / ⚠ updates available / ⚠ compatibility issues）+ `[Fix all]`
- 入力: `ai-adapter doctor --fix`
- 応答: 更新・互換性修正の適用と結果報告
- **既存検証系との関係**: doctor は既存の `opencode validate` / `plugin validate` / Agent Plugins の `ValidationIssue` を**共通モデルとして統合**し、重複実装しない（🟡4 反映）

---

## 5. 機能ロードマップ

### フェーズ 0: 基盤完成（現在〜 v0.22）— 4〜6 週間
**目的**: 既存機能を固め、OSS としての完成度を高める。市場投入の土台。

| # | タスク | 期待する振る舞い | 優先度 |
|---|--------|-----------------|--------|
| 0-1 | README ファーストビュー刷新 | 「One configuration for all your AI coding agents」+ 対応ツール図 + 最短 3 コマンド導線 | 🔴 高 |
| 0-2 | **Cursor 対応の一本化**（skills + mcp + agent） | `skill get-all --format cursor`（`.cursor/rules/*.mdc`）・`.cursor/mcp.json` 生成・`agent get --format cursor`。既存 `mcp.py` の `--tool cursor` フィルタと `--format openclaw` パターンを土台に**フェーズ 0 で一括完了**（🔴3 反映） | 🔴 高 |
| 0-3 | `skill search` の**ローカル検索強化に限定** | 名前/説明/タグの一致 + タグフィルタ。パブリックレジストリ検索はフェーズ 4-3 に分離（🟡6 反映） | 🟡 中 |
| 0-4 | `get-all-rec` に診断サマリー追加 | 環境検出数・重複・不一致を要約表示（`diff.py` の `compare_all` / `FileDiff` を再利用） | 🟡 中 |
| 0-5 | docs 整備（wiki: 対応ツール比較を README へ昇格） | 競合比較をユーザー向けに整理 | 🟢 低 |
| 0-6 | メタデータ整備（pyproject keywords / description 刷新） | パッケージ説明を「Manage and sync your AI agent configuration across Claude Code, Codex, Cursor, VS Code, OpenCode」に変更 | 🟢 低 |

**テスト計画（フェーズ 0）**: 既存 337 テスト + 追加 20〜30 テスト。
- 0-2: `test_cursor.py` 新設（形式変換 Unit 10〜15 件・`--format cursor` のスナップショット）
- 0-4: `test_get_all_rec.py` 拡張（サマリー出力の Unit 5 件）
- 実行ゲート: `scripts/run_tests.sh`（sandbox 方式）を CI・pre-commit で維持（🟡5 反映）

### フェーズ 1: Discover（v0.23〜v0.30）— 6〜8 週間
**目的**: 「環境診断ツール」としての価値確立。新規ユーザーの入口を作る。

| # | タスク | 期待する振る舞い | 優先度 |
|---|--------|-----------------|--------|
| 1-1a | **`scan` — Claude Code 検出** | `~/.claude/` 配下の agents / skills / settings を検出（ファイル名・frontmatter のみ読み取り、auth 系は除外） | 🔴 高 |
| 1-1b | **`scan` — Codex / Cursor 検出** | `~/.codex/`・`~/.cursor/` 配下の config / rules を検出（`auth.json` 等の認証ファイルはブラックリスト除外） | 🔴 高 |
| 1-1c | **`scan` — OpenCode / プロジェクト検出** | `~/.config/opencode/`・プロジェクトの `.github/` `AGENTS.md` `CLAUDE.md` `.mcp.json` を検出 | 🔴 高 |
| 1-1d | **`scan` — 結果統合表示** | 1-1a〜c の結果を統合し、一覧 + 件数サマリーを表示（🔴2 反映: ツール単位に分割） | 🔴 高 |
| 1-2 | `scan` の問題診断 | 重複 MCP・Claude/Codex 間の設定不一致・古い Skill を警告表示（`ValidationIssue` モデル活用） | 🔴 高 |
| 1-3 | `scan` の検出結果から `init` 導線 | 検出結果を `~/.ai-adapter/` へ取り込む提案 | 🟡 中 |
| 1-4 | `doctor` の診断部分（読み取り専用） | ヘルスサマリー表示（更新可能・非互換の検出）。`agent_plugins.py` の `ValidationIssue` / severity パターンを統合（🟡4 反映） | 🟡 中 |

**テスト計画（フェーズ 1）**: 追加 40〜50 テスト。
- 1-1a〜d: `test_scan.py` 新設（各ツール検出の Unit 15 件・認証ファイル除外 5 件・統合表示 5 件）
- 1-2: 問題診断ロジック Unit 10 件（`ValidationIssue` 再利用）
- 1-4: doctor 診断 Unit 10 件
- **セキュリティテスト**: `~/.codex/auth.json` 等が scan 結果に含まれないことを確認するテストを必須化（🟡8 反映）

### フェーズ 2: Configure（v0.31〜v0.40）— 8 週間
**目的**: 「管理ツール」から「便利なツール」への転換。プリセットによる一括セットアップ。

| # | タスク | 期待する振る舞い | 優先度 |
|---|--------|-----------------|--------|
| 2-1 | **`ai-adapter setup <profile>`**（P0） | プロファイル（web-development 等）の推奨構成を提示・一括導入 | 🔴 高 |
| 2-2 | `setup` のプロファイル定義形式 | `profiles/` ディレクトリに YAML で定義（skills/mcp/agents/commands の集合） | 🔴 高 |
| 2-3 | `setup --dry-run` | 適用前に推奨構成のプレビュー（何が入るか） | 🟡 中 |
| 2-4 | Pack コンセプト導入（ローカル） | 複数プロファイルの組み合わせを 1 コマンドで適用 | 🟡 中 |
| 2-5 | `skill install <name>`（ローカル/リポジトリ） | 名前指定でスキルを取得・導入（Registry 準備段階。ローカルキャッシュ・GitHub リポジトリをソースに限定） | 🟡 中 |

**テスト計画（フェーズ 2）**: 追加 30〜40 テスト。
- 2-1/2-2: `test_setup.py` 新設（プロファイル適用の Integration 15 件・YAML パース Unit 10 件）
- 2-3: `--dry-run` が変更を加えないことを確認するテスト 5 件
- 2-5: skill install のソース解決 Unit 5 件

### フェーズ 3: Maintain（v0.41〜v0.50）— 8〜10 週間
**目的**: 環境を継続的に改善する「AI 環境の Dependabot」。

| # | タスク | 期待する振る舞い | 優先度 |
|---|--------|-----------------|--------|
| 3-1 | **`ai-adapter doctor`**（P0・フル） | ヘルスサマリー + 更新検出 + 互換性診断（1-4 の診断部分を拡張） | 🔴 高 |
| 3-2 | `doctor --fix` | 検出された問題の自動修正（更新・重複解消・設定統一）。**ローカル実行のみ無料** | 🔴 高 |
| 3-3 | `ai-adapter optimize`（診断） | 未使用 MCP・重複 Instruction・設定ドリフトの分析と改善提案 | 🟡 中 |
| 3-4 | `optimize --apply` | 提案の自動適用（複雑性低減の計測レポート付き）。**ローカル実行のみ無料** | 🟢 低 |
| 3-5 | バージョン追跡 | Skill/Plugin のバージョン管理（v1.3→v1.5 等の更新検出） | 🟡 中 |

**テスト計画（フェーズ 3）**: 追加 30〜40 テスト。
- 3-1/3-2: `test_doctor.py` 新設（診断 15 件・`--fix` の Integration 10 件・`ValidationIssue` 統合 5 件）
- 3-3/3-4: `test_optimize.py` 新設（診断 10 件・`--apply` 5 件）

### フェーズ 4: Cloud / Registry（v0.60+）— 3〜6 ヶ月
**目的**: 収益化の開始。バックアップ・復元・マルチデバイス同期。

| # | タスク | 期待する振る舞い | 優先度 |
|---|--------|-----------------|--------|
| 4-1a | **`ai-adapter cloud` — CLI 側** | バックアップ・復元・マルチデバイス同期の CLI インターフェース。**GitHub Sync を既定のバックアップ手段として位置付け**（`Config.remote` + `_run_git` 再利用）（🟡7 反映） | 🔴 高 |
| 4-1b | **Cloud サーバー側（API）** | 認証・環境スナップショット保存・復元 API（Pro 契約） | 🔴 高 |
| 4-2 | `ai-adapter login` | アカウント認証（OAuth） | 🔴 高 |
| 4-3 | Skill Registry（パブリック） | `skill search` で公開レジストリを横断検索・`skill install`（0-3 のローカル検索とは分離） | 🔴 高 |
| 4-4 | Pack Registry / Marketplace | プリセット（Next.js Pro 等）の公開・インストール | 🟡 中 |
| 4-5 | Multi-device sync | 複数 PC 間での自動同期（Cloud サーバー経由） | 🟡 中 |
| 4-6 | Web UI（構成ブラウザ） | 環境構成のブラウザ閲覧・管理 | 🟢 低 |

**テスト計画（フェーズ 4）**: 追加 20〜30 テスト（CLI 側）。サーバー側は別リポジトリ/サービスとして API テストを分離。

### フェーズ 5: Team / Enterprise（v1.0+）— 6〜12 ヶ月
**目的**: 組織向けガバナンス。企業収益の柱。

| # | タスク | 期待する振る舞い | 優先度 |
|---|--------|-----------------|--------|
| 5-1 | Team workspace | チーム共有の Skills/MCP/Environments 管理 | 🔴 高 |
| 5-2 | RBAC | ロール別権限制御 | 🔴 高 |
| 5-3 | Audit log | 設定変更履歴の記録・監査 | 🟡 中 |
| 5-4 | Organization policies | 組織ポリシー（利用必須 Skill 等）の強制 | 🟡 中 |
| 5-5 | SSO/SAML・SCIM | Enterprise 認証連携 | 🟢 低 |
| 5-6 | On-premise / Private registry | セルフホスト・社内専用レジストリ | 🟢 低 |

---

## 6. マネタイズ戦略

### 6.1 基本原則（🔴1 反映）

- **CLI 機能はすべて無料・無制限**。`scan` / `setup` / `doctor` / `optimize` のローカル実行は Free に含める
- 課金の境界は **「Cloud サービス」** に置く: クラウド同期・バックアップ・チーム共有・レジストリ・組織管理・サポート
- 「設定管理」ではなく **「AI 開発環境の再現性」** を売る（新しい PC で 5 分復元 / ツール移行で設定を失わない / チームで同一環境）

### 6.2 ティア構成

| 機能 | Free | Pro（参考 $10-20/月） | Team（参考 $20-40/user/月） | Enterprise（参考 $5,000-30,000/年） |
|------|:----:|:---------------------:|:---------------------------:|:-----------------------------------:|
| Local 管理（Agents/Skills/MCP/Prompts/Commands/Bins） | ✓ | ✓ | ✓ | ✓ |
| GitHub Sync | ✓ | ✓ | ✓ | ✓ |
| scan / setup / doctor / optimize（ローカル実行） | ✓ | ✓ | ✓ | ✓ |
| Cursor / Codex / OpenCode / OpenClaw / Plugin build-validate | ✓ | ✓ | ✓ | ✓ |
| Cloud backup / Multi-device sync / Version history | - | ✓ | ✓ | ✓ |
| Web UI / Skill marketplace（パブリック） | - | ✓ | ✓ | ✓ |
| Private registry / Team presets / Shared Skills-MCP | - | - | ✓ | ✓ |
| RBAC / Audit log / Organization policies | - | - | ✓ | ✓ |
| SSO/SAML / SCIM / On-premise / Support | - | - | - | ✓ |

**価格帯の位置付け（🟢9 反映）**: 上記の価格は**参考値**であり、競合調査（類似 Cloud サービスの価格・AI 設定管理市場の WTP）を実施した上で、**GitHub Star 1,000 到達前後**に確定する。それまでは Pro/Team/Enterprise の価格は未確定とする。

### 6.3 収益モデル（1 本化）

```
                    ai-adapter
                         │
              ┌──────────┴──────────┐
              │                     │
           OSS CLI              ai-adapter Cloud
              │                     │
          無料・無制限             有料（サーバーサービス）
              │                     │
      ┌───────┼───────┐       ┌────┼────┐
      │       │       │       │    │    │
    Skills   MCP    Agents   Sync Team Registry
                              │
                           Enterprise
```

---

## 7. マーケティング戦略

### 7.1 カテゴリー創造: 「AI dotfiles」
既存の dotfiles（vim/zsh/git/tmux）概念を AI に拡張し、**「AI development dotfiles」** というカテゴリーを自ら定義して繰り返し使用する。

```
.ai-adapter
    ↓
Claude / Codex / Cursor / OpenCode / MCP / Skills / Agents / Prompts
```

「AI の設定を Git 管理したい」→「ai-adapter」を想起させる。

### 7.2 競合の捉え方
真の競合は類似 CLI ではなく **「設定がバラバラになっている現状」**。

> **Stop managing AI agent configs one tool at a time.**

### 7.3 狙うキーワード
- AI agent configuration / Claude Code configuration / Codex configuration
- AGENTS.md management / MCP configuration manager / MCP server manager
- AI agent skills / Claude skills / Codex skills / OpenCode skills
- AI agent plugin / Agent Plugins / AI agent dotfiles / AI dotfiles

### 7.4 GitHub Star 成長戦略（100 → 1,000 → 10,000）
| 段階 | 施策 |
|------|------|
| 100→1,000 | README 刷新・Cursor 対応・`scan` リリース・Hacker News 投稿・Agent Plugins 1.0.0 コンプライアンス PR |
| 1,000→10,000 | Registry 公開・`setup` プリセット・コミュニティ Skill/Pack 投稿制度・チュートリアル記事群・YouTube/ブログ |

---

## 8. 既存ユーティリティ再利用マップ（🟢10 反映）

グランドデザインの各タスクが既存コードを再利用し、重複実装を防ぐための対応表。

| 新機能 | 再利用する既存資産 | 用途 |
|--------|-------------------|------|
| 0-2 Cursor 対応 | `mcp.py` の `--tool cursor` フィルタ・`--format openclaw` パターン・`skill.py` の get-all | 形式変換の土台。openclaw 実装を Cursor に水平展開 |
| 0-4 診断サマリー | `diff.py` の `compare_all` / `FileDiff` | 既存環境と `~/.ai-adapter/` の差分検出をそのまま集約 |
| 1-1 scan | `agent_format.py` の `parse_frontmatter`（L21）・`skill.py` の `_parse_skill_metadata`（L29） | frontmatter 解析・スキルメタデータ抽出（検出ロジック本体は新規実装） |
| 1-2 / 1-4 / 3-1 doctor | `agent_plugins.py` の `ValidationIssue` / severity パターン・`opencode.py` の `opencode_validate` | 診断結果の共通モデル。重複実装を防止（🟡4 反映） |
| 2-1/2-2 setup | `skill.py` / `mcp.py` / `agent.py` / `command.py` の add 系コマンド | プロファイル適用時に既存 add を呼び出す |
| 3-5 バージョン追跡 | `git.py` の `_run_git`（fan-in 16 の唯一の窓口） | リポジトリ操作は必ず `_run_git` 経由 |
| 4-1a cloud CLI | `sync.py` / `Config.remote` / `git.py` の `_run_git` | GitHub Sync を既定バックアップ手段として再利用（🟡7 反映） |

---

## 9. 成功指標（KPI）

### プロダクト指標
| 指標 | フェーズ 0→1 | フェーズ 2→3 | フェーズ 4+ |
|------|------------|------------|-----------|
| GitHub Stars | 100→1,000 | 1,000→5,000 | 5,000→10,000 |
| 週間インストール数（PyPI） | 立ち上げ | 成長 | 安定成長 |
| `scan` 実行ユーザー率 | - | 新規ユーザーの 50% | - |
| Cloud 登録（Pro トライアル） | - | - | 導入ユーザーの 10% |
| 有料転換率 | - | - | Pro 5% / Team 0.5% |

### 技術指標
- テスト数: 337 → 500+（scan/setup/doctor/optimize 追加分）
- CI カバレッジ維持、CCN < 20 維持（pre-commit ゲート）
- `uvx ai-adapter` 起動時間 < 2 秒
- テスト実行は必ず `scripts/run_tests.sh` 経由（sandbox 方式、`.github` 保護）（🟡5 反映）
- テストの cwd 隔離は `tests/conftest.py`（pytest プラグイン）が担う。`uv run pytest` を直接実行する場合は conftest.py の隔離に依存するため、`.github` を触るテストは常に run_tests.sh を推奨

---

## 10. リスクと対策

| リスク | 影響 | 対策 |
|--------|------|------|
| エコシステムの急速な変化（ツール形式の変更） | 対応コスト増 | Provider 層の抽象化（wiki の比較表を生かす）・形式変換の集中管理 |
| OSS 普及と収益化のバランス | コミュニティ離反 | CLI は永久無料を明言・Cloud は「再現性」という別価値 |
| Cursor/Continue 等のクローズドな形式 | 対応難 | 形式変換を `--format` で集中実装し、新形式は追加コスト低減 |
| 過剰機能による複雑化 | UX 低下 | 「Install→Discover→Configure→Maintain」の 4 段階を原則とし、checklist DoD で保護 |
| Agent Plugins 1.0.0 の標準競合 | 差別化困難 | 標準準拠を前提に「管理・同期・診断」の上位レイヤーで差別化 |
| scan による機密情報の露出 | セキュリティ事故 | 認証ファイルのブラックリスト（`auth.json` 等）・frontmatter のみ読み取り・scan 結果はメタデータ限定 |
| Cloud サーバーの運用コスト | 収益悪化 | GitHub Sync を既定手段としてサーバー依存を最小化・フェーズ 4 の後半に実装 |

---

## 11. 実装順序の根拠（プランナー P0/P1/P2 との整合）

| プランナー提言 | 本ロードマップ | 根拠 |
|--------------|--------------|------|
| P0: `scan` | フェーズ 1-1a〜1-1d | 新規ユーザーの入口・既存機能を束ねる体験（ツール単位に分割） |
| P0: `setup` | フェーズ 2-1 | 「管理」から「便利」への転換点 |
| P1: `cloud` | フェーズ 4-1a/4-1b | 課金の開始点（再現性の価値・サーバー/CLI を分離） |
| P1: Registry / Packs | フェーズ 2-4 / 4-3 | 「作る」から「インストールする」へ |
| P2: `doctor` / `optimize` | フェーズ 3 | 継続価値・Pro 差別化（ローカル実行は無料） |

**重要**: フェーズ 0（README 刷新・Cursor 対応一本化）を先行することで、OSS としての認知獲得と機能の「束ね直し」を同時に進める。

---

## 12. 次のアクション

1. [x] Plan Architect レビュー（🔴3 / 🟡5 / 🟢2 反映済み）
2. [ ] ユーザー承認（本グランドデザインの方向性・マネタイズ境界の確認）
3. [ ] 承認後: フェーズ 0 の BDD タスク分解（0-1 README 刷新を最初に）
4. [ ] Implementer 実装 → Reviewer 検収 → QA チェック（プロセスどおり）
