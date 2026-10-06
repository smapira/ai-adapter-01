# 設計書 02: Claude Code ネイティブパス対応

- 日付: 2026-10-06
- 作成者: Product Manager
- 状態: ドラフト
- 上位計画: [platform_parity_master_design](./20261006_platform_parity_master_design.md)
- 優先度: P0
- 想定規模: 中（provider 拡張 + format 追加）
- 依存: 設計書 01（User スコープ指示ファイル）

---

## 1. 目的

Claude Code の**プロジェクトネイティブパス**（`.claude/` 配下）を ai-adapter から管理できるようにする。

### 対象ギャップ

| 行 | パス | スコープ | 現状 |
|----|------|----------|------|
| 22 | `.claude/agents/<name>.md` | Project | ❌ |
| 23 | `~/.claude/agents/<name>.md` | User | ⚠️ scan のみ |
| 24 | `.claude/settings.json` | Project | ❌ |
| 25 | `.claude/settings.local.json` | Project-local | ❌ |
| 26 | `~/.claude/settings.json` | User | ⚠️ scan + JSON 検査のみ |
| 30 | `.claude/rules/*.md` | Project | ❌ |
| 31 | `.claude/skills/<name>/SKILL.md` | Project | ❌ |
| 32 | `~/.claude/skills/<name>/SKILL.md` | User | ⚠️ scan のみ |

**現状**: Claude Code は `.github/` 共有（Copilot 互換）経由でカバー。`.claude/` ネイティブは未管理。

---

## 2. アプローチ

### 2.1 デプロイ先の二層化

既存 `.github/` デプロイは維持しつつ、`--format claude` で `.claude/` へデプロイできるようにする。

```
skill get --format standard   → .github/skills/        （現状維持）
skill get --format claude     → .claude/skills/        （新規）

agent get --format standard   → .github/agents/        （現状維持）
agent get --format claude     → .claude/agents/        （新規）
```

### 2.2 新規 provider: `src/ai_adapter/providers/claude.py`

cursor/openclaw と同じパターンで Claude Code 固有ロジックを分離する。

```python
"""Claude Code provider integration.

Handles deployment to Claude Code native paths (.claude/).
"""

def resolve_agents_path(scope: str, project_dir: Path | None = None) -> Path:
    """scope: 'project' → .claude/agents/, 'user' → ~/.claude/agents/"""

def resolve_skills_path(scope: str, project_dir: Path | None = None) -> Path:
    """scope: 'project' → .claude/skills/, 'user' → ~/.claude/skills/"""

def deploy_agents(agents, src_dir, scope, project_dir, force) -> None:
    """Copy agent files to .claude/agents/."""

def deploy_skills(skills, src_dir, scope, project_dir, force) -> None:
    """Copy skill directories to .claude/skills/."""

def export_mcp_user(servers: list[MCPServer]) -> dict:
    """Export MCP servers for ~/.claude.json (user scope).

    Claude Code user MCP is defined in ~/.claude.json's mcpServers key.
    Project scope uses .mcp.json (existing `mcp get --format standard`).
    """

def merge_into_claude_json(path: Path, data: dict, force: bool = False) -> None:
    """Merge MCP servers into ~/.claude.json preserving other keys."""
    # .bak バックアップ必須。mcpServers キーのみ操作。
```

**`--scope` の再利用**: scope 解決は設計書 01 の `config.resolve_scope_path()` を使用する
（本設計書で独自実装しない）。

### 2.3 settings.json / settings.local.json の管理方針

**設定ファイルは「生成」しない**（ユーザーの権限・hooks は破壊リスクが高い）。
代わりに以下の 2 段階で対応する。

**方針**: Claude Code の MCP 設定は **`.mcp.json`（プロジェクト）** と **`~/.claude.json`（ユーザー）** が正となる。

**重要（Plan Architect 指摘 C1 反映）**: 初稿では `.claude/settings.json` へのマージを提案したが、
現行 Claude Code の実態では `settings.json` は permissions/hooks 等が主体で、
MCP サーバー定義は `.mcp.json`（`mcpServers` キー）が正である。
さらにプロジェクト用 `.mcp.json` は **既存の `mcp get --format standard` が既に書き出している**ため、
`--format claude` を新設しても Claude が読まないファイルへの書き込み＋既存機能の重複になる。

**是正後の方針**:

| スコープ | デプロイ先 | 操作 |
|----------|-----------|------|
| Project | `<project>/.mcp.json` | 既存 `mcp get --format standard` で**充足**（新機能不要） |
| User | `~/.claude.json` | `mcp get --format claude --scope user` で新規マージ |

**`~/.claude.json` の注意点**:
- このファイルは Claude Code 自体のユーザーデータ（プロジェクト履歴等）も含む
- **merge は `mcpServers` キーのみ操作**し、他キーは読み取り専用
- `.bak` バックアップ必須
- 未整備（`~/.claude.json` が存在しない）場合は新規作成（`{"mcpServers": {}}`）

