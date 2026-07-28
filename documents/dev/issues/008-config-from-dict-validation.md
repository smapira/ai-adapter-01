# Issue #8: `Config.from_dict()` にバリデーションがない

> **優先度**: 🟡 中  
> **種類**: 堅牢性不足  
> **対象ファイル**: `src/ai_adapter/models.py`  
> **対象行**: 179-199行目付近

---

## 問題

`Config.from_dict()` は入力データをそのまま信頼しており、型チェックやバリデーションを行っていない。

```python
@classmethod
def from_dict(cls, data: dict) -> "Config":
    return cls(
        version=data.get("version", 1),
        agents=[Agent.from_dict(a) for a in data.get("agents", [])],
        envs=[Env.from_dict(e) for e in data.get("envs", [])],
        # ...
    )
```

## 影響

- `config.json` が壊れている場合（例：`default_env` が数値、`agents` が文字列など）、`AttributeError` や `TypeError` が生のまま上がる
- ユーザーには「内部エラー」として表示され、原因が分かりにくい
- 手動で `config.json` を編集したユーザーがミスに気づけない

## 修正内容

`from_dict()` に型チェックとバリデーションを追加する。

```python
@classmethod
def from_dict(cls, data: dict) -> "Config":
    """設定ファイルから Config オブジェクトを生成する。
    
    Raises:
        ValueError: データの型が不正な場合。
    """
    if not isinstance(data, dict):
        raise ValueError(f"設定ファイルの形式が不正です: dict である必要があります")
    
    # version のバリデーション
    version = data.get("version", 1)
    if not isinstance(version, int):
        raise ValueError(f"version は整数である必要があります: {version}")
    
    # default_env のバリデーション
    default_env = data.get("default_env", "default")
    if not isinstance(default_env, str):
        raise ValueError(f"default_env は文字列である必要があります: {default_env}")
    
    # agents のバリデーション
    agents_data = data.get("agents", [])
    if not isinstance(agents_data, list):
        raise ValueError(f"agents は配列である必要があります: {agents_data}")
    agents = [Agent.from_dict(a) for a in agents_data]
    
    # envs のバリデーション
    envs_data = data.get("envs", [])
    if not isinstance(envs_data, list):
        raise ValueError(f"envs は配列である必要があります: {envs_data}")
    envs = [Env.from_dict(e) for e in envs_data]
    
    # bins のバリデーション
    bins_data = data.get("bins", [])
    if not isinstance(bins_data, list):
        raise ValueError(f"bins は配列である必要があります: {bins_data}")
    bins = [Bin.from_dict(b) for b in bins_data]
    
    # ... 他フィールドも同様に ...
    
    return cls(
        version=version,
        agents=agents,
        envs=envs,
        bins=bins,
        default_env=default_env,
        # ...
    )
```

## エラーハンドリング

`load_config()` で `ValueError` をキャッチし、ユーザーフレンドリーなメッセージを表示する。

```python
# config.py
def load_config() -> Config | None:
    config_path = get_config_path()
    if not config_path.exists():
        return None
    
    with open(config_path) as f:
        data = json.load(f)
    
    try:
        return Config.from_dict(data)
    except ValueError as e:
        click.echo(f"設定ファイルの形式が不正です: {e}", err=True)
        click.echo(f"  {config_path}", err=True)
        click.echo("  config.json を修正するか、ai-adapter uninstall でリセットしてください。", err=True)
        raise click.ClickException("設定ファイルの読み込みに失敗しました。")
```

## テスト

`tests/test_config.py` に以下を追加:

```python
def test_from_dict_invalid_version(self):
    """version が整数でない場合に ValueError が上がることを確認する。"""
    with self.assertRaises(ValueError):
        Config.from_dict({"version": "1"})


def test_from_dict_invalid_agents(self):
    """agents が配列でない場合に ValueError が上がることを確認する。"""
    with self.assertRaises(ValueError):
        Config.from_dict({"agents": "not a list"})


def test_from_dict_invalid_default_env(self):
    """default_env が文字列でない場合に ValueError が上がることを確認する。"""
    with self.assertRaises(ValueError):
        Config.from_dict({"default_env": 123})
```

## 検証

- [ ] 壊れた `config.json` を読み込むと適切なエラーメッセージが表示される
- [ ] `ai-adapter status` で壊れた設定ファイルの場合にガイドが表示される
- [ ] 全テスト PASS
