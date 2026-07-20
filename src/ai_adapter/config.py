"""設定ファイル管理モジュール。

~/.ai-adapter/config.yaml の読み書き・バリデーションを担当する。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml

from ai_adapter.models import Config, Env

AI_ADAPTER_DIR = Path.home() / ".ai-adapter"


def get_config_path() -> Path:
    """設定ファイルのパスを返す。

    環境変数 AI_ADAPTER_CONFIG で上書き可能。
    """
    env = os.environ.get("AI_ADAPTER_CONFIG")
    if env:
        return Path(env)
    return AI_ADAPTER_DIR / "config.yaml"


def get_agents_dir() -> Path:
    """~/.ai-adapter/agents/ を返す。"""
    return AI_ADAPTER_DIR / "agents"


def get_bins_dir() -> Path:
    """~/.ai-adapter/bin/ を返す。"""
    return AI_ADAPTER_DIR / "bin"


def get_github_agents_dir() -> Path:
    """カレントプロジェクトの .github/agents/ を返す。"""
    return Path.cwd() / ".github" / "agents"


def get_github_bins_dir() -> Path:
    """カレントプロジェクトの .github/bin/ を返す。"""
    return Path.cwd() / ".github" / "bin"


def init() -> bool:
    """~/.ai-adapter/ ディレクトリを初期化する。

    Returns:
        新規作成された場合は True、既存の場合は False。
    """
    dirs = [
        AI_ADAPTER_DIR,
        AI_ADAPTER_DIR / "agents",
        AI_ADAPTER_DIR / "bin",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    config_path = get_config_path()
    if config_path.exists():
        return False

    config = Config(
        version=1,
        default_env="default",
        envs=[
            Env(name="default", description="デフォルト環境"),
        ],
        agent_bindings=[],
    )
    save_config(config)
    return True


def load_config() -> Optional[Config]:
    """設定ファイルを読み込む。

    Returns:
        設定が見つかれば Config オブジェクト、見つからなければ None。
    """
    config_path = get_config_path()
    if not config_path.exists():
        return None

    with open(config_path, "r") as f:
        data = yaml.safe_load(f)

    if data is None:
        return None

    return Config.from_dict(data)


def save_config(config: Config) -> None:
    """設定ファイルを保存する。"""
    config_path = get_config_path()
    with open(config_path, "w") as f:
        yaml.dump(
            config.to_dict(),
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )
