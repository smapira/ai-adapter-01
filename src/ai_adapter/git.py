"""Git 操作ラッパーモジュール。

subprocess で git コマンドをラップする。
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional


class GitError(Exception):
    """Git 操作に関連するエラー。"""


def _run_git(
    args: list[str],
    cwd: Optional[Path] = None,
) -> subprocess.CompletedProcess:
    """git コマンドを実行する。

    Args:
        args: git サブコマンドの引数リスト。
        cwd: 作業ディレクトリ。None の場合はカレントディレクトリ。

    Returns:
        subprocess.CompletedProcess。

    Raises:
        GitError: コマンドが失敗した場合。
    """
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise GitError(
                f"git {' '.join(args)} 失敗:\n{result.stderr.strip()}"
            )
        return result
    except FileNotFoundError:
        raise GitError("git コマンドが見つかりません。Git がインストールされているか確認してください。")


def is_repo(path: Path) -> bool:
    """指定されたディレクトリが Git リポジトリか確認する。

    git rev-parse --git-dir で判断。
    """
    try:
        result = _run_git(["rev-parse", "--git-dir"], cwd=path)
        return result.returncode == 0
    except GitError:
        return False


def init_repo(path: Path) -> None:
    """Git リポジトリを初期化する。

    git init を実行する。
    """
    _run_git(["init"], cwd=path)


def has_remote(path: Path) -> bool:
    """リモートリポジトリが設定されているか確認する。"""
    try:
        result = _run_git(["remote", "-v"], cwd=path)
        return bool(result.stdout.strip())
    except GitError:
        return False


def add_all(path: Path) -> bool:
    """git add -A を実行する。

    Returns:
        ステージされた変更がある場合は True、ない場合は False。
    """
    _run_git(["add", "-A"], cwd=path)
    # 変更があるか確認
    result = _run_git(["diff", "--cached", "--quiet"], cwd=path)
    return result.returncode != 0


def commit(path: Path, message: str = "ai-adapter sync") -> None:
    """git commit を実行する。"""
    _run_git(["commit", "-m", message], cwd=path)


def pull_rebase(path: Path) -> None:
    """git pull --rebase origin main を実行する。"""
    try:
        _run_git(["pull", "--rebase", "origin", "main"], cwd=path)
    except GitError as e:
        # コンフリクト時は abort
        try:
            _run_git(["rebase", "--abort"], cwd=path)
        except GitError:
            pass
        raise GitError(
            f"pull --rebase に失敗しました。手動で解決してください:\n{e}"
        )


def push(path: Path) -> None:
    """git push origin main を実行する。"""
    _run_git(["push", "origin", "main"], cwd=path)


def get_remotes(path: Path) -> list[str]:
    """リモートリポジトリ一覧を取得する。"""
    result = _run_git(["remote"], cwd=path)
    return [r.strip() for r in result.stdout.strip().split("\n") if r.strip()]


def clone(url: str, dest: Path) -> None:
    """git clone を実行する。"""
    _run_git(["clone", url, str(dest.name)], cwd=dest.parent)


def add_remote(path: Path, name: str, url: str) -> None:
    """git remote add を実行する。"""
    _run_git(["remote", "add", name, url], cwd=path)


def get_current_branch(path: Path) -> str:
    """現在のブランチ名を取得する。"""
    result = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=path)
    return result.stdout.strip()
