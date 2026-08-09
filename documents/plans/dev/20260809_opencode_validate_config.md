# opencode validate — opencode.json スキーマ検証機能追加

**作成日**: 2026-08-09
**フェーズ**: 実装計画
**優先度**: 🟡 中

---

## 背景

現在の `ai-adapter opencode validate` は `.github/agents/` 配下の `.agent.md` ファイルの `tools` フォーマットのみ検証する。
`opencode install` で生成された `opencode.json` 自体のスキーマ整合性を検証する機能がない。

---

## 振る舞い定義（BDD）

### Task 1: opencode.json の存在確認

| # | シナリオ | 期待出力 |
|---|---------|---------|
| 1.1 | `opencode.json` が存在する | 検証を実行 |
| 1.2 | `opencode.json` が存在しない | エラーメッセージ + exit 1 |

### Task 2: JSON 構文チェック

| # | シナリオ | 期待出力 |
|---|---------|---------|
| 2.1 | 有効な JSON | 検証を続行 |
| 2.2 | 不正な JSON（構文エラー） | エラーメッセージ + exit 1 |

### Task 3: スキーマ検証（ai-adapter が生成するセクション）

| # | シナリオ | 検証内容 |
|---|---------|---------|
| 3.1 | `instructions` | 配列か？各要素は文字列か？ |
| 3.2 | `permission` | オブジェクトか？キーは有効な値か？（read, edit, glob, grep, list, bash, task, webfetch, websearch, todowrite） |
| 3.3 | `mcp` | オブジェクトか？各サーバーに `type` と `command` があるか？ `type` は "local" か "remote" か？ |
| 3.4 | `skills` | オブジェクトか？`paths` は配列か？ |
| 3.5 | `command` | オブジェクトか？各コマンドに `template` があるか？ |

### Task 4: パス存在確認（オプション）

| # | シナリオ | 期待出力 |
|---|---------|---------|
| 4.1 | `skills.paths` のパスが実在する | OK |
| 4.2 | `skills.paths` のパスが存在しない | 警告メッセージ |

### Task 5: 既存動作の維持

| # | シナリオ | 期待出力 |
|---|---------|---------|
| 5.1 | `.agent.md` ファイルの検証 | 従来通り動作 |
| 5.2 | `--fix` オプション | `.agent.md` の修正のみ実行 |
| 5.3 | `--quiet` オプション | 最小限の出力 |

---

## 実装方針

### 拡張コマンド構造

```
ai-adapter opencode validate [--fix] [--quiet] [--project-dir DIR]
```

- 既存の `.agent.md` 検証は維持
- `opencode.json` の検証を追加（新しいオプション `--config` で制御可能）
- デフォルトでは両方検証

### 検証ロジック

```python
def _validate_opencode_config(config_path: Path) -> list[str]:
    """Validate opencode.json against expected schema."""
    errors = []

    # 1. JSON parse
    try:
        with open(config_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return [f"Invalid JSON: {e}"]

    # 2. instructions check
    if "instructions" in data:
        if not isinstance(data["instructions"], list):
            errors.append("'instructions' must be an array")
        elif not all(isinstance(s, str) for s in data["instructions"]):
            errors.append("'instructions' items must be strings")

    # 3. permission check
    VALID_PERMISSION_KEYS = {
        "read",
        "edit",
        "glob",
        "grep",
        "list",
        "bash",
        "task",
        "external_directory",
        "todowrite",
        "question",
        "webfetch",
        "websearch",
        "lsp",
        "doom_loop",
        "skill",
    }
    if "permission" in data:
        if not isinstance(data["permission"], dict):
            errors.append("'permission' must be an object")
        else:
            for key in data["permission"]:
                if key not in VALID_PERMISSION_KEYS:
                    errors.append(f"Unknown permission key: '{key}'")

    # 4. mcp check
    if "mcp" in data:
        if not isinstance(data["mcp"], dict):
            errors.append("'mcp' must be an object")
        else:
            for name, server in data["mcp"].items():
                if not isinstance(server, dict):
                    errors.append(f"mcp.{name} must be an object")
                    continue
                if "type" not in server:
                    errors.append(f"mcp.{name}: missing 'type'")
                elif server["type"] not in ("local", "remote"):
                    errors.append(f"mcp.{name}: invalid type '{server['type']}'")
                if "command" not in server:
                    errors.append(f"mcp.{name}: missing 'command'")
                elif not isinstance(server["command"], list):
                    errors.append(f"mcp.{name}: 'command' must be an array")

    # 5. skills check
    if "skills" in data:
        if not isinstance(data["skills"], dict):
            errors.append("'skills' must be an object")
        elif "paths" in data["skills"]:
            if not isinstance(data["skills"]["paths"], list):
                errors.append("'skills.paths' must be an array")

    # 6. command check
    if "command" in data:
        if not isinstance(data["command"], dict):
            errors.append("'command' must be an object")
        else:
            for name, cmd in data["command"].items():
                if not isinstance(cmd, dict):
                    errors.append(f"command.{name} must be an object")
                elif "template" not in cmd:
                    errors.append(f"command.{name}: missing required 'template'")

    return errors
```

---

## 変更対象ファイル

| ファイル | 変更内容 |
|---------|---------|
| `src/ai_adapter/providers/opencode.py` | `_validate_opencode_config()` 関数追加、`opencode_validate()` に統合 |
| `tests/test_opencode.py` | 検証テスト追加 |
| `README.md` | ドキュメント更新 |

---

## 検証方法

```bash
# テスト実行
uv run python -m unittest tests/test_opencode.py -v

# 手動検証
ai-adapter opencode install
ai-adapter opencode validate
```
