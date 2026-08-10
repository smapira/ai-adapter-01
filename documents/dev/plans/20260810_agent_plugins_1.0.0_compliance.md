# Agent Plugins 1.0.0 準拠 開発者向け指示書

## 概要

[Agent Plugins 1.0.0](https://agent-plugins.org/) は、AIエージェントのスキルやMCPサーバ設定を異なるエージェント間で共有可能にする業界標準の仕様です。AWS、Microsoft、OpenAI、Anysphere、Vercel、Google がサポートしています。

本ドキュメントは、`ai-adapter` プロジェクトを Agent Plugins 1.0.0 に準拠させるための開発者向け指示書です。

---

## 1. Agent Plugins のパッケージ構成

Agent Plugins は以下のディレクトリ構成が必須です：

```
my-plugin/
├── plugin.json              # 必須マニフェスト
├── skills/                  # スキル（Agent Skills 形式）
│   └── skill-name/
│       ├── SKILL.md
│       ├── scripts/
│       └── references/
├── mcp.json                 # MCP サーバ設定
└── com.example.client/      # クライアント拡張（任意）
    └── hooks/
```

---

## 2. `plugin.json` マニフェスト（必須）

### 2.1 最小構成

```json
{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
  "name": "my-plugin"
}
```

### 2.2 フル構成

```json
{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
  "name": "ai-adapter-plugin",
  "version": "1.0.0",
  "description": "AI agent skills and MCP servers for EC operations",
  "author": {
    "name": "smapira",
    "url": "https://github.com/smapira"
  },
  "homepage": "https://github.com/smapira/ai-adapter-01",
  "repository": "https://github.com/smapira/ai-adapter-01",
  "license": "MIT",
  "keywords": ["ai-agent", "skills", "mcp", "ec-cube"],
  "extensions": {
    "ai.smapira.adapter": {
      "opencode_compat": true
    }
  }
}
```

### 2.3 `name` の制約

| 制約 | 要件 |
|------|------|
| 文字数 | 1〜64文字 |
| 文字セット | `a-z`, `0-9`, `-`, `.` のみ |
| 先頭・末尾 | 英数字 |
| 連続記号 | `--` や `..` は不可 |

有効例: `ai-adapter-plugin`, `acme.tools`, `lint3r`
無効例: `My-Plugin`（大文字）, `-start`（先頭ハイフン）

---

## 3. `mcp.json` MCP サーバ設定

### 3.1 フォーマット

Agent Plugins の `mcp.json` は以下の形式です：

```json
{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
  "mcpServers": {
    "server-name": {
      "type": "stdio",
      "command": "./bin/server",
      "args": ["--config", "${PLUGIN_ROOT}/config.json"],
      "env": {
        "DATA_DIR": "${PLUGIN_DATA}/database"
      },
      "cwd": "${PLUGIN_ROOT}"
    }
  }
}
```

### 3.2 既存 `.mcp.json` との違い

| 項目 | 既存 `.mcp.json` | Agent Plugins `mcp.json` |
|------|-----------------|------------------------|
| スキーマ | なし | `$schema` 必須 |
| サーバの `type` | なし（stdio のみ） | `type: "stdio"` 必須 |
| `command` | 単一トークン | 単一トークン（プラグイン相対パスなら `./`） |
| パス変数 | なし | `${PLUGIN_ROOT}`, `${PLUGIN_DATA}` 使用可 |
| ファイル名 | `.mcp.json` | `mcp.json`（ドットなし） |

### 3.3 変換ルール

既存の `.mcp.json` を Agent Plugins 形式に変換するルール：

1. `$schema` を追加
2. 各サーバに `"type": "stdio"` を追加
3. `command` を単一トークンに変換（配列の場合は先頭要素）
4. パスを `${PLUGIN_ROOT}` ベースに変換（可能な場合）
5. ファイル名を `.mcp.json` → `mcp.json` に変更

### 3.4 `${PLUGIN_ROOT}` と `${PLUGIN_DATA}`

| 変数 | 説明 | 用途 |
|------|------|------|
| `${PLUGIN_ROOT}` | プラグインルートの絶対パス | バンドルされたスクリプト・設定ファイルの参照 |
| `${PLUGIN_DATA}` | クライアント管理の永続データディレクトリ | node_modules、キャッシュ、生成ファイル |

**注意:** `PLUGIN_ROOT` と `PLUGIN_DATA` は `env` オブジェクト内では使用できません。クライアントが自動的に設定します。

---

## 4. スキル（Agent Skills）

### 4.1 ディレクトリ構成

```
skills/
└── skill-name/
    ├── SKILL.md          # 必須（スキル定義）
    ├── scripts/          # 任意（補助スクリプト）
    └── references/       # 任意（参照資料）
```

### 4.2 SKILL.md フォーマット

Agent Plugins は [Agent Skills 仕様](https://agentskills.io/specification) に準拠した SKILL.md を要求します。現行の SKILL.md は基本的に互換性がありますが、以下の点を確認してください：

- YAML frontmatter に `name`, `description` が含まれていること
- ファイルパスがプラグインルート内に収まること

### 4.3 現行スキルとの互換性

`ai-adapter` のスキル（`.github/skills/*/SKILL.md`）は Agent Skills 仕様に準拠しているため、大きな変更は不要です。配置パスを `.github/skills/` → `skills/` に変更するだけで対応可能です。

---

## 5. `ai-adapter` への実装方針

### 5.1 新規コマンド: `ai-adapter plugin`

Agent Plugins 準拠のプラグインパッケージを生成するコマンドを追加します。

```bash
# プラグインパッケージを生成
ai-adapter plugin build --output ./dist

# plugin.json をバリデーション
ai-adapter plugin validate

# mcp.json を生成（既存の MCP サーバ設定から）
ai-adapter plugin mcp-generate
```

### 5.2 既存コマンドの拡張

| コマンド | 変更内容 |
|---------|---------|
| `mcp get` | `--format agent-plugins` オプション追加 |
| `skill get-all` | `--format agent-plugins` オプション追加 |
| `opencode install` | Agent Plugins 形式にも対応 |

### 5.3 MCP サーバの変換対応

既存の MCP サーバ設定を Agent Plugins 形式に変換するユーティリティを追加：

```python
# src/ai_adapter/providers/agent_plugins.py


def convert_mcp_to_agent_plugins(server: MCPServer) -> dict:
    """既存 MCPServer を Agent Plugins mcp.json 形式に変換"""
    return {
        "type": "stdio",
        "command": server.command,
        "args": server.args,
        "env": {k: f"${{{k}}}" for k in server.env_keys},
    }


def generate_plugin_manifest(
    name: str,
    version: str = "1.0.0",
    description: str = "",
    **kwargs,
) -> dict:
    """plugin.json を生成"""
    return {
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        "name": name,
        "version": version,
        "description": description,
        **kwargs,
    }
```

---

## 6. 対応クライアントの状況

| クライアント | Agent Plugins 対応 | 備考 |
|------------|-------------------|------|
| GitHub Copilot | ✅ 対応済み | VS Code, CLI |
| Cursor | ✅ 対応済み | Anysphere |
| ChatGPT / Codex | ✅ 対応済み | OpenAI |
| AWS Kiro | ✅ 対応済み | Amazon |
| VS Code | ✅ 対応済み | Microsoft |
| Google | ✅ 対応発表 | Google |
| Claude Code | ❌ 未対応 | Anthropic は現時点で沈黙 |

---

## 7. 移行ステップ

### Phase 1: 準備（即座に実行可能）

1. `plugin.json` のテンプレートを作成
2. `mcp.json` 変換ユーティリティを開発
3. 既存スキルの Agent Skills 仕様適合確認

### Phase 2: 実装（要検討）

1. `ai-adapter plugin` コマンドの実装
2. `mcp get --format agent-plugins` の実装
3. OpenCode との連携確認

### Phase 3: 本番运用

1. 実際のクライアント（Cursor, VS Code 等）での動作確認
2. ドキュメント整備
3. リリース

---

## 8. 参考リンク

- [Agent Plugins 仕様](https://agent-plugins.org/specification)
- [Agent Plugins スキーマ](https://agent-plugins.org/schemas)
- [plugin.json スキーマ](https://agent-plugins.org/schemas/1.0.0/plugin.schema.json)
- [mcp.json スキーマ](https://agent-plugins.org/schemas/1.0.0/mcp.schema.json)
- [Agent Skills 仕様](https://agentskills.io/specification)
- [MCP 仕様](https://modelcontextprotocol.io/specification)
- [GitHub リポジトリ](https://github.com/agentplugins/agent-plugins-spec)
