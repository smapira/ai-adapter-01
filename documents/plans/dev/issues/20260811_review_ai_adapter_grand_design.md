# ai-adapter グランドデザイン & ロードマップ レビュー

## 優先度
🔴 高（修正必要 — マネタイズ戦略の内部矛盾・タスク粒度・セキュリティ考慮の欠落）

## 判定
**修正必要（方向性は承認）** — ポジショニング・UX 4 段階・フェーズ構成の骨格は妥当。ただし以下の指摘を反映した上で、フェーズ 0 の BDD タスク分解に進むこと。特に 🔴 1（マネタイズ矛盾）と 🔴 4（scan のセキュリティ）は着手前に要判断。

## 対象
- 計画書: `documents/plans/dev/20260811_ai_adapter_grand_design.md`
- 関連ファイル:
  - `src/ai_adapter/diff.py`（compare_all / FileDiff — scan・診断サマリーの基盤）
  - `src/ai_adapter/commands/add_all_rec.py`（.github/ 取り込み — scan の参照実装）
  - `src/ai_adapter/providers/opencode.py`（_validate_* 群 — doctor の診断パターン）
  - `src/ai_adapter/agent_plugins.py`（ValidationIssue / severity — 診断結果モデル）
  - `src/ai_adapter/commands/skill.py`（_parse_skill_metadata / search — scan・setup の基盤）
  - `src/ai_adapter/commands/mcp.py`（--tool フィルタ vscode/claude/cursor — Cursor 対応の土台）
  - `src/ai_adapter/git.py`（_run_git 集約 — cloud の唯一の git 窓口）
  - `src/ai_adapter/models.py`（Config.remote — cloud との関係）

---

## 指摘事項

### 1. 🔴 OSS「無料・無制限」と Pro の `doctor --fix` / `optimize --apply` 有料化が矛盾

**問題**:
計画書 L20・L259-261 は「OSS CLI は無料・無制限」と宣言しているが、マネタイズ表（L246）では `doctor --fix` / `optimize --apply`（自動改善）が **Pro のみ** となっている。CLI のコア機能に課金ゲートを設けると「無料・無制限」のポジショニングが崩れ、OSS コミュニティの反発を招く。プランナー提言「OSS CLI 無料 + Cloud/Registry で収益化」とも整合しない。

**改善案**:
- 課金境界を「CLI 機能」ではなく「**クラウドサービス**」に置く: ローカルの `doctor --fix`・`optimize --apply` は無料、Pro は「Cloud backup / Multi-device sync / Version history / Web UI / Skill marketplace」に限定
- どうしても自動改善を Pro 価値とするなら、「自動改善は Cloud アカウント認証後（クラウド上の知識ベースと連携する場合）にのみ有効」と機能の線引きを明確化し、ローカル単体では無料であることを明記
- マネタイズ表の該当行（L246）を修正し、OSS CLI 無料の原則と表の整合を取る

---

### 2. 🔴 `scan`（1-1）のタスク粒度が過大 — BDD の振る舞い単位で分割されていない

**問題**:
1-1「既存 AI 設定（Claude/Codex/Cursor/OpenCode/MCP/AGENTS.md）を検出・可視化」は **6 系統 × 複数カテゴリ** の検出を 1 タスクに含む。現実の環境では `~/.claude/skills/`（17 スキル）、`~/.codex/`、`~/.config/opencode/`、`~/.cursor/` がそれぞれ別形式・別ディレクトリ構成であり、1 タスクでは実装・テストともに破綻する。

**改善案**:
- 検出をツール単位で分割: **1-1a** Claude Code 検出（`~/.claude/skills/`・`~/.claude/.mcp.json`）、**1-1b** OpenCode 検出（`~/.config/opencode/opencode.json*`）、**1-1c** Codex 検出（`~/.codex/`・AGENTS.md）、**1-1d** Cursor / MCP / AGENTS.md 検出
- 実装は既存の `providers/` 構造（opencode.py / openclaw.py / codex.py）に倣い `src/ai_adapter/providers/` 配下に検出モジュールを新設し、`scan` はそれらの集約表示のみ担当
- 各タスクに「入力: 当該ディレクトリに設定が存在 / 応答: 検出一覧」の BDD シナリオを明記

