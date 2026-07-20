"""opencode サブコマンドの実装。

.opencode シンボリックリンクの管理と opencode.json のインストール/アンインストールを行う。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import click

from ai_adapter import config as _config


def _get_opencode_config() -> dict:
    """opencode.json の設定内容を生成する。

    ~/.ai-adapter/mcp/servers.json の内容を元に、opencode 形式の hooks 設定を生成する。
    """
    config = _config.load_config()
    mcp_config: dict = {"hooks": {}}

    if config is None:
        return mcp_config

    for server in config.mcp_servers:
        if not server.enabled:
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

        mcp_config["hooks"][server.name] = entry

    return mcp_config


@click.group(name="opencode")
def opencode_group() -> None:
    """OpenCode 連携設定を管理する。"""


@opencode_group.command(name="alias")
def opencode_alias() -> None:
    """カレントディレクトリに .opencode → .github のシンボリックリンクを作成する。

    .github/ ディレクトリへの絶対パスのシンボリックリンクを .opencode として作成する。
    """
    github_path = Path.cwd().resolve() / ".github"
    opencode_path = Path.cwd().resolve() / ".opencode"

    if not github_path.exists():
        click.echo(f"'.github' ディレクトリが見つかりません: {github_path}", err=True)
        raise click.ClickException(".github ディレクトリが存在しません。")

    if opencode_path.exists() or opencode_path.is_symlink():
        click.echo(f"'.opencode' は既に存在します。")
        click.confirm("置き換えますか？", abort=True)
        if opencode_path.is_symlink() or opencode_path.is_dir():
            import shutil
            if opencode_path.is_symlink() or opencode_path.is_file():
                opencode_path.unlink()
            else:
                shutil.rmtree(opencode_path)

    os.symlink(str(github_path), str(opencode_path))
    click.echo(f"シンボリックリンクを作成しました: {opencode_path} → {github_path}")


@opencode_group.command(name="install")
def opencode_install() -> None:
    """opencode.json をカレントディレクトリに生成する。"""
    mcp_config = _get_opencode_config()
    output_path = Path.cwd() / "opencode.json"

    with open(output_path, "w") as f:
        json.dump(mcp_config, f, indent=2, ensure_ascii=False)

    click.echo(f"opencode.json を生成しました: {output_path}")


@opencode_group.command(name="uninstall")
def opencode_uninstall() -> None:
    """カレントディレクトリの opencode.json を削除する。"""
    output_path = Path.cwd() / "opencode.json"

    if not output_path.exists():
        click.echo("opencode.json が見つかりません。")
        return

    output_path.unlink()
    click.echo(f"opencode.json を削除しました: {output_path}")
