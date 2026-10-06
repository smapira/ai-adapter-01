# 設計書 08: VS Code エディタ設定 + .vscode/mcp.json + .github/instructions デプロイ

- 日付: 2026-10-06
- 作成者: Product Manager
- 状態: ドラフト
- 上位計画: [platform_parity_master_design](./20261006_platform_parity_master_design.md)
- 優先度: P1
- 想定規模: 中（新規 provider + 既存 instruction デプロイの拡張）

---

## 1. 目的

VS Code 関連のギャップを解消する。2 つの独立した領域をカバーする。

### 対象ギャップ

**領域 A: Copilot / .github/ デプロイの不整合**

| 行 | パス | 現状 |
|----|------|------|
| 54 | `.github/copilot-instructions.md` | ⚠️ opencode.json の fallback として参照されるが、scan 検出はルート直下のみ |
| 55 | `.github/instructions/**/*.instructions.md` | ⚠️ scan は検出するが、instruction デプロイ先はプロジェクトルート |

**領域 B: VS Code エディタ設定（新規）**

| 行 | パス | 現状 |
|----|------|------|
| 53 | `.vscode/settings.json` | ❌ |
| 57 | `.vscode/mcp.json` | ❌ |
| 61 | `.vscode/launch.json` | ❌ |
| 62 | `.vscode/extensions.json` | ❌ |
| 63 | `.vscode/tasks.json` | ❌ |

---

## 2. アプローチ

### 2.1 領域 A: instruction デプロイパスの拡張

**現状の問題**:
- `instruction get` は `get_github_instructions_dir()` で**プロジェクトルート**へデプロイ
- scan は `.github/instructions/` を検出するが、デプロイ先が異なる
- `.github/copilot-instructions.md` は opencode.json の fallback として参照されるが、直接配置されない

**方針**: `--path` オプションでデプロイ先を明示指定できるようにする。

```bash
# 現状（変更なし）
ai-adapter agent get <name>
# → ./.<name>（プロジェクトルート）

# 新規: .github/instructions/ へ
ai-adapter agent get <name> --path .github/instructions
# → ./.github/instructions/<name>

# 新規: .github/copilot-instructions.md として
ai-adapter agent get copilot-instructions --path .github --as copilot-instructions.md
# → ./.github/copilot-instructions.md
```

**簡易版（推奨）**: `--target` オプションで既知のパスを指定

```bash
--target root          # デフォルト: プロジェクトルート
--target github-instructions  # .github/instructions/
--target github-copilot      # .github/copilot-instructions.md
```

**`--format` と `--target` の相互作用（Plan Architect 指摘 M8-1）**:
- `--target` 指定時は `--format` を `standard` に固定（排他）
- `--format`（設計書 01 のプラットフォーム選択）と `--target` の併用は**エラー**
- 例: `--format gemini --target github-instructions` → エラー「--target is incompatible with --format」

**受け入れ条件**:
- AC1: `--target` 省略時は既存動作（ルート配置）
- AC2: `github-instructions` ターゲットで `.github/instructions/` に配置
- AC3: `github-copilot` ターゲットで `.github/copilot-instructions.md` に配置
- AC4: scan が `.github/copilot-instructions.md` を instruction として検出（現状はルートのみ）

---

### 2.2 領域 B: VS Code エディタ設定 provider

**方針**: 新規 provider `src/ai_adapter/providers/vscode.py` を作成。
ただし **責務を最小限に**留める。

**管理対象（Phase A）**:
- `.vscode/mcp.json` — MCP サーバー定義（Copilot / VS Code 拡張用）
- `.vscode/extensions.json` — 推奨拡張機能リスト

**管理対象外（将来）**:
- `.vscode/settings.json` — ユーザーのエディタ設定（テーマ、フォント等）。破壊リスク高
- `.vscode/launch.json` — デバッグ設定（プロジェクト固有）
- `.vscode/tasks.json` — タスク定義（`bin` とマッピング可能だが複雑）

