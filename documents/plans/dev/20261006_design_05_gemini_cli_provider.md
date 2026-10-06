# 設計書 05: Gemini CLI 新規 provider

- 日付: 2026-10-06
- 作成者: Product Manager
- 状態: ドラフト
- 上位計画: [platform_parity_master_design](./20261006_platform_parity_master_design.md)
- 優先度: P1
- 想定規模: 大（新規 provider + scan + CLI 統合）
- 依存: 設計書 01（User スコープ GEMINI.md）
- 外部仕様: context7 `/google-gemini/gemini-cli`（v0.39.1）

---

## 1. 目的

Gemini CLI への完全対応を提供する。現在は **provider なし・scan なし**で全ギャップ ❌。

### 対象ギャップ（全行）

| 行 | パス | カテゴリ |
|----|------|----------|
| 34 | `.gemini/commands/**/*.toml` | Command / Prompt (Project) |
| 35 | `~/.gemini/commands/**/*.toml` | Command / Prompt (User) |
| 36 | `.gemini/settings.json` | Core Config (Project) |
| 37 | `~/.gemini/settings.json` | Core Config (User) |
| 38 | `gemini-extension.json` | Extension |
| 39 | AGENTS.md / CONTEXT.md 任意名 | Instructions (Compatibility) |
| 40 | `GEMINI.md` | Instructions (Project) |
| 41 | `~/.gemini/GEMINI.md` | Instructions (User) |
| 42 | `.gemini/sandbox-macos-custom.sb` / `.gemini/sandbox.Dockerfile` | Sandbox（**非スコープ**: scan 検出のみ。生成はマスター非スコープ表に記載） |

---

## 2. 外部仕様サマリー（context7 で確認済み）

| 項目 | 仕様 |
|------|------|
| カスタムコマンド | `.gemini/commands/<name>.toml` → `/<name>`。ネストは `.gemini/commands/<dir>/<name>.toml` → `/<dir>:<name>` |
| TOML 形式 | `description = "..."` + `prompt = """..."""` |
| コンテキスト | `GEMINI.md`（プロジェクトルート + ディレクトリ階層 + ユーザー）。`context.fileName` で変更可 |
| Extension | `gemini-extension.json`（name, version, mcpServers, contextFileName, excludeTools, plan 等） |
| Settings | `.gemini/settings.json`（プロジェクト）/ `~/.gemini/settings.json`（ユーザー） |
| Sandbox | `.gemini/sandbox-macos-custom.sb` / `.gemini/sandbox.Dockerfile` |

---

## 3. アプローチ

### 3.1 新規 provider: `src/ai_adapter/providers/gemini.py`

```python
"""Gemini CLI provider integration.

Handles:
- Custom command export (.gemini/commands/**/*.toml)
- MCP export (settings.json mcpServers)
- Context file deployment (GEMINI.md)
- Extension manifest generation (gemini-extension.json)
- Scan detection
"""

def resolve_commands_path(scope: str, project_dir: Path | None = None) -> Path:
    """scope: 'project' → .gemini/commands/, 'user' → ~/.gemini/commands/"""

def resolve_settings_path(scope: str, project_dir: Path | None = None) -> Path:
    """scope: 'project' → .gemini/settings.json, 'user' → ~/.gemini/settings.json"""

def export_command_toml(command_name: str, content: str, description: str = "") -> str:
    """Convert a command/prompt to Gemini CLI TOML format."""

def export_mcp(servers: list[MCPServer]) -> dict:
    """Export MCP servers for Gemini settings.json mcpServers section."""

def merge_into_settings(path: Path, data: dict, force: bool = False) -> None:
    """Merge MCP servers into .gemini/settings.json."""

def deploy_context(content: str, scope: str, project_dir: Path | None = None, 
                  filename: str = "GEMINI.md", force: bool = False) -> Path:
    """Deploy context/instruction file as GEMINI.md."""

def generate_extension_manifest(
    name: str,
    description: str = "",
    mcp_servers: list[MCPServer] | None = None,
    context_file: str | None = None,
) -> dict:
    """Generate gemini-extension.json manifest."""

@gemini_group.command(...)
def gemini_install(): ...

@gemini_group.command(...)
def gemini_validate(): ...
```

### 3.2 CLI サブコマンド

