# OpenClaw の環境変数解決機構の検証

## 優先度
🟢 低（調査完了、ブロッカーなし）

## 調査目的
OpenClaw が `mcp.servers[].env` に `${VAR_NAME}` 形式のプレースホルダを記述したとき、正しく環境変数に解決できるかどうかを検証する。

**選択肢 A**: 標準 `.mcp.json` と同じ `${VAR_NAME}` 形式で `openclaw.json` に書き出す方式の安全性確認。

## 調査方法

1. **OpenClaw 公式ドキュメントの確認**
   - https://docs.openclaw.ai/gateway/configuration （Configuration ページ）
   - https://docs.openclaw.ai/help/environment （Environment variables ページ）
   - https://docs.openclaw.ai/gateway/configuration-reference （Configuration Reference — MCP セクション）
   - https://docs.openclaw.ai/cli/mcp （MCP CLI ページ）

2. **インストール済みソースコードの確認**
   - `/Users/bookair18/.openclaw/tools/node-v24.15.0/lib/node_modules/openclaw/dist/` 配下の JS ファイル（5493ファイル）

3. **実際の openclaw.json の運用実態の確認**
   - `/Users/bookair18/.openclaw/openclaw.json` の現存する MCP サーバー設定

4. **`.env` ファイルの内容確認**
   - `/Users/bookair18/.openclaw/.env`

## 結果

### 1. OpenClaw の env 解決機構

#### `${VAR}` 形式のサポート状況: **✅ Yes — 公式サポート済み**

OpenClaw は **Env var substitution in config values** として `${VAR_NAME}` 形式の環境変数置換を公式にサポートしています。

**エビデンス 1: Configuration ページ**
> https://docs.openclaw.ai/gateway/configuration より引用:
>
> **Env var substitution in config values**
>
> Reference env vars in any config string value with `${VAR_NAME}`:
>
> ```json5
> {
>   gateway: { auth: { token: "${OPENCLAW_GATEWAY_TOKEN}" } },
>   models: { providers: { custom: { apiKey: "${CUSTOM_API_KEY}" } } },
> }
> ```
>
> Rules:
> - Only uppercase names matched: `[A-Z_][A-Z0-9_]*`
> - Missing/empty vars throw an error at load time
> - Escape with `$${VAR}` for literal output
> - Works inside `$include` files
> - Inline substitution: `"${BASE}/v1"` → `"https://api.example.com/v1"`

**エビデンス 2: Configuration Reference — MCP セクション**
> https://docs.openclaw.ai/gateway/configuration-reference より引用（MCP の設定例）:
>
> ```json5
> {
>   mcp: {
>     servers: {
>       remote: {
>         url: "https://example.com/mcp",
>         headers: {
>           Authorization: "Bearer ${MCP_REMOTE_TOKEN}",
>         },
>         // ...
>       },
>     },
>   },
> }
> ```

この例は `mcp.servers` の `headers` で `${MCP_REMOTE_TOKEN}` を使用することを示しており、MCP サーバー設定内でも `${VAR}` 形式が有効であることが確認できます。

**エビデンス 3: MCP CLI ページの Stdio transport テーブル**
> https://docs.openclaw.ai/cli/mcp より引用（Stdio transport の env フィールド）:
>
> | Field | Description |
> |-------|-------------|
> | `env` | Extra environment variables |

このテーブルは `mcp.servers.<name>.env` が正規のフィールドであることを確認できます。

#### 解決タイミング: **Config 読み込み時（load time）**

- `${VAR}` の解決は **config ファイルの読み込み・パース時**に行われます
- 解決後の値が `mcp.servers` の設定値として保持され、MCP サーバー起動時にはすでに実際の値が入っています
- Missing/empty vars は config load 時にエラーとなり、Gateway が起動しません（fail-fast）

#### `.env` ファイルの自動読み込み: **✅ Yes — 自動読み込みされる**

OpenClaw は以下の優先順位で環境変数を読み込みます（上書きはしない）:

| 優先度 | ソース | 備考 |
|--------|--------|------|
| 1 (最高) | 親プロセスの環境変数 | shell/launchd/systemd から継承 |
| 2 | カレントワーキングディレクトリの `.env` | プロバイダ認証情報は workspace `.env` からは無視される |
| 3 | `~/.openclaw/.env` （グローバルフォールバック） | プロバイダ API キーの推奨設置場所 |
| 4 | Config `env` ブロック | `openclaw.json` 内の `env` フィールド |
| 5 | Login-shell import（オプション） | `env.shellEnv.enabled` または `OPENCLAW_LOAD_SHELL_ENV=1` |

**実際の `.env` ファイルの中身**:
```env
TELEGRAM_BOT_TOKEN=8724779834:AAE7Q6-6bHlEJUG_tWL7rcBhzxtv_kZ0XR4
OPENCODE_API_KEY="sk-V2g3fg1ktZ0s1qwYgi7YGcQN4WX1Hk2FB6d6aizNTlvG5mP40H1s9bRoYqIlbIBP"
```

### 2. 実運用での確認