#### `.vscode/mcp.json` の形式

VS Code の MCP 拡張は `.vscode/mcp.json` を使用する。
**Claude の `.mcp.json` とはキー名が異なる**:

```json
// .vscode/mcp.json（VS Code 形式）
{
  "servers": {
    "server-name": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "mcp-x"],
      "env": { "API_KEY": "${env:API_KEY}" }  # VS Code の設定変数構文（要公式ドキュメント確認）
    }
  }
}

// .mcp.json（Claude Code 標準形式）
{
  "mcpServers": {
    "server-name": {
      "command": "npx",
      "args": ["-y", "mcp-x"],
      "env": { "API_KEY": "${env:API_KEY}" }  # VS Code の設定変数構文（要公式ドキュメント確認）
    }
  }
}
```

**変換ポイント**:
- キー: `mcpServers` → `servers`
- 各サーバーに `"type": "stdio"` を追加（stdio のみ対応）

#### `.vscode/extensions.json` の形式

```json
{
  "recommendations": [
    "ms-vscode.copilot-chat",
    "ms-vscode.cpptools"
  ]
}
```

**管理モデル**: 
- `extensions.json` は **手動で推奨拡張を追加できる CLI** を提供
- store に `vscode_extensions` リストを持たない（新しいモデル追加は複雑）
- `ai-adapter vscode extension add <id>` で `.vscode/extensions.json` に追記

---

### 2.3 CLI サブコマンド

```bash
# VS Code グループ
ai-adapter mcp get --format vscode
  # → .vscode/mcp.json を生成（既存 mcp get の format 選択肢として追加）

ai-adapter vscode install
  # → .vscode/mcp.json を生成 + extensions.json 等の統合エントリポイント

ai-adapter vscode install --project-dir <path>
  # → <path>/.vscode/mcp.json を生成（`--project-dir` を使用。設計書 01 のオプション統一方針に準拠）

ai-adapter vscode extension add <extension-id>
  # → .vscode/extensions.json の recommendations に追記

ai-adapter vscode extension list
  # → .vscode/extensions.json の一覧表示

ai-adapter vscode validate
  # → .vscode/mcp.json, extensions.json を検証
```

### 2.4 scan 拡張

```python
def scan_vscode(project_dir: Path) -> list[ScanItem]:
    """Detect VS Code configurations."""
    items = []
    vscode_dir = project_dir / ".vscode"
    if not vscode_dir.is_dir():
        return items
    # mcp.json
    mcp = vscode_dir / "mcp.json"
    if mcp.is_file():
        items.append(ScanItem("vscode", "settings", "mcp.json", path=mcp))
        items.extend(_scan_mcp_servers_vscode("vscode", mcp, ".vscode/mcp.json"))
    # extensions.json
    ext = vscode_dir / "extensions.json"
    if ext.is_file():
        items.append(ScanItem("vscode", "settings", "extensions.json", path=ext))
    # launch.json, tasks.json（scan でのみ検出）
    for fname in ("launch.json", "tasks.json"):
        f = vscode_dir / fname
        if f.is_file():
            items.append(ScanItem("vscode", "settings", fname, path=f))
    return items
```

**TOOL_ORDER（マスター設計 2.7 準拠）**: `vscode` のみを append（タプル全体の再定義を禁止）。
既存: `("claude", "codex", "cursor", "opencode", "project")` → 追加後: `("claude", "codex", "cursor", "opencode", "vscode", "project")`
**注意**: gemini / zed は未実装のため本設計書の TOOL_ORDER に含めない（各設計書で個別に append）。
**必須**: `TOOL_LABELS["vscode"]` へのラベル追加、`scan_all` への `items.extend(scan_vscode(...))` 登録。

---

## 3. BDD タスク分解

### タスク 08-1: `agent get --target github-instructions`

**期待する振る舞い**:
- 入力: `ai-adapter agent get STYLE.md --target github-instructions`
- 応答: `./.github/instructions/STYLE.md` に配置
- 入力: `.github/instructions/` が存在しない
- 応答: ディレクトリを作成して配置
- 入力: `--target` なし（デフォルト）
- 応答: 従来どおりプロジェクトルートに配置

**受け入れ条件**:
- AC1: `--target` 省略時は既存動作（後方互換）
- AC2: `github-instructions` ターゲットで `.github/instructions/` に配置
- AC3: 既存ファイルは確認プロンプト

**データ（仕様例）**:
```
$ ai-adapter agent get STYLE.md --target github-instructions
Instruction 'STYLE' copied to ./.github/instructions/STYLE.md.
```

---

### タスク 08-2: `agent get --target github-copilot`

**期待する振る舞い**:
- 入力: `ai-adapter agent get AGENTS.md --target github-copilot`
- 応答: `./.github/copilot-instructions.md` に配置
  - instruction の内容をそのままコピー

**受け入れ条件**:
- AC1: ファイル名は `copilot-instructions.md` に固定
- AC2: 既存 `.github/copilot-instructions.md` は確認プロンプト

**データ（仕様例）**:
```
$ ai-adapter agent get AGENTS.md --target github-copilot
Instruction content written to ./.github/copilot-instructions.md.
```

---

### タスク 08-3: scan 拡張（.github/copilot-instructions.md）

**期待する振る舞い**:
- 入力: `ai-adapter scan`（`.github/copilot-instructions.md` が存在）
- 応答: `ScanItem(tool="project", category="instruction", name="copilot-instructions.md")` を検出
- 入力: `.github/instructions/*.instructions.md` が存在
- 応答: 既存どおり instruction として検出（変更なし）

**受け入れ条件**:
- AC1: `scan_project` が `.github/copilot-instructions.md` を検出
- AC2: 既存のルート `copilot-instructions.md` 検出は維持

---

### タスク 08-4: `vscode install`

**期待する振る舞い**:
- 入力: `ai-adapter vscode install`（MCP サーバーが登録済み）
- 応答: `.vscode/mcp.json` を生成
  - store の enabled サーバーを VS Code 形式（`servers` + `type: stdio`）で出力
- 入力: `.vscode/mcp.json` が既に存在
- 応答: 確認プロンプト後、merge（非管理サーバー preserve）
- 入力: store が空
- 応答: 「No MCP servers registered.」

**受け入れ条件**:
- AC1: 出力形式は VS Code の `servers` キー + `type: "stdio"`
- AC2: merge は `.bak` バックアップ
- AC3: 既存非管理サーバーは preserve
- AC4: **stdio のみ出力**。http / sse 型の MCP サーバーが登録されている場合は**警告を出力**してスキップ
- AC5: env 値は VS Code の `${env:API_KEY}` 形式で出力（要公式ドキュメント確認）

**データ（仕様例）**:
```
# store: mcp_servers = [{name: "github", command: "npx", args: ["-y", "@modelcontextprotocol/server-github"]}]

$ ai-adapter vscode install
VS Code MCP configuration installed:
  .vscode/mcp.json

# .vscode/mcp.json 内容
{
  "servers": {
    "github": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "API_KEY": "${env:API_KEY}" }
    }
  }
}
```

---

### タスク 08-5: `vscode extension add`

**期待する振る舞い**:
- 入力: `ai-adapter vscode extension add ms-vscode.copilot-chat`
- 応答: `.vscode/extensions.json` の recommendations に追加
  - 既存ファイルがない場合は新規作成
  - 既に存在する場合は重複チェックしてから追加
- 入力: 既に登録済みの拡張
- 応答: 「Extension already recommended.」

**受け入れ条件**:
- AC1: `.vscode/extensions.json` が存在しない場合は作成
- AC2: 重複追加は行わない
- AC3: 既存の recommendations は preserve

**データ（仕様例）**:
```
$ ai-adapter vscode extension add ms-vscode.copilot-chat
Extension 'ms-vscode.copilot-chat' added to .vscode/extensions.json.

$ ai-adapter vscode extension list
Recommended extensions:
  - ms-vscode.copilot-chat
  - ms-vscode.cpptools
```

---

### タスク 08-6: `vscode validate`

**期待する振る舞い**:
- 入力: `ai-adapter vscode validate`
- 応答: 以下を検証
  - `.vscode/mcp.json` の JSON パース + servers 形式
  - `.vscode/extensions.json` の JSON パース + recommendations 形式
- 入力: エラーなし
- 応答: 「VS Code configuration is valid.」

**受け入れ条件**:
- AC1: `opencode validate` を参考にした UX（`--json` は新設）
- AC2: `--json` オプションで構造化出力（**新設**: opencode validate には `--json` は存在しない）

---

## 4. 変更対象ファイル

| ファイル | 変更内容 |
|----------|----------|
| `src/ai_adapter/providers/vscode.py` | **新規** provider |
| `src/ai_adapter/commands/instruction.py` | `--target` オプション追加 |
| `src/ai_adapter/commands/mcp.py` | `--format vscode` 選択肢追加（`.vscode/mcp.json` 出力） |
| `src/ai_adapter/scan.py` | `scan_vscode` + `.github/copilot-instructions.md` 検出 + TOOL_ORDER |
| `src/ai_adapter/cli.py` | `vscode_group` 登録 |
| `src/ai_adapter/commands/doctor.py` | vscode 設定の診断追加 |
| `tests/test_vscode.py` | **新規** |
| `tests/test_agent.py` | `--target` のテスト |
| `tests/test_scan.py` | vscode 検出 + copilot-instructions 検出 |

---

## 5. テスト計画

```bash
bash scripts/run_tests.sh tests/test_vscode.py
bash scripts/run_tests.sh tests/test_agent.py -k target
bash scripts/run_tests.sh tests/test_scan.py -k vscode
```

### 主要テストケース

| # | ケース | 期待結果 |
|---|--------|----------|
| T1 | `agent get --target github-instructions` | `.github/instructions/` 配置 |
| T2 | `agent get --target github-copilot` | `.github/copilot-instructions.md` 配置 |
| T3 | `agent get`（--target なし） | ルート配置（回帰） |
| T4 | scan（.github/copilot-instructions.md） | 検出 |
| T5 | `vscode install` | `.vscode/mcp.json` 生成 |
| T6 | `vscode install`（既存 mcp.json） | merge + preserve |
| T7 | `vscode extension add`（新規） | extensions.json 生成 |
| T8 | `vscode extension add`（重複） | 「already recommended」 |
| T9 | `vscode validate`（正常） | valid 判定 |
| T10 | `vscode validate`（mcp.json 破損） | エラー表示 |
| T11 | `--format gemini --target github-instructions` | エラー（排他） |
| T12 | `mcp get --format vscode` | `.vscode/mcp.json` 生成 |

---

## 6. リスクと対策

| リスク | 対策 |
|--------|------|
| VS Code MCP 形式の変更 | validate で形式検証。README に形式を明記 |
| `.github/` と `.vscode/` の責務混同 | README で「Copilot (.github/)」と「VS Code エディタ (.vscode/)」を区別 |
| `--target` オプションの複雑化 | ターゲット名を enum で限定（root / github-instructions / github-copilot） |
| settings.json / launch.json / tasks.json の破壊リスク | 本設計書では**管理しない**（scan 検出のみ） |

---

## 7. 完了定義

- [ ] `agent get --target github-instructions` が動作
- [ ] `agent get --target github-copilot` が動作
- [ ] scan が `.github/copilot-instructions.md` を検出
- [ ] `vscode install` が `.vscode/mcp.json` を生成
- [ ] `vscode extension add` が extensions.json を管理
- [ ] `vscode validate` が設定を検証
- [ ] 既存 instruction デプロイのテストが全て通過（後方互換）
- [ ] README の VS Code セクション更新
