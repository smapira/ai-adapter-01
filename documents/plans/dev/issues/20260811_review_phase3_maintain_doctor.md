# フェーズ 3 計画レビュー（Maintain: `doctor` フル + `--fix` + `optimize` + バージョン追跡）

## 優先度
🟡 中（🔴 なし / 🟡 3 / 🟢 3）

## 対象
- 計画書: `documents/plans/dev/20260811_phase3_maintain_doctor.md`

## 指摘事項

### 🟡 3-1: severity の記述不整合 — `ValidationIssue` は error/warning のみで info が存在しない

§2.1 は「`agent_plugins.py` の `ValidationIssue`（severity: error/warning/info）を共通モデルとして利用」と書くが、実装（agent_plugins.py L51-63）は error/warning のみ（`__str__` は error 以外を全て WARN 表示）。doctor / optimize の提案（「更新可能」「互換性警告」）は info レベルの発行が自然で、フェーズ 1 の 1-2 / 1-4 と同じモデルを共有する。

**改善案**:
- `ValidationIssue` に `"info"` を追加する拡張を計画に明記し、**フェーズ 1 で実施して本フェーズに持ち越さない**（`__str__` のラベル分岐も追加。既存呼び出しは後方互換）。
- 拡張しない場合は §2.1 / §3 の記述を「error/warning」に統一。

### 🟡 3-2: バックアップ場所 `~/.ai-adapter/backups/` は git 同期リポジトリを汚染する

§2.2 / §4 は修正前スナップショットを `~/.ai-adapter/backups/{timestamp}/` に保存するとするが、`~/.ai-adapter/` は GitHub Sync（`sync.py` / `Config.remote`）の管理下にある git リポジトリ。バックアップを置くと:
- `ai-adapter sync` / `get-all-rec` のデプロイ対象やコミットに混入し、リポジトリが肥大化する
- `doctor --fix` が認証情報を含む設定を修正した場合、バックアップに機密情報が残り、同期で外部に漏れるリスクがある

**改善案**:
- バックアップディレクトリを同期対象外にする:
  - `config.py` の `add_to_gitignore`（L181、実在確認済み）で `~/.ai-adapter/.gitignore` に `backups/` を追加する、または
  - `~/.ai-adapter-backups/` など管理ディレクトリ外に配置する
- バックアップに認証情報が含まれ得ることを §7 リスク表に明記し、保存前に機密ファイルを除外する方針（`SCAN_IGNORE_PATTERNS` 相当）を検討

### 🟡 3-3: バージョン追跡の「更新元ソース」が未定義 — `Skill` モデルに version / source フィールドが存在しない

3-5 は「バージョン情報は frontmatter（`version` フィールド）を正とする」「最新版は GitHub タグから」とするが、`models.py` の `Skill`（L93）は name / description / path / tags / env のみで version・source を持たない。`VersionInfo.source`（比較元 GitHub tag）の出所が定義されていない。

なお frontmatter パース自体は `_parse_skill_metadata`（skill.py L29、yaml.safe_load で任意キーを返す）で `version` / `repository` を読み取れることは確認済み。

**改善案**:
- SKILL.md frontmatter の `version:` / `repository:` キーを正とし、config モデルは拡張せず**読み取り時に frontmatter から取得**する方針を AC に明記する（Agent Plugins の `PLUGIN_MANIFEST_FIELDS` にも `repository` が存在し規約として親和性あり）
- `repository` キーが無い Skill は「更新元不明（latest 判定対象外）」として扱う旨も明記

### 🟢 3-4: 3-3 の「未使用 MCP」判定基準が未定義

「`mcp list` のサーバーがどの Skill/Agent からも参照されていない」という判定は、モデルに Skill → MCP の参照関係が存在しないため成立条件が不明。

**改善案**: 判定基準を明確化する（例: SKILL.md frontmatter の `mcp:` キーで宣言する規約を導入、または「`~/.ai-adapter/` 配下の全ファイルでサーバー名が一度も出現しない」という明確なヒューリスティックに限定）。

### 🟢 3-5: `ai-adapter version` 新設の cli.py 登録・既存 `--version` との関係が未記載

3-5 は新トップレベルコマンド `ai-adapter version` を計画するが、cli.py には既に `@click.version_option`（L41、`ai-adapter --version`）が存在し、`main.add_command` 群（L325-337）への登録・スモークテストの記載がない。

**改善案**: 受け入れ条件に「`cli.py` への `add_command` 登録と CLI スモークテスト」を明記し、`--version` オプションとの棲み分け（`--version` = パッケージ版、`version` = 管理下 Skill/Plugin の一覧）を定義する。

### 🟢 3-6: 3-2 の「更新」はフェーズ 2 の `skill install`（2-5）に依存する

`doctor --fix` の「更新可能な Skill を最新版に更新」は、ソースからの再取得が必要で、フェーズ 2 の 2-5（`skill install` のソース解決）に依存する。実装順序（§8）は 3-5 → 3-1 → 3-2 だが、依存関係の明記がない。

**改善案**: §8 に「3-2 の更新系は 2-5 のソース解決（git clone / frontmatter repository キー）に依存」を注記する。

## 備考
コードベース参照（`ValidationIssue` L51、`Skill` モデル L93、`_parse_skill_metadata` L29、`compare_all` diff.py L202、`_run_git` git.py L17、`add_to_gitignore` config.py L181、`PLUGIN_MANIFEST_FIELDS` の repository、`--version` cli.py L41）はすべて実在確認済み。安全性の設計（`--dry-run` デフォルト・破壊的修正の確認必須・バックアップ・`_run_git` 経由の git 操作）は妥当。🟡3 件（severity 統一・バックアップの同期汚染・更新元ソース定義）の修正を条件に承認可能。

## 判定
修正必要（軽微）— 🟡3 件の修正を条件に承認可
