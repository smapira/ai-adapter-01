# ai-adapter sync コンフリクト解決改善 — 開発者向け指示書

> **作成年月日**: 2026-07-21  
> **問題**: `pull --rebase` のコンフリクト時に自動 abort → ユーザー混乱  
> **目的**: コンフリクト検出・メッセージ・手動解決フローを改善する

---

## 1. 問題の整理

### 1.1 発生した事象

`ai-adapter sync` 実行時に以下のコンフリクトが発生:

```
リモート: fc9800c Revert "ai-adapter sync"
ローカル: 9a22659 ai-adapter sync

現在の挙動:
1. pull_rebase() が GitError をキャッチ
2. 内部で git rebase --abort を自動実行 → ユーザーの判断を奪う
3. 「手動解決してください」と表示 → abort 済みなので意味がない
```

### 1.2 原因

`git.py` の `pull_rebase()` が `except` 内で無条件に `git rebase --abort` を実行するため。

```python
def pull_rebase(path, branch="main"):
    try:
        _run_git(["pull", "--rebase", "origin", branch], cwd=path)
    except GitError as e:
        try:
            _run_git(["rebase", "--abort"], cwd=path)  # ← これが問題
        except GitError:
            pass
        raise GitError(str(e))
```

### 1.3 改善点

| 問題 | 改善 |
|------|------|
| 自動 abort でユーザーの判断を奪う | abort を自動実行せず、選択肢を提示 |
| エラーメッセージが抽象的 | 具体的な手順と原因を表示 |
| リベース中の状態を検出できない | `is_rebasing()` 関数を追加 |
| リベース再開/中断コマンドがない | `sync --continue / --abort / --skip` を追加 |
| 何がコンフリクトしたかわからない | `get_conflicted_files()` で競合ファイル一覧を表示 |

---

## 2. 実装ファイル構成

| ファイル | 変更内容 |
|---------|---------|
| `src/ai_adapter/git.py` | `is_rebasing()` 追加, `get_conflicted_files()` 追加, `pull_rebase()` の abort 自動実行を削除 |
| `src/ai_adapter/sync.py` | リベース検出ブロック追加, adapter_dir 引数対応 |
| `src/ai_adapter/cli.py` | `cmd_sync` に `--continue/--abort/--skip` 追加, `status` にリベース状態表示追加 |
| `tests/test_git.py` | `test_is_rebasing`, `test_get_conflicted_files` 追加 |
| `tests/test_sync.py` | `test_sync_detects_rebase_in_progress` 追加 |
| `tests/test_cli.py` | `test_sync_continue`, `test_sync_abort`, `test_sync_skip` 追加 |

---

## 3. 実装詳細

### 3.1 `git.py` — 関数追加 + pull_rebase 改修

```python
def is_rebasing(path: Path) -> bool:
    """リベース中かどうかを判定する。"""
    git_dir_result = _run_git(["rev-parse", "--git-dir"], cwd=path)
    git_dir = Path(git_dir_result.stdout.strip())
    return (git_dir / "rebase-apply").exists() or (git_dir / "rebase-merge").exists()


def get_conflicted_files(path: Path) -> list[str]:
    """コンフリクト中のファイル一覧を取得する。"""
    try:
        result = _run_git(["diff", "--name-only", "--diff-filter=U"], cwd=path)
        return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    except GitError:
        return []


def pull_rebase(path: Path, branch: str = "main") -> None:
    """git pull --rebase origin <branch>（コンフリクト時に abort しない）。"""
    try:
        _run_git(["pull", "--rebase", "origin", branch], cwd=path)
    except GitError as e:
        err_msg = str(e)
        if is_rebasing(path):
            conflicted = get_conflicted_files(path)
            detail = ""
            if conflicted:
                detail = "\n  コンフリクトファイル:\n" + "\n".join(f"    - {f}" for f in conflicted)

            raise GitError(
                f"pull --rebase でコンフリクトが発生しました。{detail}\n\n"
                "  以下のコマンドで手動解決してください:\n\n"
                "  1. コンフリクトを解決する場合:\n"
                "     cd ~/.ai-adapter && git add <ファイル> && git rebase --continue\n\n"
                "  2. リベースを中断する場合:\n"
                "     cd ~/.ai-adapter && git rebase --abort\n\n"
                "  3. ローカルのコミットをスキップする場合:\n"
                "     cd ~/.ai-adapter && git rebase --skip\n\n"
                "  ai-adapter sync --continue   # リベース続行\n"
                "  ai-adapter sync --abort      # リベース中断\n"
                "  ai-adapter sync --skip       # このコミットをスキップ"
            )
        raise GitError(f"pull --rebase に失敗しました:\n{err_msg}")
```

### 3.2 `cli.py` — sync コマンド改修