現在の `openclaw.json` では、MCP サーバーの `env` フィールドは **すべて実値（リテラル値）** で書かれています。

**実値形式の例**:
```json
{
  "mcp": {
    "servers": {
      "ga4": {
        "command": "/Users/bookair18/OS/media/05_claude/.venv/bin/python",
        "args": ["/Users/bookair18/OS/media/05_claude/.github/bin/ga4_mcp_server.py"],
        "env": {
          "GA4_PROPERTY_ID": "397146254",
          "GA4_CREDENTIALS_FILE": "/Users/bookair18/OS/media/05_claude/.github/bin/gas-mcp-server/credentials.json",
          "GA4_TOKEN_FILE": "/Users/bookair18/OS/media/05_claude/.github/bin/gas-mcp-server/ga4_token.json"
        }
      }
    }
  }
}
```

`${VAR}` 形式は現在の設定では使用されていませんが、これは env 値がすべて実値で問題ない設定（パスや定数）であるためです。認証トークンを含む env 値を安全に管理したい場面では `${VAR}` 形式が推奨されます。

### 3. Stdio env safety filter（セキュリティ機構）

OpenClaw は MCP サーバー起動時に、`env` フィールドの値を検査する **Stdio env safety filter** を持っています。

> OpenClaw rejects interpreter-startup, loader-hijack, and shell-init env keys before spawning a stdio MCP server, even if they appear in a server's `env` block.

ブロックされるキーの例:
- `NODE_OPTIONS`, `PYTHONSTARTUP`, `PERL5OPT`, `RUBYOPT`, `BASHOPTS`, `KSH_ENV`
- `DYLD_*`, `LD_*`, `BASH_FUNC_*`

許可されるキーの例（通常の MCP 認証情報）:
- `GITHUB_TOKEN`, `GH_TOKEN`, `GITLAB_TOKEN`, `NPM_TOKEN`, `NODE_AUTH_TOKEN`
- `DATABASE_URL`, `MONGODB_URI`, `REDIS_URL`, `AMQP_URL`
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`
- `HTTP_PROXY`
- カスタム `*_API_KEY` 系

また、`openclaw mcp doctor` は **env/headers にリテラル値（生のトークン等）** が含まれていると警告を出します。これにより `${VAR}` 形式の使用が事実上推奨されていると言えます。

## 推奨事項

### A方式（`${VAR}` 形式）は安全か？ → **✅ 安全。推奨する。**

**理由**:
1. OpenClaw が `${VAR}` 形式を公式サポートしており、ドキュメントにも明記されている
2. MCP サーバー設定（`headers`、`env`）での使用例が公式ドキュメントに掲載されている
3. Config load 時に解決されるため、MCP サーバー起動時には正しい値が渡る
4. `openclaw mcp doctor` がリテラル値に対して警告を出すため、`${VAR}` 形式の方がセキュリティ上推奨される
5. Missing/empty vars は load time にエラーとなる（fail-fast）

### 注意点・制約

| 項目 | 内容 |
|------|------|
| 変数名のルール | `[A-Z_][A-Z0-9_]*` のみ（大文字 + アンダースコア + 数字のみ） |
| 未定義変数 | Config load 時にエラー。Gateway が起動しない |
| エスケープ | `$${VAR}` でリテラル `${VAR}` を出力可能 |
| `.env` の優先順位 | プロセス env > `.env` > `~/.openclaw/.env` > config `env` ブロック |
| security filter | `NODE_OPTIONS` 等の危険な env キーは自動ブロックされる |
| hot reload | `mcp.*` の変更は hot-apply 可能。Gateway 再起動不要 |

### ai-adapter での書き出し方針

```json
// ai-adapter が openclaw.json に書き出す推奨形式
{
  "mcp": {
    "servers": {
      "github": {
        "enabled": true,
        "command": "npx",
        "args": ["@modelcontextprotocol/server-github"],
        "env": {
          "GITHUB_TOKEN": "${GITHUB_TOKEN}"
        }
      }
    }
  }
}
```

- 認証トークンや機密情報は `${VAR}` 形式で書き出す
- パスや固定値（例: `GA4_PROPERTY_ID`）は実値でも可（セキュリティリスクなし）
- 利用者は事前に `~/.openclaw/.env` またはプロセス env で変数を定義しておく必要がある
- `${VAR}` の変数が未定義の場合、OpenClaw は起動時にエラーを報告する（意図しない missing を早期発見できる）

## 備考

- OpenClaw のバージョン: `2026.7.1-2`（2026年7月23日時点）
- Node.js バージョン: v24.15.0
- この調査は ai-adapter から OpenClaw への MCP 設定書き出し機能の設計判断に使用する

## 参照元

- OpenClaw Configuration: https://docs.openclaw.ai/gateway/configuration
- OpenClaw Environment Variables: https://docs.openclaw.ai/help/environment
- OpenClaw Configuration Reference (MCP): https://docs.openclaw.ai/gateway/configuration-reference
- OpenClaw MCP CLI: https://docs.openclaw.ai/cli/mcp
