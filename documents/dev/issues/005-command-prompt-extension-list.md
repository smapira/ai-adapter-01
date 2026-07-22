# Issue #5: `command get`/`prompt get` の拡張子リストが固定

> **優先度**: 🟡 中  
> **種類**: 機能不足（柔軟性欠如）  
> **対象ファイル**: `src/ai_adapter/command.py`, `src/ai_adapter/prompt.py`

---

## 問題

`command get` と `prompt get` のファイル検索で、拡張子リストがハードコードされている。

**`src/ai_adapter/command.py:78-81`:**
```python
candidates = [
    commands_dir / f"{name}",
    commands_dir / f"{name}.sh",
    commands_dir / f"{name}.py",
    commands_dir / f"{name}.md",
]
```

**`src/ai_adapter/prompt.py:75-78`:**
```python
candidates = [
    prompts_dir / f"{name}",
    prompts_dir / f"{name}.md",
    prompts_dir / f"{name}.txt",
]
```

## 影響

- `.rb`, `.js`, `.json`, `.yaml`, `.toml` 等のファイルが検索されない
- ユーザーが `ai-adapter command get my-script` を実行しても、`my-script.rb` が見つからない
- 拡張子を明示的に指定する手段がない

## 修正内容

### 案 A: 拡張子リストを拡張

```python
# command.py
candidates = [
    commands_dir / f"{name}",
    commands_dir / f"{name}.sh",
    commands_dir / f"{name}.py",
    commands_dir / f"{name}.md",
    commands_dir / f"{name}.rb",
    commands_dir / f"{name}.js",
    commands_dir / f"{name}.json",
    commands_dir / f"{name}.yaml",
    commands_dir / f"{name}.toml",
]

# prompt.py
candidates = [
    prompts_dir / f"{name}",
    prompts_dir / f"{name}.md",
    prompts_dir / f"{name}.txt",
    prompts_dir / f"{name}.json",
    prompts_dir / f"{name}.yaml",
]
```

### 案 B: 拡張子なしで完全一致 → ディレクトリ内ワイルドカード検索

```python
# 1. 完全一致を試す
exact = commands_dir / name
if exact.exists():
    return exact

# 2. 拡張子付きで検索
for f in commands_dir.iterdir():
    if f.stem == name and f.is_file():
        return f

# 3. 見つからない
raise click.ClickException(f"コマンド '{name}' が見つかりません。")
```

### 推奨: 案 B

案 B の方が柔軟性が高く、将来新しい拡張子が追加されても対応不要。

## 実装方針

`agent.py` の `_get_agent_name_from_path()` と同様のロジックを採用する:

```python
def _find_command_by_name(commands_dir: Path, name: str) -> Path | None:
    """コマンド名からファイルを検索する。"""
    # 1. 完全一致
    exact = commands_dir / name
    if exact.exists() and exact.is_file():
        return exact
    
    # 2. 拡張子付きで検索
    for f in sorted(commands_dir.iterdir()):
        if f.is_file() and f.stem == name:
            return f
    
    return None
```

## 検証

- [ ] `ai-adapter command get my-script` で `my-script.rb` が見つかる
- [ ] `ai-adapter prompt get my-prompt` で `my-prompt.yaml` が見つかる
- [ ] 拡張子なしのファイルも引き続き見つかる
- [ ] 全テスト PASS
