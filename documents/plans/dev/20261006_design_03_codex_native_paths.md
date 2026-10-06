# 設計書 03: OpenAI Codex ネイティブパス対応

- 日付: 2026-10-06
- 作成者: Product Manager
- 状態: ドラフト
- 上位計画: [platform_parity_master_design](./20261006_platform_parity_master_design.md)
- 優先度: P1
- 想定規模: 中（provider 拡張 + TOML 変換）
- 依存: 設計書 01（User スコープ AGENTS.md）

---

## 1. 目的

Codex CLI の**ネイティブパス**（TOML 設定 / rules / .agents/skills）を管理できるようにする。

### 対象ギャップ

| 行 | パス | スコープ | 現状 |
|----|------|----------|------|
| 2 | `<agent-config>.toml`（agents.<name>.config_file 参照） | User/Project | ❌ |
| 3 | `.codex/config.toml` | Project | ❌ |
| 4 | `~/.codex/config.toml` | User | ⚠️ scan のみ |
| 7 | `~/.codex/rules/*.rules` | User | ❌ |
| 8 | `.agents/skills/<name>/SKILL.md` | Project | 🔄 AGENTS.md 経由 |
| 9 | `~/.agents/skills/` / `~/.codex/skills` | User | ⚠️ scan のみ |

**現状**: Codex は `codex install` で AGENTS.md を生成する**互換モードのみ**。
ネイティブ TOML 設定と rules は未対応。

---

## 2. アプローチ

### 2.1 段階的実装

| Phase | 内容 | 対象行 |
|-------|------|--------|
| A | config.toml の MCP/agents セクション管理 | 3, 4 |
| B | `.agents/skills/` デプロイ | 8, 9 |
| C | TOML サブエージェント定義生成 | 2 |
| D | rules ディレクトリ管理 | 7 |

本設計書は **Phase A + B** を対象とする。Phase C/D は将来イテレーション。

### 2.2 Phase A: config.toml MCP セクション管理

Codex の MCP サーバーは `~/.codex/config.toml` の `[mcp_servers.<name>]` で定義される。

**方針**: TOML の **merge** で管理（全体生成ではない）。

**重要（Plan Architect 指摘 M1 反映）**: 既存 `mcp get --format standard/openclaw/cursor` は
全て**プロジェクト（cwd）基準**の出力である。codex のみ user home 基準にすると
同一コマンドで書き込み先の性質が変わるため、**`--scope` モデルを 01/04 と統一する**。

| format | デフォルト出力先（`--scope project`） | `--scope user` |
|--------|--------------------------------------|----------------|
| `standard` | `<cwd>/.mcp.json` | —（非対応） |
| `openclaw` | `<cwd>/openclaw.json` | —（非対応） |
| `cursor` | `<cwd>/.cursor/mcp.json` | —（非対応） |
| `codex` | `<cwd>/.codex/config.toml` | `~/.codex/config.toml` |

**マージ対象**（プロジェクト config.toml）:
```toml
# <project>/.codex/config.toml（例）
model = "gpt-5"

[mcp_servers.managed-server]
command = "npx"
args = ["-y", "mcp-x"]

[mcp_servers.existing-unmanaged]
command = "node"
args = ["server.js"]
```

**ai-adapter の操作**:
- 管理対象（store の mcp_servers）を `[mcp_servers.<name>]` に upsert
- 非管理サーバーは preserve
- `model` 等の他セクションは**読み取り専用**

**CLI**:
```bash
ai-adapter mcp get --format codex
# → <cwd>/.codex/config.toml の [mcp_servers] をマージ（デフォルト project）

ai-adapter mcp get --format codex --scope user
# → ~/.codex/config.toml をマージ

ai-adapter mcp get --format codex --path <dir>
# → <dir>/.codex/config.toml をマージ
```

### 2.3 Phase B: `.agents/skills/` デプロイ

Codex の Skill は `.agents/skills/<name>/SKILL.md`（プロジェクト）と
`~/.agents/skills/<name>/SKILL.md`（ユーザー）で探索される。

