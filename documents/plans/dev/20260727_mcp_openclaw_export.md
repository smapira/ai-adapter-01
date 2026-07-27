# MCP OpenClaw Export — 実装計画

**作成日**: 2026-07-27
**更新日**: 2026-07-27（Plan Architect レビュー対応）
**親計画**: `documents/dev/plans/20260727_openclaw_integration_guide.md`
**フェーズ**: Phase 1（MCP 書き出し対応）
**優先度**: 🔴 高

---

## 設計判断

### 出力先とファイル名

`--format openclaw` の場合の出力先:

| `--path` 指定 | `~/.openclaw/` の状態 | 出力先 |
|---------------|----------------------|--------|
| なし | 存在する | `~/.openclaw/openclaw.json` にマージ |
| なし | 存在しない | カレントディレクトリの `openclaw.json`（新規作成） |
| あり (`/path/to/dir`) | 不問 | `/path/to/dir/openclaw.json`（新規作成） |

### マージ戦略

`openclaw.json` が既に存在する場合のマージルール:

1. `openclaw.json` を読み込む
2. `mcp.servers` セクションがなければ新規作成
3. サーバー名ベースでマージ:
   - **同名サーバー**: ai-adapter の値で上書き
   - **新規サーバー**: 追加
   - **ai-adapter にない既存サーバー**: 維持
4. 書き込み前に `.bak` バックアップを作成
5. `x-ai-adapter` マーカーを追記して管理対象サーバーを記録

```json
{
  "x-ai-adapter": {
    "version": 1,
    "managed_mcp_servers": ["github", "playwright"]
  },
  "mcp": {
    "servers": {
      "github": { ... },
      "playwright": { ... }
    }
  }
}
```

### `--force` オプション

- `mcp get` 全体に追加（`--format standard` / `--format openclaw` 両方で有効）
- 意味: "出力先ファイルが存在しても確認プロンプトを表示せず上書きする"
- `mcp get --help`: `Overwrite output file without confirmation`

### `--format` オプション（旧 `--tool`）

- `mcp list --tool` との意味衝突を避けるため `--format` / `-f` を採用
- `click.Choice(["standard", "openclaw"])`
- デフォルト: `"standard"`

---

## BDD シナリオ

### 正常系

#### Scenario 1: `mcp get --format openclaw` で OpenClaw 形式にエクスポート

**Given** ai-adapter に4つの MCP サーバーが登録されている:

| name | command | args | env_keys | enabled |
|------|---------|------|----------|---------|
| github | npx | ["@modelcontextprotocol/server-github"] | ["GITHUB_TOKEN"] | true |
| playwright | npx | ["@playwright/mcp@latest"] | [] | true |
| no-args | /usr/bin/python | [] | ["API_KEY"] | true |
| legacy-db | /usr/bin/python | ["server.py"] | ["DB_URL"] | false |

**When** `ai-adapter mcp get --format openclaw --path /tmp/test-out` を実行

**Then** 以下の内容で `/tmp/test-out/openclaw.json` が出力される:

```json
{
  "x-ai-adapter": {
    "version": 1,
    "managed_mcp_servers": ["github", "playwright", "no-args"]
  },
  "mcp": {
    "servers": {
      "github": {
        "enabled": true,
        "command": "npx",
        "args": ["@modelcontextprotocol/server-github"],
        "env": {
          "GITHUB_TOKEN": "${GITHUB_TOKEN}"
        }
      },
      "playwright": {
        "enabled": true,
        "command": "npx",
        "args": ["@playwright/mcp@latest"]
      },
      "no-args": {
        "enabled": true,
        "command": "/usr/bin/python",
        "env": {
          "API_KEY": "${API_KEY}"
        }
      }
    }
  }
}
```

**And** `legacy-db` は `enabled=false` のため出力に含まれない
**And** `no-args` の `args` は空のためキーごと省略される
**And** `playwright` の `env` は空のためキーごと省略される

#### Scenario 2: 既存 openclaw.json へのマージ

**Given** `~/.openclaw/openclaw.json` に既存サーバー `existing-server` が登録されている
**And** ai-adapter に `github` サーバーが登録されている（同名）

**When** `ai-adapter mcp get --format openclaw` を実行

