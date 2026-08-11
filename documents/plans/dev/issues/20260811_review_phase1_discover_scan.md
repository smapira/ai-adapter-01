# フェーズ 1 計画レビュー（Discover: `ai-adapter scan` + 問題診断 + init 導線 + doctor 診断部）

## 優先度
🟡 中（🔴 なし / 🟡 3 / 🟢 3）

## 対象
- 計画書: `documents/plans/dev/20260811_phase1_discover_scan.md`

## 指摘事項

### 🟡 1-1: 再利用マップの前提誤り — `get_all_rec.py` に環境検出ロジックは存在しない / `opencode.py` に `~/.config/opencode/` のパス解決は存在しない

計画 §6 は「1-1a〜c | `get_all_rec.py` の検出ロジック・`config.py` の `get_config_path` — 環境検出の起点」および「1-1b | `providers/opencode.py` のパス解決 — `~/.config/opencode/` 検出」と記述するが、コードベース実態は以下:

- `commands/get_all_rec.py` は `~/.ai-adapter/` → プロジェクト `.github/` への**デプロイ**コマンド（`cmd_get_all_rec`、`_deploy_*` 群）。`~/.claude/` 等のツール設定ディレクトリを走査するロジックは**存在しない**（フェーズ 0 レビュー 🟡0-1 と同じ誤認の再発）。
- `providers/opencode.py` は cwd の `opencode.json` 生成（`opencode_install`）と検証（`_validate_opencode_config`）のみで、`~/.config/opencode/opencode.json`（グローバル設定）を解決するコードは**存在しない**。

scan の 1-1a〜c は実質**新規の検出ロジック**であり、「既存資産を再利用して実装」という前提が成立しない。

**改善案**:
- 再利用マップを以下に修正する:
  - 1-1a〜c: `agent_format.parse_frontmatter`（L21）と `commands/skill.py` の `_parse_skill_metadata`（L29）— frontmatter の name/description/tags 抽出を流用。検出ロジック自体は `scan.py` に新規実装と明記
  - 1-1b: `opencode.py` の `_validate_opencode_config`（L270）は 1-2 の診断（opencode.json のスキーマ検証）に流用可能。`~/.config/opencode/` の検出は新規
- 計画 §2.1 / §6 の「環境検出の起点」という表現を削除し、「新規検出 + frontmatter パース再利用」に書き換える

### 🟡 1-2: severity の記述不整合 — `ValidationIssue` は error/warning のみで info が存在しない

タスク 1-2 の AC1 は「severity: error/warning/info」と書くが、§4 では「severity: error/warning」、実装は `agent_plugins.py` L51-63 でデフォルト `"error"`・コメントも `"error" or "warning"` のみ（`__str__` は error 以外を全て WARN 表示）。計画内でも記述が割れており、モデルとも一致しない。

**改善案**:
- 診断に info レベルの提案（doctor / optimize で必要）を含めるなら、`ValidationIssue` に `"info"` を追加する拡張を計画に明記する（`__str__` のラベル分岐も追加。後方互換で既存呼び出しは影響なし）。
- 拡張しない場合は、計画の AC1・§2.2・§4 の記述を「error/warning」に統一する。
- フェーズ 3 の `doctor` / `optimize` も同じモデルを使うため、info 拡張はフェーズ 1 で実施しフェーズ 3 に持ち越さないこと（共通修正）。

### 🟡 1-3: テスト隔離の不足 — scan は `Path.home()` 配下を読むが conftest は cwd のみ隔離

`tests/conftest.py` は `Path.cwd()` のみ隔離し、`Path.home()` は隔離しない。scan の検出対象（`~/.claude/` `~/.codex/` `~/.cursor/` `~/.config/opencode/`）はすべて HOME 配下のため、テストが `Path.home()` をパッチしないと**開発者実機の `~/.codex/auth.json` 等を読み込む**事故が起きる。計画 §5 のテスト計画は「tmp_path 使用・実ディレクトリ作成」のみで HOME パッチに触れていない。

既存テストは全ファイルで setUp/tearDown による `pathlib.Path.home = staticmethod(...)` パッチを確立している（例: `tests/test_skill.py` L39-40, `tests/test_cli.py` L41-42）。

**改善案**:
- 計画 §5 に「scan テストは既存パターンに倣い `Path.home()` を tmp_path にパッチ（setUp/tearDown）」を**必須条件**として明記する
- `scan.py` の実装方針として、パス解決をモジュール定数（`HOME = Path.home() / ".claude"` 等）でなく**実行時**に `Path.home()` から解決することを AC に追加（config.py の `AI_ADAPTER_DIR` がモジュール定数でテスト時に再代入される既存パターンと整合させる）

### 🟢 1-4: `--max-depth` がリスク表にのみ記載され BDD/AC に存在しない

§7 リスク対策に「深さ制限（デフォルト 2 レベル）・`--max-depth` オプション」とあるが、タスク 1-1a〜d の BDD・受け入れ条件にオプション定義がない。

**改善案**: 1-1c（プロジェクト検出）または 1-1d（統合表示）の AC に「`--max-depth`（デフォルト 2）で走査深さを制限」を追加する。

### 🟢 1-5: 「古い Skill」診断（1-2）のデータソースが未定義

1-2 の「⚠ 古い Skill（`update_date` が閾値より古い or バージョン差分）」について、`update_date` の出所が定義されていない。SKILL.md frontmatter に `update_date` の規約は存在せず、ファイル mtime はローカル環境依存。バージョン差分はフェーズ 3 の 3-5 が担当する。

**改善案**: 1-2 の「古い Skill」判定を以下のいずれかに限定して明記する:
- frontmatter の `update_date`（任意キー。`_parse_skill_metadata` は yaml.safe_load で任意キーを返すため読み取り可能）
- または「バージョン差分は 3-5 に先送りし、1-2 では重複 MCP と設定不一致のみ」にスコープ縮小

### 🟢 1-6: タスク 1-3 の取り込み — `add_all_rec.py` のソースは `.github/` であり検出ディレクトリではない

AC2「取り込みは既存の `add_all_rec` / 登録ロジックを再利用」は、`add_all_rec.py` が `.github/` 配下をソースとする（L180: `github_dir = Path.cwd() / ".github"`）点で部分的にしか成立しない。`~/.claude/` 等の検出ディレクトリからの取り込みは新規コードが必要。

**改善案**: 「`add_all_rec.py` の『コピー + config 登録 + save_config』パターン（`_import_skills` 等）を参照し、ソースを検出ディレクトリに置き換えて新規実装」と明記する。

## 備考
コードベース参照（`ValidationIssue` L51、`_parse_skill_metadata` L29、`parse_frontmatter` agent_format.py L21、conftest の cwd 隔離、既存テストの HOME パッチパターン）はすべて実在確認済み。セキュリティ原則（ブラックリスト定数 `SCAN_IGNORE_PATTERNS` 一元定義・frontmatter のみ読み取り・必須セキュリティテスト）は妥当。🟡1-1〜1-3 の修正（再利用マップの正確化・severity 記述統一・HOME 隔離の明記）を条件に承認可能。

## 判定
修正必要（軽微）— 🟡3 件の修正を条件に承認可