---

### 3. 🔴 Cursor 対応がフェーズ 0（0-2）とフェーズ 1（1-5）に分散し一貫性がない

**問題**:
0-2 は `skill get-all --format cursor`（skills のみ）、1-5 は「Cursor 対応の完成（mcp + agent 含む）」で、同じ機能群が 2 フェーズにまたがる。README の「対応ツール図」（0-1）に Cursor を掲載するなら、部分対応のまま記載するのはミスリード。また `mcp.py` には既に `--tool vscode/claude/cursor` フィルタ（L27・L62）が存在し、Cursor 対応の土台が一部あることを計画書が考慮していない。

**改善案**:
- Cursor 対応は 1 エピックとして **フェーズ 0 に一本化**（skills + mcp + agent）し、0-1 の README 刷新と同時に完了させる
- 実装は `--format openclaw` のパターン（skill.py L375-381・openclaw.py）を踏襲し、`providers/cursor.py` に形式変換（SKILL.md → `.cursor/rules/*.mdc`、frontmatter の `description`/`globs` へのマッピング）を集中実装
- フェーズ 1-5 は削除し、テスト（.mdc 生成・globs 反映）をフェーズ 0 に含める

---

### 4. 🟡 `doctor` と既存 validate 群の関係が未定義 — 重複実装リスク

**問題**:
既存に `opencode validate`（opencode.py の `_validate_opencode_config`・`_validate_*` 群）と `plugin validate`（agent_plugins.py の `validate_plugin_package` / `ValidationIssue` / severity）がある。1-4・3-1 の `doctor` がこれらを包含するのか独立するのか不明で、診断ロジックの重複実装（または車輪の再発明）が発生する。

**改善案**:
- `doctor` は `agent_plugins.py` の `ValidationIssue`（severity: error/warning）を共通の診断結果モデルとして再利用し、`doctor --check opencode` / `--check plugin` のように既存 validate をサブチェックとして統合する
- 診断ルールの定義場所（`providers/` ごとのバリデータ or 中央のヘルスチェックモジュール）を計画に明記する

---

### 5. 🟡 テスト計画が欠落 — 各タスクのテスト種別・追加数が不明

**問題**:
計画書にタスク別のテスト計画がない。「337 → 400+」（L316）という数値目標のみ。プロジェクト規約（AGENTS.md）では `scripts/run_tests.sh` 経由のテスト実行・pre-commit ゲート（337 テスト・CCN < 20・ruff）が義務で、新規コマンドはこれを通す必要がある。

**改善案**:
- 各タスクに「テスト種別 + 追加数」を明記: scan/setup/doctor は `test_cli.py` の CliRunner ベース機能テスト（正常系・異常系・エッジケース）と、診断ロジックのユニットテストに分ける
- `scan` は外部ディレクトリ（`~/.claude/` 等）をスキャンするため、`tests/conftest.py` の cwd 隔離パターンを利用した tmp ディレクトリでのテスト必須（実ホームディレクトリをスキャンしないこと）
- 技術指標の「400+」をフェーズ 1 時点の目安として具体化（例: フェーズ 0: +15、フェーズ 1: +50）

---

### 6. 🟡 `skill search` の「パブリック候補」（0-3）がフェーズ 4 の Registry（4-3）と重複

**問題**:
0-3 は「ローカル + パブリック候補」とあるが、パブリック検索はフェーズ 4-3（Skill Registry）の一部。フェーズ 0 でパブリックを実装すると、Registry API が未定義のままスコープが拡大する。

**改善案**:
- 0-3 はローカル検索の強化（タグ OR 検索・部分一致の改善・出力フォーマットの `--json` 追加）に限定
- パブリック検索は 4-3 で Registry API と同時に実装し、0-3 のスコープから除外する

---

### 7. 🟡 `cloud`（4-1）のスコープと GitHub Sync との関係が不明確

**問題**:
「バックアップ・別 PC での 1 発復元」にはサーバーサイド（バックエンド API・認証・ストレージ）が必要で、CLI 単体では完結しない。既存の GitHub Sync（`Config.remote` + `git.py _run_git` 集約 + `sync.py`）が既に「バックアップ + 復元」を実現しており、cloud との差分（自動同期・バージョン履歴・Web UI）が計画書から読み取れない。

