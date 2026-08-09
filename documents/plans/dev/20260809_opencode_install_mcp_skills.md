# opencode install — MCP・Skills 対応拡張計画

**作成日**: 2026-08-09
**フェーズ**: 実装計画
**優先度**: 🟡 中

---

## 背景

`ai-adapter opencode install` は現在 `opencode.json` に `instructions` と `permission` のみ出力する。
登録済みの MCP サーバーや Skill が opencode.json に反映されないため、拡張する。

## opencode.json スキーマ（関連セクション）

```jsonc
{
  "instructions": [".github/copilot-instructions.md"],
  "skills": {
    "paths": [".github/skills"]        // スキルディレクトリへの追加パス
  },
  "mcp": {
    "github": {                         // サーバー名でキー化
      "type": "local",
      "command": ["npx", "@modelcontextprotocol/server-github"],
      "environment": { "GITHUB_TOKEN": "${GITHUB_TOKEN}" },
      "enabled": true
    }
  },
  "permission": { ... }
}
```

---

## 設計判断

### skills.paths と instructions の関係

- `skills.paths` は opencode 側が `.github/skills/` 配下を自動検索するための指定
- `instructions` には `.github/skills/*/SKILL.md` も引き続き含める（opencode の instructions として読ませるため）
- 両方を含めることで、opencode の skills 機能と instructions 機能の両方が利用可能

### MCPServer.tools フィールド

- `MCPServer.tools` は ai-adapter の管理用フィールド（`["vscode", "claude", "cursor"]`）
- opencode は独自のツールシステムを持つため、`tools` フィールドは無視
- `enabled: false` のサーバーは opencode.json に含める（ユーザーが手動で有効化できるように）

### command の配列化

- `command` は単一トークン（スペースなし）を前提とする
- `command` + `args` を配列化して `command` フィールドに格納

### 既存 opencode.json の上書き

- `opencode install` は既存の `opencode.json` を上書きする（既存動作の維持）

---

## 振る舞い定義（BDD）

### Task 1: MCP サーバー設定の追加

| # | シナリオ | 入力データ | 期待出力 |
|---|---------|-----------|---------|
| 1.1 | MCP サーバーが1件登録されている | `mcp_servers: [MCPServer(name="github", command="npx", args=["@modelcontextprotocol/server-github"], enabled=True)]` | `opencode.json` の `mcp.github` に `{type: "local", command: ["npx", "@modelcontextprotocol/server-github"], enabled: true}` が含まれる |
| 1.2 | MCP サーバーが複数登録されている | 上記 + `MCPServer(name="playwright", command="npx", args=["@anthropic-ai/mcp-playwright"])` | 両方のサーバーが `mcp` セクションに含まれる |
| 1.3 | MCP サーバーに env_keys がある | `MCPServer(name="gh", command="npx", args=["pkg"], env_keys=["GITHUB_TOKEN"])` | `environment: {"GITHUB_TOKEN": "${GITHUB_TOKEN}"}` が設定される |
| 1.4 | MCP サーバーが無効化されている | `MCPServer(name="x", command="npx", args=["pkg"], enabled=False)` | `mcp.x.enabled: false` が設定される |
| 1.5 | MCP サーバーが0件 | 空リスト | `mcp` セクションは生成されない |
| 1.6 | args が空リスト | `MCPServer(name="x", command="npx", args=[])` | `command: ["npx"]`（単要素配列） |

### Task 2: Skills パスの追加

| # | シナリオ | 入力データ | 期待出力 |
|---|---------|-----------|---------|
| 2.1 | Skill が1件以上登録されている | `skills: [Skill(name="db-schema")]` | `skills.paths` に `.github/skills` が含まれる |
| 2.2 | Skill が0件 | 空リスト | `skills` セクションは生成されない |
| 2.3 | Skill と Agent の両方が登録されている | 両方あり | `instructions` に agent パターン + SKILL.md パターン、`skills.paths` にスキルパスがそれぞれ含まれる |

### Task 3: 既存動作の維持（非回帰）

| # | シナリオ | 期待出力 |
|---|---------|---------|
| 3.1 | MCP も Skill も未登録 | 従来通り `instructions` + `permission` のみ |
| 3.2 | Agent のみ登録 | 従来通り `instructions` に `.github/agents/*.agent.md` |
| 3.3 | `opencode uninstall` | `opencode.json` が削除される（変更なし） |
| 3.4 | `opencode validate` | エージェントファイルの検証が動作する（変更なし） |

---

## 変更対象ファイル

| ファイル | 変更内容 |
|---------|---------|
| `src/ai_adapter/providers/opencode.py` | `opencode_install()` に MCP → opencode 形式変換ロジック、skills.paths 追加ロジックを追加。変換ヘルパー関数 `_mcp_server_to_opencode()` をモジュールレベルに追加 |
| `tests/test_opencode.py` | MCP 対応テスト（6ケース）、skills 対応テスト（3ケース）を追加 |
| `README.md` | `opencode install` のドキュメント更新（MCP/skills 対応の記載追加） |

---

## MCP 変換ロジック

```python
# src/ai_adapter/providers/opencode.py 内
def _mcp_server_to_opencode(server: MCPServer) -> dict:
    """Convert ai-adapter MCPServer to opencode.json MCP format.

    Note: MCPServer.command must be a single token (no spaces).
    MCPServer.tools field is ignored (opencode has its own tool system).
    """
    entry: dict = {
        "type": "local",
        "command": [server.command] + server.args,
        "enabled": server.enabled,
    }
    if server.env_keys:
        entry["environment"] = {k: f"${{{k}}}" for k in server.env_keys}
    return entry
```

opencode_install() 内での利用:

```python
if cfg and cfg.mcp_servers:
    mcp_section = {}
    for server in cfg.mcp_servers:
        mcp_section[server.name] = _mcp_server_to_opencode(server)
    config["mcp"] = mcp_section
```

---

## スキル対応ロジック

```python
# スキルが登録されている場合、skills.paths を追加
if cfg.skills:
    config["skills"] = {"paths": [".github/skills"]}
```

---

## 検証方法

```bash
# テスト実行
uv run python -m unittest tests/test_opencode.py -v

# 手動検証
ai-adapter mcp add test-server --command npx --args test-pkg
ai-adapter skill add /path/to/skill
ai-adapter opencode install
cat opencode.json | jq '.mcp, .skills'
```
