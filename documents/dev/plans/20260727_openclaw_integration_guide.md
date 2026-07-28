# OpenClaw 対応 開発者向け指示書

**作成日**: 2026-07-27
**対象読者**: Implementer, Plan Architect, Reviewer
**ゴール**: `ai-adapter` に OpenClaw サポートを追加し、`.github/` を単一真実源として OpenClaw 環境へデプロイできるようにする

---

## 現状分析

### OpenClaw の設定構造

OpenClaw は `~/.openclaw/openclaw.json` を中心とした設定体系を持つ:

| 領域 | OpenClaw のパス | ai-adapter のパス |
|------|----------------|-------------------|
| エージェント指示 | `~/.openclaw/workspace/AGENTS.md` + `SOUL.md` + `TOOLS.md` | `.github/agents/*.agent.md` |
| スキル | `~/.openclaw/skills/<name>/SKILL.md` | `.github/skills/<name>/SKILL.md` |
| MCP サーバー | `openclaw.json` → `mcp.servers` (配列形式) | `.mcp.json` (オブジェクト形式) |
| 設定ファイル | `~/.openclaw/openclaw.json` | `~/.ai-adapter/config.json` |

### 共通点 (ブリッジしやすい部分)

1. **MCP**: 両者とも MCP サーバーを管理する。形式の変換のみで対応可能
2. **SKILL.md**: 両者とも `SKILL.md` 形式。配置先の変換のみ
3. **Markdown 指示ファイル**: OpenClaw は AGENTS.md, SOUL.md — 内容は ai-adapter の agent.md と互換性あり

---

## 実装フェーズ

優先度順に6フェーズで進める。各フェーズは独立してリリース可能。

---

## Phase 0: 事前調査・環境把握

**目的**: OpenClaw の設定構造をコードベースで理解し、テスト対象を明確にする

### やること

1. `~/.openclaw/openclaw.json` の全セクションを読む
2. `~/.openclaw/workspace/` の全ファイルを読む
3. スキルディレクトリ構造を確認 (`~/.openclaw/skills/*/SKILL.md`)
4. OpenClaw npm パッケージのドキュメントを確認 (`docs/concepts/`, `docs/tools/`)

### 確認コマンド

```bash
# 設定ファイル
cat ~/.openclaw/openclaw.json | python3 -m json.tool | head -80

# ワークスペースファイル
ls -la ~/.openclaw/workspace/

# スキル一覧
ls ~/.openclaw/skills/

# バンドルスキル数
ls ~/.openclaw/tools/node-v24.15.0/lib/node_modules/openclaw/dist/skills/ | wc -l
```

### 完了条件

- [ ] OpenClaw の MCP 設定構造 (配列形式) を理解した
- [ ] OpenClaw のワークスペースファイルの役割を理解した
- [ ] スキルの3層構造 (workspace / user / bundled) を理解した

---

## Phase 1: MCP 書き出し対応 (openclaw形式)

**目的**: `ai-adapter mcp get --format openclaw` で OpenClaw 形式の MCP 設定を出力できるようにする

### 背景

OpenClaw の `openclaw.json` 内 MCP 設定は以下の配列形式:

```json
{
  "mcp": {
    "servers": [
      {
        "enabled": true,
        "name": "codebase-memory-mcp",
        "command": "/Users/bookair18/.local/bin/codebase-memory-mcp",
        "args": ["--project", "ai-adapter-01"],
        "env": {}
      }
    ]
  }
}
```

標準 `.mcp.json` はオブジェクト形式:

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-github"],
      "env": { "GITHUB_TOKEN": "${GITHUB_TOKEN}" }
    }
  }
}
```

### 実装手順

#### Step 1: MCP エクスポート関数に `--tool openclaw` オプション追加

**対象ファイル**: `src/ai_adapter/mcp.py`

```python
@click.option("--tool", "-t", "tool_name",
              type=click.Choice(["standard", "opencode", "openclaw"]),
              default="standard",
              help="Output format (standard=.mcp.json, openclaw=openclaw.json section)")
@click.option("--path", default=None, help="Output directory")
def mcp_get(tool_name, path):
    # ...