**Then** 出力された `~/.openclaw/openclaw.json` には:
- `github`: ai-adapter の設定で上書きされる
- `existing-server`: 維持される（ai-adapter で管理外）
- `x-ai-adapter.managed_mcp_servers`: `["github"]` と記録される

#### Scenario 3: `mcp get --format standard`（従来形式）は変更なし

**Given** ai-adapter に MCP サーバーが登録されている

**When** `ai-adapter mcp get`（オプションなし = デフォルト standard）を実行

**Then** 従来通りの `.mcp.json` 形式で出力される（後方互換性確認）

#### Scenario 4: `mcp get --format openclaw --force` で上書き

**Given** 出力先に既存の `openclaw.json` が存在する

**When** `ai-adapter mcp get --format openclaw --force` を実行

**Then** 確認プロンプトなしで上書きマージされる

### 異常系

#### Scenario 5: OpenClaw 未インストール時の警告表示

**Given** `~/.openclaw/` が存在しない

**When** `ai-adapter mcp get --format openclaw` を実行（`--path` なし）

**Then** 以下の警告が表示される:
```
Warning: OpenClaw not found (~/.openclaw/ not detected). Run 'npm install -g openclaw' first.
Output written to ./openclaw.json
```

**And** カレントディレクトリに `openclaw.json` が出力される（処理は続行）

#### Scenario 6: 空の MCP 登録

**Given** MCP サーバーが1つも登録されていない（または全て disabled）

**When** `ai-adapter mcp get --format openclaw` を実行

**Then** `No enabled MCP servers registered.` と表示され、JSON は出力されない

#### Scenario 7: env キー名が OpenClaw の制約に違反

**Given** ai-adapter に `env_keys: ["myApiKey"]`（小文字+キャメルケース）のサーバーが登録されている

**When** `ai-adapter mcp get --format openclaw` を実行

**Then** 以下の警告が表示される:
```
Warning: env key 'myApiKey' may not be valid in OpenClaw format. OpenClaw only supports [A-Z_][A-Z0-9_]* pattern.
```

**And** 出力は行われる（警告のみ、処理は続行）

---

## タスク一覧

### Task 1: `export_openclaw_mcp()` ヘルパー関数の追加

**ファイル**: `src/ai_adapter/mcp.py`

**振る舞い**:
- `list[MCPServer]` を受け取り、OpenClaw 形式の辞書を返す
- `enabled=false` のサーバーは除外する
- `env` の値は `${KEY}` 形式で出力する（`env_keys` から生成）
- `env` が空の場合はキーごと出力しない
- `args` が空の場合はキーごと出力しない
- 各 env キー名を `[A-Z_][A-Z0-9_]*` パターンで検証し、違反するキーは警告を出力する（`click.echo(..., err=True)`）
- `x-ai-adapter` マーカーセクションを追加する（管理対象サーバー名のリスト）

**受け入れ条件**:
- [ ] `export_openclaw_mcp([server1, server2])` が正しい辞書を返す
- [ ] 空の `env_keys` が適切に省略される
- [ ] 空の `args` が適切に省略される
- [ ] `enabled=false` のサーバーが除外される
- [ ] 無効な env キー名に警告が出る
- [ ] `x-ai-adapter` マーカーが含まれる

### Task 2: `merge_into_openclaw_json()` マージ関数の追加

**ファイル**: `src/ai_adapter/mcp.py`（新規関数）

**振る舞い**:
- 出力先の `openclaw.json` を読み込む（なければ空の辞書から開始）
- 既存の `mcp.servers` がある場合は保持する
- サーバー名ベースでマージ:
  - 同名サーバー: 新規設定で上書き
  - 新規サーバー: 追加
  - ai-adapter にない既存サーバー: 維持
- 書き込み前に `.bak` バックアップを作成（`shutil.copy2`）
- `x-ai-adapter.managed_mcp_servers` を更新/追加する
- ファイル出力先のディレクトリがなければ作成する

**受け入れ条件**:
- [ ] 既存ファイルがない場合、新規作成される
- [ ] 既存サーバーが保持される（マージ）
- [ ] 同名サーバーが上書きされる
- [ ] `.bak` バックアップが作成される
- [ ] ディレクトリが自動生成される

### Task 3: `mcp get` に `--format` / `-f` オプション追加

**ファイル**: `src/ai_adapter/mcp.py`