**方針（Plan Architect 指摘 M4 反映）**: **正本は `~/.agents/skills/`**（仕様準拠パス）。
`~/.codex/skills/` へのコピーは**明示的なオプトイン**とする（二重ステートによるドリフト防止）。

```bash
# 正本デプロイ（プロジェクト）
ai-adapter skill get-all --format codex
# → .agents/skills/<name>/SKILL.md に配置

# 正本デプロイ（ユーザー）
ai-adapter skill get-all --format codex --scope user
# → ~/.agents/skills/<name>/SKILL.md に配置

# 互換コピー（オプトイン）
ai-adapter skill get-all --format codex --scope user --also-codex-dir
# → ~/.agents/skills/ + ~/.codex/skills/ の両方にコピー
```

**注意**: scan_codex は現在 `~/.codex/skills/` を検出している。
正本を `~/.agents/skills/` に置く場合、scan は**両パスを検出**し、
同一スキルが両方に存在する場合は「互換コピー」として区別表示する。

**フォーマット名**: `codex-agents` ではなく **`codex`** に統一
（既存の standard/openclaw/cursor と同じプラットフォーム名パターンに合わせる）。

### 2.4 TOML ヘルパー（新規）

```python
# src/ai_adapter/providers/codex.py に追加

def export_mcp_toml(servers: list[MCPServer]) -> dict:
    """Export MCP servers as Codex config.toml mcp_servers section."""
    # → {"mcp_servers": {name: {"command": ..., "args": [...]}}}

def merge_into_config_toml(path: Path, mcp_data: dict, force: bool = False) -> None:
    """Merge mcp_servers into existing config.toml preserving other sections."""
```

**TOML コメント保持（Plan Architect 指摘 M3 反映・必須要件）**:

`tomllib` → `tomli-w` のラウンドトリップは **config.toml のコメントとキー順を丸ごと破壊する**。
`model` / `approval_policy` 等の手書きコメントは失われるため、`.bak` 復元しか救いがない。
**以下のいずれかを採用する（実装時に確定）**:

| 方式 | 手法 | 利点 | 欠点 |
|------|------|------|------|
| (a) text-splice | `[mcp_servers.*]` セクションのみをテキストで差し替え | 依存追加なし。コメント完全保持 | TOML パーサ実装が必要 |
| (b) tomlkit | `tomlkit` を採用（コメント・キー順保持ライブラリ） | 実装が容易 | 新規依存追加 |

**推奨**: **(a) text-splice**（依存を増やさず、コメント完全保持できるため）。
実装方針:
1. 既存 config.toml をテキストとして読み込む
2. `[mcp_servers.*]` セクションの範囲を検出
3. 管理管理対象のサーバーのみをテキストで差し替え（非管理はそのまま）
4. セクションが存在しない場合は末尾に追記

**Python 3.10 対応（Plan Architect 指摘 M2 反映）**:

`pyproject.toml` は `requires-python = ">=3.10"` だが、`tomllib` は 3.11+ の標準ライブラリ。

```python
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]
```

- 読み取り: 上記フォールバック
- 書き出し: text-splice 方式のためライブラリ不要（tomli-w 不要）
- `tomli` は Python 3.10 向けトランジティブ依存として uv.lock に既存

---

## 3. BDD タスク分解

### タスク 03-1: `mcp get --format codex`（config.toml マージ）

**期待する振る舞い**:
- 入力: `ai-adapter mcp get --format codex`
- 応答: `<cwd>/.codex/config.toml` の `[mcp_servers]` セクションを更新（デフォルト project）
  - store の enabled サーバーを upsert
  - 非管理サーバーは preserve
  - 他セクション（model, approval_policy 等）は **コメント含め preserve**
- 入力: `ai-adapter mcp get --format codex --scope user`
- 応答: `~/.codex/config.toml` をマージ
- 入力: config.toml が存在しない
- 応答: 新規作成（`[mcp_servers]` のみ）
- 入力: `~/.codex/auth.json` が存在
- 応答: **絶対に読まない・書かない**（SCAN_IGNORE_PATTERNS 同様の保護）