**改善案**:
- フェーズ 4 を「**CLI 側**（cloud コマンドのインターフェース + バックエンド API 契約 / OpenAPI 仕様）」「**サーバー側**（バックエンド実装）」に分割
- CLI 側は既存の `git.py _run_git` 集約と `Config.remote` を拡張し、GitHub Sync をプライベートバックアップの既定手段として残す（cloud はその上位レイヤー）
- マルチデバイス自動同期（4-5）は GitHub Sync の pull/push 自動化として実装可能なことを計画に明記し、独自バックエンドの必要性を再評価する

---

### 8. 🟡 `scan` のセキュリティ考慮が欠落 — 秘匿情報の取り扱い

**問題**:
`scan` の対象ディレクトリには秘匿情報が含まれる。実環境では `~/.codex/auth.json`（認証情報）、`~/.claude/` 内の設定・キャッシュ、MCP サーバーの env_keys に API キー参照がある。`scan` がファイル内容を表示・出力する場合、認証情報が漏れるリスクがある。

**改善案**:
- `scan` は**ファイル名・メタデータ（frontmatter）のみを扱い、本文・認証情報を含むファイル（auth.json / config.toml 等）の内容は表示しない**方針を計画に明記
- スキャン対象から除外するパス（`auth.json`・`*.json.bak`・`node_modules/`・`cache/` 等）のブラックリストを定義
- `cloud` の OAuth トークン（4-2）は keyring / 環境変数で管理し、`config.json` に平文保存しない設計を併記

---

### 9. 🟢 マネタイズ価格帯の根拠が不明

**問題**:
Pro $10-20/月・Team $20-40/user/月・Enterprise $5,000-30,000/年（L238）の根拠（競合比較・コスト構造）がなく、フェーズ 4 未実装の段階での試算。Star 100 段階での確定は時期尚早。

**改善案**:
- 競合（MCP manager・dotfiles 管理・git-sync 系ツール）の価格調査を Researcher に依頼し、価格帯の裏付けを取る
- Star 1,000 到達前は価格決定を保留し、計画書には「参考価格帯（要調査）」と明記する

---

### 10. 🟢 既存ユーティリティの再利用マップが計画書にない

**問題**:
計画書に各タスクが活用すべき既存モジュールの対応表がない。Implementer が車輪の再発明をするリスクがある。実際には以下が再利用可能:

| 計画タスク | 再利用すべき既存資産 |
|-----------|---------------------|
| 0-4 診断サマリー | `diff.py` の `compare_all` / `FileDiff`（status: up-to-date/added/modified/orphaned/missing_source）をそのまま集約 |
| 1-1/1-2 scan 検出・診断 | `add_all_rec.py` の `_import_*`（検出パターン）、`skill.py` の `_parse_skill_metadata`、`agent_format.py` の `parse_frontmatter` |
| 1-4/3-1 doctor | `agent_plugins.py` の `ValidationIssue` / severity、`opencode.py` の `_validate_*` 群 |
| 2-1/2-2 setup | `config.py` の `resolve_env` / `get_*_dir`、`skill.py` の `skill_add_rec`（一括登録） |
| 0-2/1-5 Cursor | `skill.py` の `--format openclaw` パターン、`mcp.py` の `--tool` フィルタ |
| 4-1 cloud | `git.py` の `_run_git` 集約（fan-in 16 の唯一の窓口）、`sync.py` |

**改善案**:
- 計画書 §3 レイヤー構造に「既存資産マップ」の列を追加し、各タスクが参照するモジュールを明記する
- 新規 `providers/` モジュール（cursor.py / scan 検出）は既存の opencode.py / openclaw.py の構造（変換関数 + バリデーションの分離）に合わせる

---

## 備考

- フェーズ 0〜5 全体（12 ヶ月以上）のグランドデザインとしての骨格は妥当。プランナー提言（P0 scan/setup・P1 cloud・P2 doctor）との整合も取れている（§10）
- 🔴 1（マネタイズ矛盾）はマーケティング上のポジショニングに直結するため、ユーザー承認の前に方針確定を推奨
- フェーズ 0 の BDD タスク分解（次のアクション 2）は、本レビューの指摘反映後に進めること
