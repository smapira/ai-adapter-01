"""mcp サブコマンドの実装。

~/.ai-adapter/mcp/ 配下の MCP サーバー設定を管理する。
各ツール（VS Code / Claude / Cursor）の形式で設定を出力する。
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from ai_adapter import config as _config
from ai_adapter.models import MCPServer


def _get_output_path(tool: str) -> str:
    """ツール名に対応する出力パスを返す。"""
    paths = {
        "vscode": ".vscode/mcp.json",
        "claude": ".mcp.json",
        "cursor": ".cursor/mcp.json",
    }
    return paths.get(tool, "")


@click.group(name="mcp")
def mcp_group() -> None:
    """MCP サーバー設定を管理する。"""


@mcp_group.command(name="list")
@click.option("--tool", help="ツール名でフィルタ（vscode/claude/cursor）")
@click.option("--env", help="環境名でフィルタ")
def mcp_list(tool: str | None, env: str | None) -> None:
    """MCP サーバー一覧を表示する。"""
    config = _config.load_config()
    if config is None:
        click.echo("設定ファイルが見つかりません。ai-adapter init を実行してください。")
        return

    servers = config.mcp_servers
    if tool:
        servers = [s for s in servers if tool in s.tools]
    if env:
        servers = [s for s in servers if s.env is None or s.env == env]

    if not servers:
        click.echo("登録済みの MCP サーバーはありません。")
        return

    click.echo("MCP サーバー一覧:")
    click.echo("-" * 70)
    for s in servers:
        enabled_mark = "✓" if s.enabled else "✗"
        tools_str = f" [{', '.join(s.tools)}]" if s.tools else ""
        env_str = f" (env: {s.env})" if s.env else ""
        click.echo(f"  {enabled_mark} {s.name}{tools_str}{env_str}")
        click.echo(f"     command: {s.command} {' '.join(s.args)}")


@mcp_group.command(name="add")
@click.argument("name")
@click.option("--command", "-c", help="実行コマンド")
@click.option("--args", "-a", multiple=True, help="コマンド引数（複数指定可）")
@click.option("--env-key", "-e", multiple=True, help="必要な環境変数キー（複数指定可）")
@click.option("--tool", "-t", multiple=True, help="対応ツール（vscode/claude/cursor、複数指定可）")
@click.option("--env", help="有効環境")
@click.option("--file", "json_file", type=click.Path(exists=True, readable=True),
              help="JSON 設定ファイルから追加")
def mcp_add(
    name: str,
    command: str | None,
    args: tuple[str, ...],
    env_key: tuple[str, ...],
    tool: tuple[str, ...],
    env: str | None,
    json_file: str | None,
) -> None:
    """MCP サーバー設定を追加する。

    NAME: MCP サーバー名。

    JSON ファイルからの追加: --file オプションで JSON 設定ファイルを指定。
    対話的追加: --command, --args, --env-key, --tool オプションで指定。
    """
    config = _config.load_config()
    if config is None:
        click.echo("設定ファイルが見つかりません。ai-adapter init を実行してください。")
        return

    # 重複チェック
    for existing in config.mcp_servers:
        if existing.name == name:
            click.echo(f"MCP サーバー '{name}' は既に存在します。", err=True)
            raise click.ClickException(f"MCP サーバー '{name}' は既に登録されています。")

    if json_file:
        # JSON ファイルから読み込み
        with open(json_file) as f:
            data = json.load(f)

        server_data = data.get("mcpServers", {}).get(name, data)
        server = MCPServer(
            name=name,
            command=server_data.get("command", ""),
            args=server_data.get("args", []),
            env_keys=list(server_data.get("env_keys", server_data.get("env", {}).keys())),
            enabled=server_data.get("enabled", True),
            tools=server_data.get("tools", []),
            env=server_data.get("env"),
        )
    else:
        if not command:
            click.echo("--command は必須です。", err=True)
            raise click.ClickException("--command オプションが必要です。")
        server = MCPServer(
            name=name,
            command=command,
            args=list(args),
            env_keys=list(env_key),
            enabled=True,
            tools=list(tool) if tool else ["vscode", "claude", "cursor"],
            env=env,
        )

    config.mcp_servers.append(server)
    _config.save_config(config)
    click.echo(f"MCP サーバー '{name}' を追加しました。")


@mcp_group.command(name="remove")
@click.argument("name")
def mcp_remove(name: str) -> None:
    """MCP サーバー設定を削除する。

    NAME: 削除する MCP サーバー名。
    """
    config = _config.load_config()
    if config is None:
        click.echo("設定ファイルが見つかりません。ai-adapter init を実行してください。")
        return

    found = None
    for s in config.mcp_servers:
        if s.name == name:
            found = s
            break

    if found is None:
        click.echo(f"MCP サーバー '{name}' は登録されていません。", err=True)
        raise click.ClickException(f"MCP サーバー '{name}' が見つかりません。")

    config.mcp_servers.remove(found)
    _config.save_config(config)
    click.echo(f"MCP サーバー '{name}' を削除しました。")


@mcp_group.command(name="export")
@click.option("--path", required=True,
              type=click.Choice(["vscode", "claude", "cursor"], case_sensitive=False),
              help="出力先ツール")
def mcp_export(path: str) -> None:
    """MCP 設定を各ツールの形式で出力する。"""
    config = _config.load_config()
    if config is None:
        click.echo("設定ファイルが見つかりません。ai-adapter init を実行してください。")
        return

    enabled_servers = [s for s in config.mcp_servers if s.enabled]

    mcp_config: dict = {"mcpServers": {}}
    for server in enabled_servers:
        if path not in server.tools:
            continue

        env_dict = {}
        for key in server.env_keys:
            env_dict[key] = f"${{{key}}}"

        entry: dict = {
            "command": server.command,
            "args": server.args,
        }
        if env_dict:
            entry["env"] = env_dict

        mcp_config["mcpServers"][server.name] = entry

    output_path = Path.cwd() / _get_output_path(path)
    if not output_path:
        click.echo(f"不明なツール: {path}", err=True)
        raise click.ClickException(f"ツール '{path}' の出力先が未定義です。")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(mcp_config, f, indent=2, ensure_ascii=False)

    click.echo(f"MCP 設定を出力しました: {output_path}")


@mcp_group.command(name="enable")
@click.argument("name")
def mcp_enable(name: str) -> None:
    """MCP サーバーを有効化する。

    NAME: 有効化する MCP サーバー名。
    """
    config = _config.load_config()
    if config is None:
        click.echo("設定ファイルが見つかりません。ai-adapter init を実行してください。")
        return

    for s in config.mcp_servers:
        if s.name == name:
            s.enabled = True
            _config.save_config(config)
            click.echo(f"MCP サーバー '{name}' を有効化しました。")
            return

    click.echo(f"MCP サーバー '{name}' は登録されていません。", err=True)
    raise click.ClickException(f"MCP サーバー '{name}' が見つかりません。")


@mcp_group.command(name="disable")
@click.argument("name")
def mcp_disable(name: str) -> None:
    """MCP サーバーを無効化する。

    NAME: 無効化する MCP サーバー名。
    """
    config = _config.load_config()
    if config is None:
        click.echo("設定ファイルが見つかりません。ai-adapter init を実行してください。")
        return

    for s in config.mcp_servers:
        if s.name == name:
            s.enabled = False
            _config.save_config(config)
            click.echo(f"MCP サーバー '{name}' を無効化しました。")
            return

    click.echo(f"MCP サーバー '{name}' は登録されていません。", err=True)
    raise click.ClickException(f"MCP サーバー '{name}' が見つかりません。")
