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
    # git diff --cached --quiet は変更ありのとき exit code 1 を返す（正常）
    try:
        _run_git(["diff", "--cached", "--quiet"], cwd=path)
        return False  # 変更なし
    except GitError:
        return True  # 変更あり


def commit(path: Path, message: str = "ai-adapter sync") -> None:
    """git commit を実行する。"""
    _run_git(["commit", "-m", message], cwd=path)


def pull_rebase(path: Path, branch: str = "main") -> None:
    """git pull --rebase origin <branch> を実行する。

    Args:
        path: リポジトリパス。
        branch: ブランチ名（デフォルト: main）。
    """
    try:
        _run_git(["pull", "--rebase", "origin", branch], cwd=path)
    except GitError as e:
        # コンフリクト時は abort
        try:
            _run_git(["rebase", "--abort"], cwd=path)
        except GitError:
            pass
        raise GitError(str(e))


def push(path: Path, branch: str = "main") -> None:
    """git push origin <branch> を実行する。

    Args:
        path: リポジトリパス。
        branch: ブランチ名（デフォルト: main）。
    """
    _run_git(["push", "origin", branch], cwd=path)


def get_remotes(path: Path) -> list[str]:
    """リモートリポジトリ一覧を取得する。"""
    result = _run_git(["remote"], cwd=path)
    return [r.strip() for r in result.stdout.strip().split("\n") if r.strip()]


def get_current_branch(path: Path) -> str:
    """現在のブランチ名を取得する。"""
    result = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=path)
    return result.stdout.strip()


def remote_branch_exists(path: Path, branch: str = "main") -> bool:
    """リモートに指定ブランチが存在するか確認する。

    git ls-remote --heads origin <branch> で判断。
    """
    try:
        result = _run_git(
            ["ls-remote", "--heads", "origin", branch], cwd=path
        )
        return bool(result.stdout.strip())
    except GitError:
        return False


def test_remote_connectivity(path: Path) -> bool:
    """リモートリポジトリに接続できるか確認する。

    git ls-remote --heads origin で判断。
    """
    try:
        _run_git(["ls-remote", "--heads", "origin"], cwd=path)
        return True
    except GitError:
        return False


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