```

**追加する出力形式**:

```python
def _export_openclaw_mcp(servers: list[MCPServer]) -> dict:
    """Export MCP servers in OpenClaw format (array under mcp.servers)."""
    return {
        "mcp": {
            "servers": [
                {
                    "enabled": s.enabled,
                    "name": s.name,
                    "command": s.command,
                    "args": list(s.args),
                    "env": {k: f"${{{k}}}" for k in s.env_keys},
                }
                for s in servers
            ]
        }
    }
```

#### Step 2: 出力先の違いに対応

- standard: カレントディレクトリの `.mcp.json` に出力
- openclaw: `~/.openclaw/openclaw.json` にマージ (または `--openclaw-config` で指定)

マージ戦略: `openclaw.json` の既存 `mcp.servers` と、ai-adapter の MCP サーバーを統合する。同名のサーバーは上書き。

#### Step 3: テスト

**対象ファイル**: `tests/test_mcp.py`

テストケース:
- normal: 標準MCP → OpenClaw形式の変換が正しいこと
- edge: `env_keys`, `args` が空の場合の出力
- edge: `enabled=False` のサーバーの扱い (出力に含めない / `"enabled": false` を含める)

```python
def test_export_openclaw_format():
    servers = [
        MCPServer(
            name="github", command="npx", args=["@modelcontextprotocol/server-github"], env_keys=["GITHUB_TOKEN"]
        ),
    ]
    result = _export_openclaw_mcp(servers)
    assert result["mcp"]["servers"][0]["name"] == "github"
    assert result["mcp"]["servers"][0]["enabled"] is True
    assert result["mcp"]["servers"][0]["env"] == {"GITHUB_TOKEN": "${GITHUB_TOKEN}"}
```

### 完了条件

- [ ] `ai-adapter mcp get --tool openclaw` で OpenClaw 形式の MCP 設定を出力できる
- [ ] マージ先パスを `--openclaw-config` で指定可能 (デフォルトは `~/.openclaw/openclaw.json`)
- [ ] 既存の `--tool standard` が後方互換性を保っている
- [ ] 全テストが通る

---

## Phase 2: MCP 読み取り対応 (openclaw からのインポート)

**目的**: OpenClaw の `openclaw.json` から MCP 設定を `ai-adapter` にインポートできるようにする

### 実装手順

#### Step 1: MCP インポート関数に `--from openclaw` オプション追加

**対象ファイル**: `src/ai_adapter/mcp.py`

```python
@click.option("--from", "from_format",
              type=click.Choice(["standard", "opencode", "openclaw"]),
              default="standard",
              help="Source format for import")
```

**追加する読み取り関数**:

```python
def _import_openclaw_mcp(config, config_path: str) -> None:
    """Import MCP servers from an OpenClaw openclaw.json."""
    from ai_adapter.models import MCPServer

    with open(config_path) as f:
        data = json.load(f)

    servers_data = data.get("mcp", {}).get("servers", [])
    if not servers_data:
        click.echo(f"No MCP servers found in '{config_path}'", err=True)
        return

    loaded = 0
    skipped = 0
    for server_data in servers_data:
        name = server_data.get("name")
        if not name:
            continue

        # Duplicate check
        if any(s.name == name for s in config.mcp_servers):
            skipped += 1
            continue

        server = MCPServer(
            name=name,
            command=server_data.get("command", ""),
            args=server_data.get("args", []),
            env_keys=list(server_data.get("env", {}).keys()),
            enabled=server_data.get("enabled", True),
            tools=[],
        )
        config.mcp_servers.append(server)
        loaded += 1

    _config.save_config(config)
    click.echo(f"OpenClaw MCP imported: {loaded} added, {skipped} skipped (duplicate)")