**受け入れ条件**:
- AC1: merge 前に `.codex/config.toml.bak` を作成
- AC2: TOML のコメント・キー順序を**完全に保持**（text-splice 方式）
- AC3: env 値は `"${ENV_KEY}"` 文字列に変換
- AC4: `--force` で確認プロンプト省略
- AC5: `auth.json` へのアクセスをテストで禁止
- AC6: デフォルト出力先は project（`--scope` で user に切り替え）

**データ（仕様例）**:
```
# 既存 <cwd>/.codex/config.toml
# Primary model for Codex CLI
model = "gpt-5"
approval_policy = "untrusted"

[mcp_servers.legacy]
command = "node"
args = ["legacy.js"]

# ai-adapter store: mcp_servers = [{name: "new-mcp", command: "npx", args: ["-y", "x"]}]

# 実行後（コメントとキー順が保持される）
# Primary model for Codex CLI
model = "gpt-5"
approval_policy = "untrusted"

[mcp_servers.legacy]
command = "node"
args = ["legacy.js"]

[mcp_servers.new-mcp]
command = "npx"
args = ["-y", "x"]
```

---

### タスク 03-2: project `.codex/config.toml` 対応

**期待する振る舞い**:
- 入力: `ai-adapter mcp get --format codex`（デフォルト project）
- 応答: `<cwd>/.codex/config.toml` をマージ
- 入力: `ai-adapter mcp get --format codex --scope user`
- 応答: `~/.codex/config.toml` をマージ（User のものとは別ファイル）
- 入力: `ai-adapter scan`（project に `.codex/config.toml` が存在）
- 応答: `ScanItem(tool="codex", category="settings", name=".codex/config.toml")` を検出

**受け入れ条件**:
- AC1: User スコープと Project スコープの config.toml を**同一コマンドで別々に**管理可能
- AC2: scan が project `.codex/config.toml` を検出（現在は User のみ）
- AC3: `--scope` デフォルトは project（既存 mcp get との一貫性）

**データ（仕様例）**:
```
$ ai-adapter scan
Codex:
  settings: 2
    - ~/.codex/config.toml (user)
    - ./.codex/config.toml (project)
```

---

### タスク 03-3: `skill get-all --format codex`

**期待する振る舞い**:
- 入力: `ai-adapter skill get-all --format codex`
- 応答: 登録済みスキルを `.agents/skills/<name>/SKILL.md` にコピー（プロジェクト）
- 入力: `ai-adapter skill get-all --format codex --scope user`
- 応答: `~/.agents/skills/<name>/SKILL.md` にコピー（ユーザー・正本）
  - `~/.agents/skills/` が存在しない場合は作成
- 入力: `ai-adapter skill get-all --format codex --scope user --also-codex-dir`
- 応答: `~/.agents/skills/` + `~/.codex/skills/` の両方にコピー（オプトイン互換）
- 入力: `~/.codex/skills/` に既存スキルがあり `--also-codex-dir` なし
- 応答: `~/.agents/skills/` のみにコピー（`.codex/skills/` は touch しない）

**受け入れ条件**:
- AC1: 正本は `~/.agents/skills/`（仕様準拠）。`~/.codex/skills/` へのコピーは `--also-codex-dir` で明示的にオプトイン
- AC2: 既存スキルは `--force` なしでは確認プロンプト
- AC3: `--env` フィルタが機能

**データ（仕様例）**:
```
$ ai-adapter skill get-all --format codex --scope user
Copied 3 skills to ~/.agents/skills/.
  db-schema, code-review, docs-gen

$ ai-adapter skill get-all --format codex --scope user --also-codex-dir
Copied 3 skills to ~/.agents/skills/ and ~/.codex/skills/ (compat).
  db-schema, code-review, docs-gen
```

---

### タスク 03-4: scan 拡張（.agents/skills + project config.toml）

**期待する振る舞い**:
- 入力: `ai-adapter scan`（`~/.agents/skills/foo/SKILL.md` が存在）
- 応答: `ScanItem(tool="codex", category="skill", name="foo")` を検出
- 入力: `.agents/skills/`（プロジェクト）が存在
- 応答: project スコープの skill として検出
- 入力: `.codex/config.toml`（プロジェクト）が存在
- 応答: settings として検出