```bash
# Gemini CLI グループ
ai-adapter gemini install
  # .gemini/ 配下に必要ファイルを配置
  # - settings.json（MCP セクション）
  # - commands/（登録済み command/prompt を TOML 変換）
  # - GEMINI.md（instructions をコンテキストとして配置）
  # - gemini-extension.json（--with-extension 指定時）

ai-adapter gemini install --scope user
  # ~/.gemini/ 配下に配置

ai-adapter gemini install --project-dir <path>
  # 指定ディレクトリに配置（デフォルト: cwd）

ai-adapter gemini install --with-extension
  # gemini-extension.json も生成

ai-adapter gemini validate
  # .gemini/settings.json, gemini-extension.json を検証

ai-adapter gemini uninstall
  # ai-adapter が生成したファイルを削除
```

### 3.3 既存コマンドへの format 追加

```bash
# command/prompt のデプロイ
ai-adapter command get <name> --format gemini
# → .gemini/commands/<name>.toml（Markdown → TOML 変換）

ai-adapter prompt get <name> --format gemini
# → .gemini/commands/<name>.toml

# MCP のエクスポート
ai-adapter mcp get --format gemini
# → .gemini/settings.json の mcpServers をマージ

# instructions のデプロイ
ai-adapter agent get <name> --format gemini
# → プロジェクトルート GEMINI.md として配置
```

### 3.4 Command → TOML 変換ロジック

既存の command は Markdown（`.github/commands/*.md`）。
Gemini CLI は TOML（`description` + `prompt`）。

**変換規則**:

```
# 入力: .github/commands/deploy.md
---
description: Deploy the application
---
# Deploy steps
1. Run tests
2. Build
3. Deploy to staging

# 出力: .gemini/commands/deploy.toml
description = "Deploy the application"

prompt = """
# Deploy steps
1. Run tests
2. Build
3. Deploy to staging
"""
```

- YAML frontmatter の `description` → TOML の `description`
- 本文 → TOML の `prompt`（triple-quoted string）
- ネスト command（`dir/name.md`）→ `.gemini/commands/dir/name.toml`
- **エスケープ規則（Plan Architect 指摘 M5-3）**: `prompt` が `"""` を含む場合は、`""\"` にエスケープするか、逐次エスケープ方式（`tomli_w` 使用）を採用する。末尾バックスラッシュも同様にエスケープする。

### 3.5 scan 拡張

```python
def scan_gemini(home: Path, project_dir: Path) -> list[ScanItem]:
    """Detect Gemini CLI configurations."""
    items = []
    # User
    gemini_dir = home / ".gemini"
    if gemini_dir.is_dir():
        # commands/**/*.toml
        for f in (gemini_dir / "commands").rglob("*.toml"):
            items.append(ScanItem("gemini", "command", f.stem, path=f))
        # settings.json
        settings = gemini_dir / "settings.json"
        if settings.is_file():
            items.append(ScanItem("gemini", "settings", "settings.json", path=settings))
            items.extend(_scan_mcp_servers("gemini", settings, ".gemini/settings.json"))
        # GEMINI.md
        context = gemini_dir / "GEMINI.md"
        if context.is_file():
            items.append(ScanItem("gemini", "instruction", "GEMINI.md", path=context))
    # Project
    proj_gemini = project_dir / ".gemini"
    if proj_gemini.is_dir():
        for f in (proj_gemini / "commands").rglob("*.toml"):
            items.append(ScanItem("gemini", "command", f.stem, path=f))
        settings = proj_gemini / "settings.json"
        if settings.is_file():
            items.append(ScanItem("gemini", "settings", "settings.json", path=settings))
            items.extend(_scan_mcp_servers("gemini", settings, ".gemini/settings.json"))
    # Extension manifests (installed under ~/.gemini/extensions/<name>/)
    extensions_dir = home / ".gemini" / "extensions"
    if extensions_dir.is_dir():
        for ext in extensions_dir.rglob("gemini-extension.json"):
            items.append(ScanItem("gemini", "settings", ext.parent.name, path=ext))
    # Project root GEMINI.md
    root_context = project_dir / "GEMINI.md"
    if root_context.is_file():
        items.append(ScanItem("gemini", "instruction", "GEMINI.md", path=root_context))
    return items
```

**TOOL_ORDER 更新（マスター設計 2.7 準拠）**: `gemini` のみを append（タプル全体の再定義を禁止）。
既存: `("claude", "codex", "cursor", "opencode", "project")` → 追加後: `("claude", "codex", "cursor", "opencode", "gemini", "project")`
**必須**: `TOOL_LABELS["gemini"]` へのラベル追加、`scan_all` への `items.extend(scan_gemini(...))` 登録。

---

## 4. BDD タスク分解

### タスク 05-1: `gemini install`（プロジェクトスコープ）

**期待する振る舞い**:
- 入力: `ai-adapter gemini install`（store に 3 command + 2 MCP + 1 instruction が登録済み）
- 応答: 以下を生成
  - `.gemini/settings.json`（mcpServers セクション）
  - `.gemini/commands/<name>.toml` × 3
  - `GEMINI.md`（instruction 内容）