**Phase B（将来）**: doctor による `~/.claude.json` の mcpServers 検証強化。

**`settings.local.json`** は個人用のため ai-adapter は管理しない（scan 検出のみ追加）。

### 2.4 rules ディレクトリ

Claude Code の `.claude/rules/*.md` はトピック/パススコープのルール。
ai-adapter では **Skill と同様のディレクトリ構造**で管理する。

```bash
# rules は Skill ストアからデプロイ（スキルと同一モデル）
ai-adapter skill get --format claude-rules
# → .claude/rules/<name>.md に展開
```

**ただし優先度は低く**、本設計書では Phase A に含まれない。
**スコープ外**: rules の完全管理は将来イテレーション。

---

## 3. BDD タスク分解

### タスク 02-1: `skill get --format claude`

**期待する振る舞い**:
- 入力: `ai-adapter skill get <name> --format claude`
- 応答: `.claude/skills/<name>/` にスキルディレクトリをコピー
- 入力: `ai-adapter skill get-all --format claude`
- 応答: 登録済みスキルを全て `.claude/skills/` へコピー
- 入力: 既存 `.claude/skills/<name>/` があり `--force` なし
- 応答: 確認プロンプト表示

**受け入れ条件**:
- AC1: `.github/skills/`（standard）へのデプロイは引き続き動作
- AC2: 既存ファイルは `.bak` バックアップまたは確認プロンプトで保護
- AC3: スキルの frontmatter（name/description/tags）は保持される
- AC4: `--env` フィルタが `--format claude` でも機能

**データ（仕様例）**:
```
# store: ~/.ai-adapter/skills/db-schema/SKILL.md
$ ai-adapter skill get db-schema --format claude
Skill 'db-schema' copied to .claude/skills/db-schema/.

$ ls .claude/skills/db-schema/
SKILL.md
```

---

### タスク 02-2: `sub-agent get --format claude`

**期待する振る舞い**:
- 入力: `ai-adapter sub-agent get <name> --format claude`
- 応答: `.claude/agents/<name>.md` にエージェントファイルをコピー
  - `.agent.md` 拡張子は `.md` に正規化（Claude Code は `.md` を読む）
- 入力: `ai-adapter sub-agent get-all --format claude`
- 応答: 登録済みエージェントを `.claude/agents/` へコピー

**受け入れ条件**:
- AC1: `.agent.md` → `.md` のリネームが行われる（frontmatter は保持）
- AC2: tools フィールドの array→object 変換は `agent_format.convert_agent_file` を再利用
- AC3: `~/.claude/agents/` への User デプロイは `--scope user` で可能（設計書 01 と統合）

**データ（仕様例）**:
```
# store: ~/.ai-adapter/agents/reviewer.agent.md
$ ai-adapter sub-agent get reviewer --format claude
Agent 'reviewer' copied to .claude/agents/reviewer.md.

$ head -5 .claude/agents/reviewer.md
---
name: reviewer
description: Code review specialist
tools:
  read: true
  grep: true
---
# Reviewer instructions...
```

---

### タスク 02-3: `mcp get --format claude --scope user`（~/.claude.json マージ）

**期待する振る舞い**:
- 入力: `ai-adapter mcp get --format claude --scope user`
- 応答: `~/.claude.json` の `mcpServers` をマージ更新
  - 既存の非管理サーバーは preserve
  - 管理対象は上書き
- 入力: `~/.claude.json` が存在しない
- 応答: 新規作成（最小構造 `{"mcpServers": {}}` から開始）
- 入力: `ai-adapter mcp get --format claude --scope project`
- 応答: `.mcp.json` にマージ（**既存 `mcp get --format standard` と同じ出力**。新機能ではなく整合のため明示）

**受け入れ条件**:
- AC1: merge は `.bak` バックアップを取る（cursor/openclaw パターン）
- AC2: 管理対象外のキー（プロジェクト履歴等）は**絶対に変更しない**
- AC3: env 値は `${ENV_KEY}` 形式に変換（既存 export パターン）
- AC4: `--force` で確認プロンプト省略
- AC5: `--scope project` は `.mcp.json`（Claude Code のプロジェクト MCP 設定場所）

**データ（仕様例）**:
```
# 既存 ~/.claude.json
{
  "projects": {"/path/to/repo": {"allowedTools": [...]}},
  "mcpServers": {
    "existing-server": {"command": "node", "args": ["server.js"]}
  }
}

# ai-adapter mcp get --format claude --scope user 後
{
  "projects": {"/path/to/repo": {"allowedTools": [...]}},
  "mcpServers": {
    "existing-server": {"command": "node", "args": ["server.js"]},
    "managed-server": {"command": "npx", "args": ["-y", "mcp-x"], "env": {"API_KEY": "${API_KEY}"}}
  }
}
```

---

### タスク 02-4: scan 拡張（project .claude/）