**受け入れ条件**:
- AC1: `scan_codex` が `~/.codex/skills` + `~/.agents/skills` の両方を検出
- AC2: `scan_project` が `.codex/config.toml` と `.agents/skills/` を検出
- AC3: 重複検出時は path で区別

---

## 4. 変更対象ファイル

| ファイル | 変更内容 |
|----------|----------|
| `src/ai_adapter/providers/codex.py` | TOML text-splice merge 関数追加 |
| `src/ai_adapter/commands/mcp.py` | `--format codex` + `--scope` 選択肢追加 |
| `src/ai_adapter/commands/skill.py` | `--format codex` + `--also-codex-dir` 選択肢追加 |
| `src/ai_adapter/scan.py` | `.agents/skills` + project `.codex/` 検出追加 |
| `src/ai_adapter/doctor.py` | config.toml の mcp_servers 検証追加 |
| `pyproject.toml` | `tomli` を Python 3.10 向け extras に追加（tomllib フォールバック用） |
| `tests/test_codex.py` | TOML マージ（コメント保持）のテスト追加 |
| `tests/test_mcp.py` | format=codex のテスト |
| `tests/test_skill.py` | format=codex のテスト |
| `tests/test_scan.py` | .agents/skills 検出テスト |

---

## 5. テスト計画

```bash
bash scripts/run_tests.sh tests/test_codex.py
bash scripts/run_tests.sh tests/test_mcp.py -k codex
bash scripts/run_tests.sh tests/test_skill.py -k codex
bash scripts/run_tests.sh tests/test_scan.py -k codex
```

### 主要テストケース

| # | ケース | 期待結果 |
|---|--------|----------|
| T1 | `mcp get --format codex`（既存 config.toml with comments） | コメント・キー順 preserve |
| T2 | `mcp get --format codex`（新規） | `[mcp_servers]` のみ作成 |
| T3 | `.bak` バックアップ | ファイル存在確認 |
| T4 | auth.json が存在 | **読まない**（mock で検証） |
| T5 | `mcp get --format codex --scope user` | `~/.codex/config.toml` |
| T6 | `skill get-all --format codex --scope user` | `~/.agents/skills/` のみ |
| T7 | `skill get-all --format codex --scope user --also-codex-dir` | 両パス |
| T8 | scan（`~/.agents/skills/foo/`） | skill 検出 |
| T9 | scan（project `.codex/config.toml`） | settings 検出 |
| T10 | TOML 書き出し後の再読み込み | 有効な TOML であることを確認 |
| T11 | Python 3.10（tomli フォールバック） | tomllib として動作 |

---

## 6. リスクと対策

| リスク | 対策 |
|--------|------|
| TOML ライブラリのコメント消失 | **text-splice 方式を必須要件化**（tomli-w ラウンドトリップは使用しない） |
| `~/.agents/skills` と `~/.codex/skills` の二重管理 | 正本は `~/.agents/skills/`。`.codex/skills/` は `--also-codex-dir` でオプトイン |
| auth.json 誤アクセス | テストで `open()` の呼び出しをアサート。SCAN_IGNORE_PATTERNS と同等のガード |
| Python 3.10 の tomllib 不在 | `try: import tomllib / except ImportError: import tomli as tomllib` フォールバック |
| フォーマット名の不統一 | `codex-agents` ではなく `codex` に統一（standard/openclaw/cursor と同じプラットフォーム名パターン） |

---

## 7. 完了定義

- [ ] `mcp get --format codex` が config.toml を**コメント保持**で安全にマージ
- [ ] `mcp get --format codex --scope user` が `~/.codex/config.toml` をマージ
- [ ] `skill get-all --format codex` が `.agents/skills/` に配置
- [ ] `--also-codex-dir` で `~/.codex/skills/` への互換コピーが可能
- [ ] scan が `.agents/skills` と project `.codex/config.toml` を検出
- [ ] auth.json への非アクセスがテストで担保
- [ ] Python 3.10（tomli フォールバック）でテストが通過
- [ ] ruff format / ruff lint / lizard CCN ≤ 20 が通過
- [ ] README の Codex セクション更新