- 入力: store が空
- 応答: 「Nothing to install.」（エラーにしない）

**受け入れ条件**:
- AC1: 生成物は Gemini CLI の形式に準拠（TOML パース可能）
- AC2: settings.json の mcpServers は `${ENV_KEY}` 形式
- AC3: 既存 `.gemini/settings.json` がある場合は merge（非管理キー preserve）
- AC4: 生成ファイルに `.gitignore` 登録（`add_to_gitignore`）

**データ（仕様例）**:
```
# store commands: deploy (Markdown), test (Markdown)
$ ai-adapter gemini install
Gemini CLI configuration installed:
  .gemini/settings.json
  .gemini/commands/deploy.toml
  .gemini/commands/test.toml
  GEMINI.md
```

---

### タスク 05-2: `gemini install --scope user`

**期待する振る舞い**:
- 入力: `ai-adapter gemini install --scope user`
- 応答: `~/.gemini/` 配下に配置
  - `~/.gemini/settings.json`
  - `~/.gemini/commands/<name>.toml`
  - `~/.gemini/GEMINI.md`

**受け入れ条件**:
- AC1: `~/.gemini/` が存在しない場合は作成
- AC2: User スコープの settings.json は既存ユーザー設定を preserve しながらマージ

---

### タスク 05-3: `gemini install --with-extension`（拡張マニフェスト生成）

**重要（Plan Architect 指摘 C5-1 反映）**: Gemini CLI の拡張は**プロジェクトルートの manifest を参照しない**。
正しい配置は `~/.gemini/extensions/<name>/gemini-extension.json` であり、
`gemini extensions install` で登録する必要がある。

**期待する振る舞い**:
- 入力: `ai-adapter gemini install --with-extension`
- 応答: `~/.gemini/extensions/<project-name>/gemini-extension.json` を生成
  - `name`: プロジェクト名（cwd のディレクトリ名）
  - `mcpServers`: store の MCP サーバー
  - `contextFileName`: "GEMINI.md"
  - **インストール手順を出力**: `gemini extensions install ~/.gemini/extensions/<name>`
- 入力: 既に同名ディレクトリが存在
- 応答: 確認プロンプト

**受け入れ条件**:
- AC1: manifest は Gemini CLI の仕様に準拠（`~/.gemini/extensions/<name>/` 配置）
- AC2: `${extensionPath}` プレースホルダは**公式どおり許容**する（portability のため推奨）。ai-adapter は MCP サーバーにパス解決を強制しない
- AC3: 生成後、`gemini extensions install` のインストール手順を出力
- AC4: プロジェクトルートには manifest を生成しない（Gemini が読まないため）

**データ（仕様例）**:
```
# ~/.gemini/extensions/my-project/gemini-extension.json
{
  "name": "my-project",
  "version": "1.0.0",
  "description": "Gemini CLI extension managed by ai-adapter",
  "mcpServers": {
    "managed-server": {
      "command": "npx",
      "args": ["-y", "mcp-x"]
    }
  },
  "contextFileName": "GEMINI.md"
}

# 出力メッセージ
Gemini extension manifest generated:
  ~/.gemini/extensions/my-project/gemini-extension.json
Install with: gemini extensions install ~/.gemini/extensions/my-project
```

---

### タスク 05-4: `command get --format gemini`

**期待する振る舞い**:
- 入力: `ai-adapter command get deploy --format gemini`
- 応答: `.gemini/commands/deploy.toml` を生成
  - Markdown frontmatter + body → TOML 変換
- 入力: Markdown に frontmatter がない
- 応答: body 全体を `prompt` に格納

**受け入れ条件**:
- AC1: TOML が `tomllib` でパース可能であることをテストで担保
- AC2: description が空の場合は空文字列
- AC3: ネスト command（`dir/name.md`）→ `.gemini/commands/dir/name.toml`

**データ（仕様例）**:
```toml
# 入力: command "refactor" (Markdown)
---
description: Refactor the provided code
---
Refactor the code into a pure function.

# 出力: .gemini/commands/refactor.toml
description = "Refactor the provided code"

prompt = """
Refactor the code into a pure function.
"""
```

---

### タスク 05-5: `mcp get --format gemini`

**期待する振る舞い**:
- 入力: `ai-adapter mcp get --format gemini`
- 応答: `.gemini/settings.json` の `mcpServers` をマージ
  - 既存非管理サーバーは preserve
- 入力: settings.json が存在しない
- 応答: 新規作成