```python
# cli.py の import に追加
from ai_adapter.git import is_rebasing, get_conflicted_files, _run_git as run_git

# main.add_command(sync_command) を削除し、以下に置き換え


@main.command(name="sync")
@click.option("--continue", "do_continue", is_flag=True, help="中断されたリベースを続行")
@click.option("--abort", "do_abort", is_flag=True, help="リベースを中断")
@click.option("--skip", "do_skip", is_flag=True, help="コミットをスキップ")
@click.pass_context
def cmd_sync(ctx: click.Context, do_continue: bool, do_abort: bool, do_skip: bool) -> None:
    """~/.ai-adapter/ を GitHub リモートと同期する。"""
    adapter_dir = _config.AI_ADAPTER_DIR

    if not adapter_dir.exists():
        click.echo(f"'{adapter_dir}' が見つかりません。ai-adapter init を実行してください。")
        raise click.ClickException("ai-adapter が初期化されていません。")

    # リベース操作モード
    if do_continue or do_abort or do_skip:
        _handle_rebase_operation(adapter_dir, do_continue, do_abort, do_skip)
        return

    # 通常の sync（リベース検出付き）
    from ai_adapter.sync import sync_command

    try:
        sync_command(adapter_dir)
    except GitError as e:
        click.echo(f"エラー: {e}", err=True)
        raise click.ClickException(str(e))


def _handle_rebase_operation(adapter_dir: Path, do_continue: bool, do_abort: bool, do_skip: bool) -> None:
    """リベース操作を処理する。"""
    if not is_rebasing(adapter_dir):
        click.echo("リベース中の状態ではありません。")
        return

    if do_abort:
        click.echo("リベースを中断中...")
        run_git(["rebase", "--abort"], cwd=adapter_dir)
        click.echo("リベースを中断しました。元の状態に戻りました。")
    elif do_skip:
        click.echo("コミットをスキップしてリベースを続行中...")
        run_git(["rebase", "--skip"], cwd=adapter_dir)
        click.echo("スキップしました。")
        if is_rebasing(adapter_dir):
            click.echo("まだリベース中のコミットがあります。git status で確認してください。")
        else:
            click.echo("全てのリベースが完了しました。ai-adapter sync でプッシュしてください。")
    elif do_continue:
        click.echo("リベースを続行中...")
        try:
            run_git(["rebase", "--continue"], cwd=adapter_dir)
            click.echo("リベースを続行しました。")
            if is_rebasing(adapter_dir):
                click.echo("まだリベース中のコミットがあります。")
            else:
                click.echo("ai-adapter sync を再実行してプッシュしてください。")
        except GitError as e:
            if "Author identity unknown" in str(e):
                click.echo("Git ユーザー設定がされていません。")
                click.echo("  git config --global user.email 'you@example.com'")
                click.echo("  git config --global user.name 'Your Name'")
            elif "unchanged" in str(e).lower():
                click.echo("コンフリクトがまだ解決されていません。")
                click.echo("  cd ~/.ai-adapter && git status で状態を確認")
            else:
                click.echo(f"リベース続行に失敗: {e}")

    # cmd_status 内に追加:
    from ai_adapter.git import is_rebasing, get_conflicted_files

    rebasing = is_rebasing(adapter_dir)
    click.echo(f"  リベース状態: {'⚠ 中断中' if rebasing else '✓'}")
    if rebasing:
        conflicted = get_conflicted_files(adapter_dir)
        if conflicted:
            click.echo(f"  コンフリクトファイル: {', '.join(conflicted)}")
```

### 3.3 `sync.py` — リベース検出ブロック追加

```python
# sync_command の先頭に追加
from ai_adapter.git import is_rebasing, get_conflicted_files


def sync_command(adapter_dir: Path | None = None) -> None:
    """~/.ai-adapter/ を GitHub リモートと同期する。"""
    if adapter_dir is None:
        adapter_dir = _config.AI_ADAPTER_DIR

    if not adapter_dir.exists():
        click.echo(f"'{adapter_dir}' が見つかりません。")
        raise click.ClickException("ai-adapter が初期化されていません。")

    # ★ リベース中断検出
    if is_rebasing(adapter_dir):
        conflicted = get_conflicted_files(adapter_dir)
        click.echo("⚠ 前回の sync でリベースが中断されたままです。")
        if conflicted:
            click.echo("  コンフリクトファイル:")
            for f in conflicted:
                click.echo(f"    - {f}")
        click.echo("  解決方法: ai-adapter sync --continue / --abort / --skip")
        raise click.ClickException("リベースを先に解決してください。")

    # ... 以下既存のロジック（adapter_dir 引数対応のみ）...
```

---

## 4. 期待する動作

```bash
# コンフリクト発生時
$ ai-adapter sync
Step 3: pull --rebase でコンフリクトが発生しました。
  コンフリクトファイル:
    - config.json
  解決方法: ai-adapter sync --continue / --abort / --skip

# リベース中断 → 再実行
$ ai-adapter sync
⚠ 前回の sync でリベースが中断されたままです。
  コンフリクトファイル:
    - config.json
  解決方法: ai-adapter sync --continue / --abort / --skip

# sync --abort
$ ai-adapter sync --abort
リベースを中断しました。

# status 表示
$ ai-adapter status
  リベース状態: ⚠ 中断中
  コンフリクトファイル: config.json
```

---

## 5. 検証手順

- [ ] コンフリクト時に auto-abort しない
- [ ] コンフリクトファイル一覧が表示される
- [ ] `sync --abort` でリベースが中断される
- [ ] `sync --skip` でコミットがスキップされる
- [ ] リベース中断状態で `sync` 再実行時に検出される
- [ ] `status` にリベース状態が表示される
- [ ] 全テスト PASS