```

### 完了条件

- [ ] `ai-adapter mcp add --file ~/.openclaw/openclaw.json --from openclaw` でインポート可能
- [ ] 重複チェックが正しく動作する
- [ ] 全テストが通る

---

## Phase 3: スキル書き出し対応 (openclaw 用)

**目的**: `ai-adapter skill get-all --tool openclaw` でスキルを `~/.openclaw/skills/` にデプロイできるようにする

### 背景

OpenClaw のスキル配置先:
- User skills: `~/.openclaw/skills/<name>/SKILL.md`
- Workspace skills: `~/.openclaw/workspace/skills/<name>/SKILL.md` (プロジェクト固有の場合)

ai-adapter のスキル配置先:
- `.github/skills/<name>/SKILL.md`

### 実装手順

#### Step 1: skill get-all に `--tool openclaw` オプション追加

**対象ファイル**: `src/ai_adapter/skill.py`

```python
@click.option("--tool", "-t", "tool_name",
              type=click.Choice(["standard", "openclaw"]),
              default="standard",
              help="Deploy target")
```

OpenClaw 向けデプロイ先:
- 通常: `~/.openclaw/skills/`
- プロジェクト固有: `~/.openclaw/workspace/skills/` (ワークスペースパスは `openclaw.json` から取得)

```python
def _get_openclaw_skills_dir() -> Path:
    """Return the OpenClaw skills directory (~/.openclaw/skills/)."""
    return Path.home() / ".openclaw" / "skills"


def _deploy_skill_to_openclaw(skill_entry, src_dir) -> bool:
    """Deploy a skill to ~/.openclaw/skills/<name>/."""
    dest = _get_openclaw_skills_dir() / skill_entry.name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src_dir, dest)
    return True
```

#### Step 2: 既存スキルとの重複を考慮

OpenClaw には既に52のバンドルスキルが存在する。同名のスキルをデプロイする場合:
- ユーザースキル (`~/.openclaw/skills/`) はバンドルスキルより優先されるため、上書きで問題ない
- ただし確認プロンプトを出す (`--force` でスキップ)

#### Step 3: テスト

```python
def test_deploy_skill_to_openclaw():
    # テスト用の一時ディレクトリで実施
    with tempfile.TemporaryDirectory() as tmp:
        skill_src = Path(tmp) / "my-skill"
        skill_src.mkdir()
        (skill_src / "SKILL.md").write_text("# My Skill")
        
        # ... deploy and verify
