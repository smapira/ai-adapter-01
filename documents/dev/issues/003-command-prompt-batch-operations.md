# Issue #3: `command`/`prompt` に一括操作コマンドがない

> **優先度**: 🔴 高  
> **種類**: 機能不足（一貫性欠如）  
> **対象ファイル**: `src/ai_adapter/command.py`, `src/ai_adapter/prompt.py`

---

## 問題

`agent`/`bin`/`skill` には以下の一括操作コマンドが実装されているが、`command`/`prompt` にはない。

| コマンド | agent | bin | skill | command | prompt |
|---------|-------|-----|-------|---------|--------|
| `add-rec` | ✅ | ✅ | ✅ | ❌ | ❌ |
| `get-all` | ✅ | ✅ | ✅ | ❌ | ❌ |
| `remove-all` | ✅ | ✅ | ✅ | ❌ | ❌ |

## 影響

- ユーザーが `command`/`prompt` に対して一括操作を行えない
- `agent`/`bin`/`skill` との操作性の一貫性が損なわれる
- 複数のコマンド/プロンプトを個別に登録・展開・削除する手間がかかる

## 修正内容

`command.py` と `prompt.py` に以下を追加する:

### `command add-rec <dir>`
指定ディレクトリ内の全ファイルを `~/.ai-adapter/commands/` に再帰的にコピー。

### `command get-all [--project-dir/-d]`
全登録コマンドを `.github/commands/` に一括コピー。

### `command remove-all [--force]`
全登録コマンドを一括削除。

### `prompt add-rec <dir>`
指定ディレクトリ内の全ファイルを `~/.ai-adapter/prompts/` に再帰的にコピー。

### `prompt get-all [--project-dir/-d]`
全登録プロンプトを `.github/prompts/` に一括コピー。

### `prompt remove-all [--force]`
全登録プロンプトを一括削除。

## 実装方針

`agent.py`/`bin.py`/`skill.py` の既存実装を参考に、以下のパターンで実装する:

```python
@command_group.command(name="add-rec")
@click.argument("dir", type=click.Path(exists=True, file_okay=False, readable=True))
def command_add_rec(dir: str) -> None:
    """ディレクトリ内の全ファイルを ~/.ai-adapter/commands/ に再帰的に追加する。"""
    # ... 実装 ...

@command_group.command(name="get-all")
@click.option("--project-dir", "-d", type=click.Path(...), default=None)
def command_get_all(project_dir: str | None) -> None:
    """全登録コマンドを .github/commands/ に一括コピーする。"""
    # ... 実装 ...

@command_group.command(name="remove-all")
@click.option("--force", is_flag=True, help="確認プロンプトを表示せずに削除")
def command_remove_all(force: bool) -> None:
    """全登録コマンドを一括削除する。"""
    # ... 実装 ...
```

## テスト

- `tests/test_command.py` に `test_command_add_rec`, `test_command_get_all`, `test_command_remove_all` を追加
- `tests/test_prompt.py` に `test_prompt_add_rec`, `test_prompt_get_all`, `test_prompt_remove_all` を追加

## 検証

- [ ] `ai-adapter command add-rec <dir>` で一括登録できる
- [ ] `ai-adapter command get-all` で一括展開できる
- [ ] `ai-adapter command remove-all --force` で一括削除できる
- [ ] `prompt` も同様に動作する
- [ ] 全テスト PASS