**期待する振る舞い**:
- 入力: `ai-adapter scan`（プロジェクトに `.claude/agents/reviewer.md` が存在）
- 応答: `ScanItem(tool="claude", category="agent", name="reviewer")` を検出
- 入力: `.claude/skills/*/SKILL.md` が存在
- 応答: skill カテゴリで検出
- 入力: `.claude/rules/` が存在
- 応答: 現状どおり**検出しない**（Phase B で対応）

**受け入れ条件**:
- AC1: `scan_claude` は User スコープ（現状）に加え project `.claude/` を検出
- AC2: project 検出結果の tool 名は `"claude"`（**マスター設計 2.6 のタクソノミー方針に準拠**）
- AC3: `scan_project` の `.github/` 検出（tool=`"project"`）とはパスが異なるため重複しない
- AC4: `SCAN_IGNORE_PATTERNS` / `is_ignored()` を適用

**データ（仕様例）**:
```
$ ai-adapter scan
Claude Code:
  agents: 2 (project .claude/agents/ + user ~/.claude/agents/)
  skills: 1 (project .claude/skills/)
```

---

## 4. 変更対象ファイル

| ファイル | 変更内容 |
|----------|----------|
| `src/ai_adapter/providers/claude.py` | **新規** provider |
| `src/ai_adapter/commands/skill.py` | `skill get-all` に `--format claude` 選択肢追加（**`skill get` 単数には `--format` が無いため新規導入ではなく get-all への追加**） |
| `src/ai_adapter/commands/agent.py` | `sub-agent get/get-all` に `--format claude` 選択肢追加 |
| `src/ai_adapter/commands/mcp.py` | `--format claude` 選択肢追加 + `--scope`（設計書 01 のヘルパー再利用） |
| `src/ai_adapter/scan.py` | `scan_claude` の project 検出追加（tool=`"claude"`） |
| `src/ai_adapter/doctor.py` | `~/.claude.json` の mcpServers 検証追加 |
| `src/ai_adapter/cli.py` | `claude_group` 登録（**Phase A では空グループ。将来の claude install 用。実装は後続**） |
| `tests/test_claude.py` | **新規** provider テスト |
| `tests/test_skill.py` | get-all format=claude のテスト追加 |
| `tests/test_agent.py` | sub-agent format=claude のテスト追加 |
| `tests/test_mcp.py` | format=claude のテスト追加 |
| `tests/test_scan.py` | project .claude/ 検出テスト |

---

## 5. テスト計画

```bash
bash scripts/run_tests.sh tests/test_claude.py
bash scripts/run_tests.sh tests/test_skill.py -k claude
bash scripts/run_tests.sh tests/test_agent.py -k claude
bash scripts/run_tests.sh tests/test_mcp.py -k claude
bash scripts/run_tests.sh tests/test_scan.py -k claude
```

### 主要テストケース

| # | ケース | 期待結果 |
|---|--------|----------|
| T1 | `skill get-all --format claude` | `.claude/skills/` に配置 |
| T2 | `skill get-all --format standard`（回帰） | `.github/skills/` に配置 |
| T3 | `sub-agent get --format claude` | `.agent.md` → `.md` リネーム |
| T4 | `mcp get --format claude --scope user`（新規 ~/.claude.json） | 最小 JSON から作成 |
| T5 | `mcp get --format claude --scope user`（既存 ~/.claude.json） | projects キー保持 + mcpServers マージ |
| T6 | `mcp get --format claude --scope project` | `.mcp.json`（standard と同じ） |
| T7 | `.bak` バックアップ | ファイル存在確認 |
| T8 | scan（project .claude/agents/） | 検出（tool="claude"） |
| T9 | scan（project .claude/skills/） | 検出 |
| T10 | 既存非管理 MCP サーバー | preserve される |
| T11 | `--force` なしで既存 ~/.claude.json | 確認プロンプト |

---

## 6. リスクと対策

| リスク | 対策 |
|--------|------|
| `~/.claude.json` の非管理データ破壊 | merge は mcpServers キーのみ操作。他キーは読み取り専用 |
| `.github/` と `.claude/` の二重管理混乱 | README で「Copilot 互換 vs Claude ネイティブ」を明記 |
| format 選択肢の増加による UX 低下 | `--format` のヘルプに各フォーマットの出力先を明記 |
| scan の tool 名混乱 | マスター設計 2.6 のタクソノミー方針に準拠（`.claude/` → `"claude"`） |
| `--scope` の独自実装 | 設計書 01 の `resolve_scope_path()` を再利用（本設計書では実装しない） |

---

## 7. 完了定義

- [ ] `skill get-all / sub-agent get --format claude` が動作
- [ ] `mcp get --format claude --scope user` が `~/.claude.json` を安全にマージ
- [ ] scan が project `.claude/agents/` `.claude/skills/` を検出（tool=`"claude"`）
- [ ] 既存 standard フォーマットのテストが全て通過
- [ ] ruff format / ruff lint / lizard CCN ≤ 20 が通過
- [ ] README の Claude Code セクション更新