```

### 完了条件

- [ ] `ai-adapter skill get-all --tool openclaw` で全スキルを `~/.openclaw/skills/` にデプロイ可能
- [ ] 同名スキルがある場合の確認プロンプトが動作する
- [ ] 既存の `--tool standard` が後方互換性を保っている

---

## Phase 4: エージェント指示ファイル書き出し

**目的**: `ai-adapter agent get-all --tool openclaw` でエージェントファイルを OpenClaw ワークスペースにデプロイできるようにする

### 背景

OpenClaw のワークスペース構造:
```
~/.openclaw/workspace/
├── AGENTS.md    # 動作指示・ルール（← ai-adapter の agent.md を統合）
├── SOUL.md      # ペルソナ・トーン・境界
├── USER.md      # ユーザー情報
└── TOOLS.md     # ローカルツールメモ
```

ai-adapter の `.github/agents/*.agent.md` は AGENTS.md にマージする形が適切。

ただし、OpenClaw には `agents.list[].workspace` でエージェント別ワークスペースを設定できる機能があるため、複数エージェントを個別ワークスペースに振り分けることも可能。

### 実装手順

#### Step 1: agent ファイル結合 → AGENTS.md 変換

**対象ファイル**: `src/ai_adapter/agent.py` (新規関数)

```python
def _merge_agents_to_openclaw_workspace(agents_dir: Path, workspace_dir: Path) -> None:
    """Merge all .agent.md files into OpenClaw workspace AGENTS.md.

    Preserves YAML frontmatter as Markdown headings and appends content
    in order. Each agent becomes a section with its name as H2.
    """
    agent_files = sorted(agents_dir.glob("*.agent.md"))
    if not agent_files:
        return

    lines = ["# Agent Instructions", "", "> Auto-generated by ai-adapter. Do not edit manually.", "", "---", ""]

    for f in agent_files:
        # Parse frontmatter to get agent name
        fm = parse_frontmatter(f)
        agent_name = fm.get("name", f.stem)
        content = _strip_frontmatter(f.read_text())

        lines.append(f"## {agent_name}")
        lines.append("")
        lines.append(content)
        lines.append("")
        lines.append("---")
        lines.append("")

    workspace_dir.mkdir(parents=True, exist_ok=True)
    (workspace_dir / "AGENTS.md").write_text("\n".join(lines))
```

#### Step 2: `agent get-all` に `--tool openclaw` オプション追加

```python
@click.option("--tool", "-t", "tool_name",
              type=click.Choice(["standard", "openclaw"]),
              default="standard",
              help="Deploy target")
```

#### Step 3: ワークスペースパスの解決

OpenClaw のデフォルトワークスペースパスは `~/.openclaw/workspace/`。  
`openclaw.json` の `agents.defaults.workspace` または `agents.list[].workspace` で上書き可能。

```python
def _get_openclaw_workspace_dir(config_path: str | None = None) -> Path:
    """Resolve the OpenClaw workspace directory from openclaw.json or default."""
    path = config_path or os.path.expanduser("~/.openclaw/openclaw.json")
    try:
        with open(path) as f:
            data = json.load(f)
        ws = data.get("agents", {}).get("defaults", {}).get("workspace")
        if ws:
            return Path(ws)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return Path.home() / ".openclaw" / "workspace"
```

### 完了条件

- [ ] `ai-adapter agent get-all --tool openclaw` で AGENTS.md に全エージェントを統合出力
- [ ] ワークスペースパスが正しく解決される
- [ ] YAML frontmatter が欠落せず保持される
- [ ] 後方互換性を維持

---

## Phase 5: OpenClaw CLI サブコマンド追加

**目的**: `ai-adapter openclaw` サブコマンドで OpenClaw 統合を一元管理する

### 実装イメージ

`opencode.py` を参考に `openclaw.py` を作成:

```
ai-adapter openclaw
├── install      # openclaw.json を生成（.github の設定を参照）
├── uninstall    # openclaw.json の ai-adapter セクションを削除
├── alias        # ~/.openclaw/skills/ → .github/skills/ のシンボリックリンク
├── status       # OpenClaw との同期状態を表示
└── validate     # エージェントファイルの形式を検証
```

### ファイル構成

**新規ファイル**: `src/ai_adapter/openclaw.py`

テンプレート:

```python
"""openclaw subcommand implementation.

Manages OpenClaw integration: config generation, workspace sync, skill deploy.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import click

from ai_adapter import config as _config


@click.group(name="openclaw")
def openclaw_group() -> None:
    """Manage OpenClaw integration settings."""


@openclaw_group.command(name="install")
@click.option("--config-path", default=None, help="Path to openclaw.json (default: ~/.openclaw/openclaw.json)")
@click.option("--dry-run", is_flag=True, help="Show what would be done without making changes")
def openclaw_install(config_path: str | None, dry_run: bool) -> None:
    """Generate/update OpenClaw configuration referencing .github/ settings.

    Updates openclaw.json to include:
    - MCP servers from ai-adapter config
    - Skill paths pointing to .github/skills/
    - Agent workspace instructions
    """
    # ... implementation
    click.echo("OpenClaw configuration updated.")


@openclaw_group.command(name="uninstall")
@click.option("--config-path", default=None, help="Path to openclaw.json")
def openclaw_uninstall(config_path: str | None) -> None:
    """Remove ai-adapter managed sections from openclaw.json."""
    # Make a backup and remove ai-adapter managed keys
    click.echo("OpenClaw configuration cleaned.")


@openclaw_group.command(name="alias")
def openclaw_alias() -> None:
    """Create .opencode symlink for OpenClaw opencode-go compatibility.

    OpenClaw uses opencode-go as a model provider. This alias ensures
    .opencode/ is available for OpenClaw's opencode-go integration.
    """
    # Same logic as opencode alias
    github_path = Path.cwd().resolve() / ".github"
    opencode_path = Path.cwd().resolve() / ".opencode"

    if not github_path.exists():
        click.echo("'.github' directory not found.", err=True)
        raise click.ClickException(".github directory does not exist.")

    # ... create symlink (same as opencode.py)
    click.echo(f"Symlink created: {opencode_path} -> {github_path}")


@openclaw_group.command(name="status")
@click.option("--config-path", default=None, help="Path to openclaw.json")
def openclaw_status(config_path: str | None) -> None:
    """Show OpenClaw sync status."""
    click.echo("OpenClaw Integration Status:")
    click.echo("=" * 40)

    openclaw_dir = Path.home() / ".openclaw"
    if not openclaw_dir.exists():
        click.echo("  OpenClaw not installed (~/.openclaw/ not found)")
        return

    # Check MCP sync
    # Check skill sync
    # Check agent sync

    click.echo("  MCP servers: ...")
    click.echo("  Skills: ...")
    click.echo("  Agent workspace: ...")
```

### CLI 統合

**対象ファイル**: `src/ai_adapter/cli.py`

```python
from ai_adapter.openclaw import openclaw_group

# Register subcommand group
main.add_command(openclaw_group)
```

### テスト

**新規ファイル**: `tests/test_openclaw.py`

```python
import json
import tempfile
from pathlib import Path
from click.testing import CliRunner
from ai_adapter.cli import main


class TestOpenclawCommands:
    def test_install_dry_run(self):
        runner = CliRunner()
        result = runner.invoke(main, ["openclaw", "install", "--dry-run"])
        assert result.exit_code == 0
        assert "OpenClaw" in result.output

    def test_alias(self):
        # ... test symlink creation
        pass
```

### 完了条件

- [ ] `ai-adapter openclaw install` が期待通り動作する
- [ ] `ai-adapter openclaw uninstall` が安全に元に戻せる
- [ ] `ai-adapter openclaw status` が同期状態を表示する
- [ ] `ai-adapter openclaw validate` が正しく検証する
- [ ] 全テストが通る

---

## Phase 6: Diff・Status 対応

**目的**: `ai-adapter status` で OpenClaw との差分も表示できるようにする

### 実装手順

#### Step 1: OpenClaw カテゴリの diff 関数追加

**対象ファイル**: `src/ai_adapter/diff.py`

```python
def compare_openclaw(project_dir: Path | None = None) -> CategoryDiff:
    """Compare ~/.ai-adapter/ with ~/.openclaw/ for synced items."""
    from ai_adapter import config as _config

    config = _config.load_config()

    openclaw_dir = Path.home() / ".openclaw"
    diffs: list[FileDiff] = []

    # 1. MCP servers diff
    openclaw_mcp_names = _get_openclaw_mcp_servers(openclaw_dir)
    ai_mcp_names = {s.name for s in config.mcp_servers if s.enabled} if config else set()
    for name in sorted(ai_mcp_names | openclaw_mcp_names):
        in_ai = name in ai_mcp_names
        in_openclaw = name in openclaw_mcp_names
        if in_ai and in_openclaw:
            diffs.append(FileDiff(name=f"mcp/{name}", status="up-to-date", rel_path=f"mcp/{name}"))
        elif in_ai and not in_openclaw:
            diffs.append(FileDiff(name=f"mcp/{name}", status="added", rel_path=f"mcp/{name}"))
        else:
            diffs.append(FileDiff(name=f"mcp/{name}", status="orphaned", rel_path=f"mcp/{name}"))

    # 2. Skills diff
    # ...

    # 3. Agent workspace diff
    # ...

    return CategoryDiff("openclaw", _config.AI_ADAPTER_DIR, openclaw_dir, diffs)
```

#### Step 2: `compare_all()` に OpenClaw を追加

```python
def compare_all(project_dir: Path | None = None) -> list[CategoryDiff]:
    return [
        compare_agents(project_dir),
        compare_bins(project_dir),
        compare_skills(project_dir),
        compare_commands(project_dir),
        compare_prompts(project_dir),
        compare_mcp(project_dir),
        compare_openclaw(project_dir),  # ← 追加
    ]
```

### 完了条件

- [ ] `ai-adapter status` に OpenClaw セクションが表示される
- [ ] MCP・スキル・エージェントの差分が正しく検出される

---

## アーキテクチャ設計判断

### 1. 新規ファイル vs 既存ファイル修正

| 判断 | 理由 |
|------|------|
| `src/ai_adapter/openclaw.py` を新規作成 | opencode.py と対称性を保つ。責務が明確 |
| `mcp.py` に `--tool openclaw` オプション追加 | MCP のコアロジックは同じ。出力形式だけ変える |
| `skill.py` に `--tool openclaw` オプション追加 | 同上 |
| `agent.py` に openclaw 向け統合関数追加 | マージロジックは新規だが、agent.py 内に収める |

### 2. 設定のマージ戦略

`openclaw.json` を直接編集する場合のルール:

1. 初回インストール時: `openclaw.json` のバックアップを `.bak` に作成
2. ai-adapter が管理するキーは `mcp.servers` のみ（スキルはファイルシステム、エージェントはワークスペースファイル）
3. 既存の `mcp.servers` は上書きせず、ai-adapter 管理外のサーバーは維持
4. アンインストール時: バックアップからリストア、または ai-adapter が追加したエントリのみ削除

### 3. スキーママーカー

OpenClaw が ai-adapter で管理された設定を識別できるように、openclaw.json にマーカーを追加:

```json
{
  "x-ai-adapter": {
    "version": 1,
    "managed_servers": ["github", "codebase-memory-mcp"]
  },
  "mcp": {
    "servers": [...]
  }
}
```

### 4. エラーハンドリング方針

| シナリオ | 対応 |
|---------|------|
| `~/.openclaw/` が存在しない | 「OpenClaw がインストールされていません。`npm install -g openclaw` を実行してください」と表示 |
| `openclaw.json` がパースエラー | エラー内容を表示し、バックアップから復元するオプションを提示 |
| ワークスペースディレクトリが存在しない | 作成して続行 (`mkdir -p`) |
| スキルコピー中に権限エラー | エラーを表示し、そのスキルをスキップして続行 |

---

## テスト計画

### 単体テスト (Unit)

| テスト | 対象 | 内容 |
|--------|------|------|
| `test_export_openclaw_mcp` | `mcp.py` | 標準MCP→OpenClaw形式変換の正しさ |
| `test_import_openclaw_mcp` | `mcp.py` | OpenClaw→標準MCP変換の正しさ |
| `test_merge_agents_to_workspace` | `agent.py` | 複数 agent.md → 単一AGENTS.md の結合 |
| `test_get_openclaw_workspace_dir` | `agent.py` | パス解決の優先順位 |
| `test_deploy_skill_to_openclaw` | `skill.py` | スキルデプロイの正しさ |

### 統合テスト (Integration)

| テスト | 内容 |
|--------|------|
| `test_openclaw_install` | 全カテゴリを1回の install でデプロイ |
| `test_openclaw_uninstall` | 変更を元に戻せること |
| `test_status_openclaw_sync` | 同期状態が正しく表示されること |

### エッジケース

| ケース | 確認事項 |
|--------|---------|
| OpenClaw 未インストール | 適切なエラーメッセージ |
| openclaw.json が空 | デフォルト値で初期化 |
| 同名スキル・同名MCPサーバー | 重複チェックが動作 |
| 日本語を含む frontmatter | エンコーディング問題が起きない |
| 巨大な agent.md ファイル | メモリ問題が起きない |

---

## リリース判断基準

各フェーズのリリース可否は以下を満たすこと:

1. ✅ 全テストが通る (新規 + 既存)
2. ✅ 後方互換性が保たれている (既存の --tool standard が従来通り動作)
3. ✅ `--help` に適切なヘルプテキストが表示される
4. ✅ エラーメッセージがユーザーフレンドリー
5. ✅ Linter/type checker が通る (`ruff check`, `mypy`)

---

## 参考リンク

- OpenClaw GitHub: https://github.com/openclaw/openclaw
- OpenClaw Docs: https://docs.openclaw.ai
- OpenClaw 設定比較表: https://github.com/smapira/ai-adapter-01/wiki/LLM-Tool-Specification-Comparison
- 既存 opencode.py: `src/ai_adapter/opencode.py`
- 既存 MCP モジュール: `src/ai_adapter/mcp.py`
- 既存 diff モジュール: `src/ai_adapter/diff.py`