**受け入れ条件**:
- AC1: Gemini settings.json の構造に準拠（mcpServers キー）
- AC2: `.bak` バックアップ
- AC3: 既存の model, theme, tools 等の設定を preserve

---

### タスク 05-6: `gemini validate`

**期待する振る舞い**:
- 入力: `ai-adapter gemini validate`
- 応答: 以下を検証
  - `.gemini/settings.json` の JSON パース + mcpServers 形式
  - `gemini-extension.json` の manifest 形式（存在時）
  - `.gemini/commands/**/*.toml` の TOML パース
- 入力: エラーなし
- 応答: 「Gemini CLI configuration is valid.」

**受け入れ条件**:
- AC1: `opencode validate` を参考にした UX（ただし `--json` は新設オプション）
- AC2: `--json` オプションで構造化出力（**新設**: opencode validate には `--json` は存在しないため）

---

### タスク 05-7: scan 拡張（gemini）

**期待する振る舞い**:
- 入力: `ai-adapter scan`（`.gemini/settings.json` + `commands/foo.toml` が存在）
- 応答: Gemini の settings と command を検出
- 入力: `~/.gemini/GEMINI.md` が存在
- 応答: User スコープの instruction として検出

**受け入れ条件**:
- AC1: `scan_gemini` が User + Project 両方を検出
- AC2: `TOOL_ORDER` に "gemini" を追加
- AC3: 既存 scan テストが全て通過

---

## 5. 変更対象ファイル

| ファイル | 変更内容 |
|----------|----------|
| `src/ai_adapter/providers/gemini.py` | **新規** provider |
| `src/ai_adapter/commands/mcp.py` | `--format gemini` 選択肢 |
| `src/ai_adapter/commands/command.py` | `--format gemini` 選択肢 |
| `src/ai_adapter/commands/prompt.py` | `--format gemini` 選択肢 |
| `src/ai_adapter/commands/instruction.py` | **変更なし**（`--format gemini` は設計書 01 で定義済み。provider の `deploy_context()` は `gemini install` 専用） |
| `src/ai_adapter/scan.py` | `scan_gemini` + TOOL_ORDER append + `SCAN_IGNORE_PATTERNS` 追加（`.gemini/*cred*`, `.gemini/*token*`） |
| `src/ai_adapter/commands/doctor.py` | gemini 設定の診断追加 |
| `src/ai_adapter/cli.py` | `gemini_group` 登録 |
| `tests/test_gemini.py` | **新規** |
| `tests/test_mcp.py` | format=gemini |
| `tests/test_command.py` | format=gemini |
| `tests/test_scan.py` | gemini 検出 |

---

## 6. テスト計画

```bash
bash scripts/run_tests.sh tests/test_gemini.py
bash scripts/run_tests.sh tests/test_mcp.py -k gemini
bash scripts/run_tests.sh tests/test_command.py -k gemini
bash scripts/run_tests.sh tests/test_scan.py -k gemini
```

### 主要テストケース

| # | ケース | 期待結果 |
|---|--------|----------|
| T1 | `gemini install`（プロジェクト） | 4 ファイル生成 |
| T2 | `gemini install --scope user` | `~/.gemini/` 配下に配置 |
| T3 | `gemini install --with-extension` | gemini-extension.json 生成 |
| T4 | `command get --format gemini`（frontmatter あり） | TOML 変換成功 |
| T5 | `command get --format gemini`（frontmatter なし） | body を prompt に |
| T6 | `mcp get --format gemini`（既存 settings） | preserve + merge |
| T7 | `gemini validate`（正常） | valid 判定 |
| T8 | `gemini validate`（TOML エラー） | エラー表示 |
| T9 | scan（.gemini/ 存在） | 検出 |
| T10 | scan（~/.gemini/GEMINI.md） | User instruction 検出 |
| T11 | TOML パース可能性 | tomllib で読み込み成功 |

---

## 7. リスクと対策

| リスク | 対策 |
|--------|------|
| Gemini CLI の仕様変更 | context7 の最新ドキュメントを参照。validate で形式検証 |
| TOML 変換のエッジケース | 変換は純関数として分離。パース可能性をテストで担保 |
| settings.json の非管理キー破壊 | merge は mcpServers のみ操作 |
| Extension manifest の形式変更 | validate で必須フィールドを検証 |

---

## 8. 完了定義

- [ ] `gemini install` が project/user 両方で動作
- [ ] `command get --format gemini` が TOML 変換
- [ ] `mcp get --format gemini` が settings.json をマージ
- [ ] `gemini validate` が設定を検証
- [ ] scan が Gemini CLI 設定を検出
- [ ] README の Supported Tools に Gemini CLI を追加
