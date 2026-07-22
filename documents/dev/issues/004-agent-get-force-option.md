# Issue #4: `agent get` に `--force` オプションがない

> **優先度**: 🟡 中  
> **種類**: 機能不足（一貫性欠如）  
> **対象ファイル**: `src/ai_adapter/agent.py`

---

## 問題

`skill get` には `--force` オプションがあるが、`agent get` にはない。

| コマンド | `--force` | 動作 |
|---------|-----------|------|
| `skill get` | ✅ あり | 既存ファイルを確認なしで上書き |
| `agent get` | ❌ なし | `shutil.copy2` で無条件上書き |
| `bin get` | ❌ なし | `shutil.copy2` で無条件上書き |

## 影響

- `agent get` で既存ファイルを上書きする際に確認プロンプトが表示されない
- ユーザーが意図せずファイルを上書きしてしまうリスクがある
- `skill get` との操作性の一貫性が損なわれる

## 修正内容

`agent get` に `--force` オプションを追加する。

```python
@agent_group.command(name="get")
@click.argument("name")
@click.option("--force", is_flag=True, help="既存ファイルを確認なしで上書き")
@click.option("--project-dir", "-d", type=click.Path(...), default=None)
def agent_get(name: str, force: bool, project_dir: str | None) -> None:
    """エージェントファイルを .github/agents/ にコピーする。"""
    # ... 既存のロジック ...
    
    if dest.exists() and not force:
        click.confirm(f"'{dest.name}' は既に存在します。上書きしますか？", abort=True)
    
    shutil.copy2(src, dest)
```

## 関連 Issue

- `bin get` にも同様に `--force` を追加すべきか検討（Issue #4b として別途作成）

## 検証

- [ ] `ai-adapter agent get reviewer` で既存ファイルがある場合に確認プロンプトが表示される
- [ ] `ai-adapter agent get reviewer --force` で確認なしで上書きされる
- [ ] 全テスト PASS