**振る舞い**:
- `--format` / `-f` オプションを `click.Choice(["standard", "openclaw"])` で追加
- デフォルト値: `"standard"`
- `--format openclaw` の場合:
  - `export_openclaw_mcp()` で形式変換
  - `merge_into_openclaw_json()` で出力先に書き込み
- `--format standard` の場合: 従来通りの動作（`--path` 先に `.mcp.json`）
- `--force` オプションを追加（両方の形式で有効）
  - 意味: 出力先ファイルが存在しても確認プロンプトを表示せず上書き
- `--path` のヘルプテキストを更新（フォーマット別のファイル名を明記）

**受け入れ条件**:
- [ ] `ai-adapter mcp get --format openclaw` で OpenClaw 形式出力
- [ ] `ai-adapter mcp get`（オプションなし）= 従来の `.mcp.json` 出力
- [ ] `ai-adapter mcp get --force` で確認プロンプトなし
- [ ] 無効な `--format` 値でエラーメッセージ

### Task 4: テストの追加

**ファイル**: `tests/test_mcp.py`

**振る舞い**:

| テスト名 | 分類 | 検証内容 |
|---------|------|---------|
| `test_export_openclaw_basic` | 単体 | 4サーバー（正常・空env・空args・disabled）の変換結果 |
| `test_export_openclaw_disabled_excluded` | 単体 | disabled サーバーが除外される |
| `test_export_openclaw_empty_env_omitted` | 単体 | 空 env が省略される |
| `test_export_openclaw_empty_args_omitted` | 単体 | 空 args が省略される |
| `test_export_openclaw_invalid_env_key_warning` | 単体 | 無効な env キー名に警告が出る |
| `test_export_openclaw_x_ai_adapter_marker` | 単体 | x-ai-adapter マーカーが含まれる |
| `test_merge_into_openclaw_new_file` | 単体 | 新規ファイル作成 |
| `test_merge_into_openclaw_merge` | 単体 | 既存サーバー保持 + 同名上書き |
| `test_cli_mcp_get_openclaw` | CLI | `--format openclaw` で JSON ファイル出力 |
| `test_cli_mcp_get_standard_still_works` | CLI | 後方互換: standard が従来通り動作 |
| `test_cli_mcp_get_openclaw_not_installed` | CLI | `~/.openclaw/` なし時の警告（--path 指定で回避） |
| `test_cli_mcp_get_no_servers` | CLI | 空 MCP → エラーメッセージ + ファイル出力なし |
| `test_cli_mcp_get_force_overwrite` | CLI | `--force` で確認プロンプトスキップ |

**受け入れ条件**:
- [ ] 全13テストが通る
- [ ] 既存の全テストに影響がない

---

## データ構造（テストフィクスチャ）

```python
# テスト用のサーバーデータ
SERVER_GITHUB = MCPServer(
    name="github",
    command="npx",
    args=["@modelcontextprotocol/server-github"],
    env_keys=["GITHUB_TOKEN"],
    enabled=True,
)

SERVER_PLAYWRIGHT = MCPServer(
    name="playwright",
    command="npx",
    args=["@playwright/mcp@latest"],
    env_keys=[],
    enabled=True,
)

SERVER_NO_ARGS = MCPServer(
    name="no-args",
    command="/usr/bin/python",
    args=[],
    env_keys=["API_KEY"],
    enabled=True,
)

SERVER_DISABLED = MCPServer(
    name="legacy-db",
    command="/usr/bin/python",
    args=["server.py"],
    env_keys=["DB_URL"],
    enabled=False,
)

SERVER_INVALID_ENV_KEY = MCPServer(
    name="bad-env",
    command="node",
    args=["server.js"],
    env_keys=["myApiKey"],  # 小文字キャメルケース → 警告対象
    enabled=True,
)
```

---

## 参考リソース

- OpenClaw Configuration: https://docs.openclaw.ai/gateway/configuration
- OpenClaw MCP env 解決検証レポート: `documents/plans/dev/issues/20260727_openclaw_env_resolution.md`
- Plan Architect レビュー指摘: `documents/plans/dev/issues/20260727_review_openclaw_export.md`
- 既存 `mcp.py`: `src/ai_adapter/mcp.py`
- 既存テスト: `tests/test_mcp.py`
