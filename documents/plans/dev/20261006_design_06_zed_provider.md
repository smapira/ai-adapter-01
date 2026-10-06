# 設計書 06: Zed 新規 provider

- 日付: 2026-10-06
- 作成者: Product Manager
- 状態: ドラフト
- 上位計画: [platform_parity_master_design](./20261006_platform_parity_master_design.md)
- 優先度: P2
- 想定規模: 中（新規 provider + scan）
- 依存: 設計書 01（User スコープ AGENTS.md）
- 外部仕様: context7 `/websites/zed_dev`

---

## 1. 目的

Zed エディタへの対応を提供する。現在は **provider なし・scan なし**。

### 対象ギャップ（全行）

| 行 | パス | カテゴリ |
|----|------|----------|
| 64 | MCP（`context_servers` キー） | MCP（**known gap**: Phase B で merge 対応。Zed の MCP キーは `context_servers`（mcpServers ではない）） |
| 65 | `.zed/settings.json` | Core Config (Project) |
| 66 | `~/.config/zed/settings.json`（macOS: `~/Library/Application Support/Zed/settings.json`） | Core Config (User) |
| 67 | `.rules` / `.cursorrules` / `.windsurfrules` / `.clinerules` / `AGENT.md` / `CLAUDE.md` / `GEMINI.md` | Instructions (Compatibility) |
| 68 | `AGENTS.md` | Instructions (Project) |
| 69 | `~/.config/zed/AGENTS.md` | Instructions (User) |
| 70 | `~/.config/zed/keymap.json` | Keymap (User) |
| 71 | `SKILL.md`（Skill directory） | Skill (User/Project) |
| 72 | `.zed/tasks.json` | Task (Project) |

---

## 2. 外部仕様サマリー（context7 で確認済み）

| 項目 | 仕様 |
|------|------|
| Instructions | `AGENTS.md` が primary。プロジェクトルート + ユーザー |
| Settings | `.zed/settings.json`（プロジェクト）/ ユーザー設定（OS 依存） |
| User パス | Linux: `~/.config/zed/settings.json` / macOS: `~/Library/Application Support/Zed/settings.json` |
| Agent 設定 | `agent.*` キー（profiles, sandbox_permissions, commit_message 等） |
| Skills | Agent Skills（SKILL.md 形式） |
| Tasks | `.zed/tasks.json` |
| Keymap | ユーザー keymap.json |

---

## 3. アプローチ

### 3.1 新規 provider: `src/ai_adapter/providers/zed.py`

```python
"""Zed editor provider integration.

Handles:
- Instructions deployment (AGENTS.md)
- Settings merge (agent section)
- Skills deployment
- Tasks deployment
- Keymap (read-only / future)
"""

def get_user_config_dir() -> Path:
    """Return Zed user config directory based on OS.

    重要（Plan Architect 指摘 M6-3）: OS 依存パス解決は **config.py に一元定義**する
    （`config.get_zed_user_dir()` 等）。provider / 設計書 01 / doctor が参照する構成。
    
    macOS: ~/Library/Application Support/Zed/
    Linux: ~/.config/zed/
    Windows: %APPDATA%\Zed\
    """

    from ai_adapter import config as _config
    return _config.get_zed_user_dir()
    
    macOS: ~/Library/Application Support/Zed/
    Linux: ~/.config/zed/
    Windows: %APPDATA%\\Zed\\
    """

def resolve_settings_path(scope: str) -> Path:
    """scope: 'project' → .zed/settings.json, 'user' → get_user_config_dir()/settings.json"""

def resolve_instructions_path(scope: str, filename: str = "AGENTS.md") -> Path:
    """scope: 'project' → ./AGENTS.md, 'user' → get_user_config_dir()/AGENTS.md"""

def resolve_skills_path(scope: str) -> Path:
    """scope: 'project' → <project>/.agents/skills/, 'user' → ~/.agents/skills/

    重要（Plan Architect 指摘 C6-1 反映）: Zed のスキル探索パスは `.zed/skills/` ではなく
    `~/.agents/skills/`（global）/ `<worktree>/.agents/skills/`（project）である。
    またネスト非対応（各スキルはルート直下の直接の子のみ）。
    """

    base = Path.cwd() if scope == "project" else Path.home()
    if scope == "project":
        return base / ".agents" / "skills"
    return base / ".agents" / "skills"

def merge_into_settings(path: Path, data: dict, force: bool = False) -> None:
    """Merge agent configuration into zed settings.json."""

def deploy_skills(skills, src_dir, scope, force=False) -> None:
    """Deploy skills to Zed skill directory."""

@zed_group.command(...)
def zed_install(): ...

@zed_group.command(...)
def zed_validate(): ...
```

### 3.2 CLI サブコマンド

```bash
# Zed グループ
ai-adapter zed install
  # - AGENTS.md（プロジェクトルート、instructions から生成）
  # - .agents/skills/（登録済みスキル。Zed の実際の探索パス）
  # 注意: settings.json は Phase A では **validate のみ**（生成しない。Phase B で merge 対応）

ai-adapter zed install --scope user
  # ~/.config/zed/ 配下に配置

ai-adapter zed validate
  # .zed/settings.json, AGENTS.md を検証

ai-adapter zed uninstall
```

### 3.3 既存コマンドへの format 追加

```bash
# instructions
ai-adapter agent get <name> --format zed
# → AGENTS.md としてプロジェクトルートに配置

# skills
ai-adapter skill get-all --format zed
# → .zed/skills/ に配置

# Zed は MCP を settings.json で管理するが、
# 本設計書では settings.json の生成・マージは**最小限**に留める
```

### 3.4 settings.json の管理方針

Zed の settings.json はユーザーのエディタ設定を含む（テーマ、フォント、LSP 等）。

**方針**: **generate しない**。代わりに:

1. **Phase A（本設計書）**: doctor で settings.json の妥当性を検証（JSON パース）
2. **Phase B（将来）**: `zed install` で `agent.profiles` セクションのみマージ

Phase A では:
```bash
ai-adapter zed validate
# → .zed/settings.json の JSON パース確認
# → AGENTS.md の存在確認
```

### 3.5 tasks.json

Zed の `.zed/tasks.json` はプロジェクトタスク定義。
ai-adapter の `bin`（スクリプト管理）とマッピングする。

**方針**: 本設計書では **スコープ外**（将来イテレーション）。
`bin` を tasks.json に変換するロジックは複雑なため段階的に対応。

### 3.6 keymap.json

User スコープの keymap は ai-adapter の管理対象外（個人設定のため）。
**scan で検出のみ**（将来の拡張用）。

---

## 4. BDD タスク分解

### タスク 06-1: `zed install`（プロジェクトスコープ）

**期待する振る舞い**:
- 入力: `ai-adapter zed install`（instructions + skills が登録済み）
- 応答: 以下を配置
  - `AGENTS.md`（プロジェクトルート）
  - `.agents/skills/<name>/SKILL.md` × N（**Zed の実際の探索パス**。ネスト非対応のためルート直下のみ）
- 入力: store が空
- 応答: 「Nothing to install.」（エラーにしない）

**受け入れ条件**:
- AC1: AGENTS.md は instruction の内容を連結
- AC2: `.zed/skills/` が存在しない場合は作成
- AC3: 既存 `AGENTS.md` がある場合は確認プロンプト（`--force` で省略）

**データ（仕様例）**:
```
# store: instructions = [AGENTS.md], skills = [db-schema, code-review]
$ ai-adapter zed install
Zed configuration installed:
  AGENTS.md
  .agents/skills/db-schema/SKILL.md
  .agents/skills/code-review/SKILL.md
```

---

### タスク 06-2: `zed install --scope user`

**期待する振る舞い**:
- 入力: `ai-adapter zed install --scope user`
- 応答: `get_user_config_dir()` 配下に配置
  - macOS: `~/Library/Application Support/Zed/AGENTS.md`
  - Linux: `~/.config/zed/AGENTS.md`

**受け入れ条件**:
- AC1: OS 依存パスを正しく解決
- AC2: ディレクトリが存在しない場合は作成

---

### タスク 06-3: `skill get-all --format zed`

**期待する振る舞い**:
- 入力: `ai-adapter skill get-all --format zed`
- 応答: `.agents/skills/<name>/SKILL.md` にコピー（**Zed の実際の探索パス**）
- 入力: `--scope user`
- 応答: `~/.agents/skills/` にコピー（**Zed の global 探索パス**）
- 注意: Zed はネスト非対応（各スキルはルート直下の直接の子のみ）

**受け入れ条件**:
- AC1: frontmatter は保持
- AC2: 既存スキルは確認プロンプト

---

### タスク 06-4: `zed validate`

**期待する振る舞い**:
- 入力: `ai-adapter zed validate`
- 応答: 以下を検証
  - `AGENTS.md` の存在
  - `.zed/settings.json` の JSON パース（存在時）
  - `.zed/skills/*/SKILL.md` の frontmatter 検証
- 入力: エラーなし
- 応答: 「Zed configuration is valid.」

**受け入れ条件**:
- AC1: `opencode validate` を参考にした UX（`--json` は新設）
- AC2: `--json` オプションで構造化出力（**新設**: opencode validate には `--json` は存在しない）

---

### タスク 06-5: scan 拡張（zed）

**期待する振る舞い**:
- 入力: `ai-adapter scan`（`.zed/settings.json` + `AGENTS.md` が存在）
- 応答: Zed の settings と instruction を検出
- 入力: `~/.config/zed/settings.json` が存在
- 応答: User スコープの settings として検出

**受け入れ条件**:
- AC1: `scan_zed` が User + Project 両方を検出
- AC2: `TOOL_ORDER` に "zed" のみ append（マスター設計 2.7 準拠。タプル全体の再定義を禁止）
- AC3: `TOOL_LABELS["zed"]` へのラベル追加、`scan_all` への `items.extend(scan_zed(...))` 登録
- AC4: `SCAN_IGNORE_PATTERNS` への追加を検討（Zed は credential ファイルが少ないため影響小）
- AC5: keymap.json も検出（category: settings）

---

## 5. 変更対象ファイル

| ファイル | 変更内容 |
|----------|----------|
| `src/ai_adapter/providers/zed.py` | **新規** provider |
| `src/ai_adapter/commands/skill.py` | `--format zed` + `--scope user` 選択肢追加（**skill 側の `--scope` は本設計書で新規定義**。設計書 01 は instruction のみ） |
| `src/ai_adapter/commands/instruction.py` | `--format zed` 選択肢 |
| `src/ai_adapter/scan.py` | `scan_zed` + TOOL_ORDER |
| `src/ai_adapter/commands/doctor.py` | zed 設定の診断追加 |
| `src/ai_adapter/cli.py` | `zed_group` 登録 |
| `tests/test_zed.py` | **新規** |
| `tests/test_skill.py` | format=zed |
| `tests/test_scan.py` | zed 検出 |

---

## 6. テスト計画

```bash
bash scripts/run_tests.sh tests/test_zed.py
bash scripts/run_tests.sh tests/test_skill.py -k zed
bash scripts/run_tests.sh tests/test_scan.py -k zed
```

### 主要テストケース

| # | ケース | 期待結果 |
|---|--------|----------|
| T1 | `zed install`（プロジェクト） | AGENTS.md + .agents/skills/ 配置 |
| T2 | `zed install --scope user`（macOS） | Application Support 配下 |
| T3 | `zed install --scope user`（Linux） | ~/.config/zed/ 配下 |
| T4 | `skill get-all --format zed` | .agents/skills/ 配置（Zed 実際の探索パス） |
| T4b | `.agents/skills/` にネストしたスキル | **Zed に認識されない**（ネスト非対応の制約を AC に明記） |
| T5 | `zed validate`（正常） | valid 判定 |
| T6 | `zed validate`（settings.json 破損） | エラー表示 |
| T7 | scan（.zed/ 存在） | 検出 |
| T8 | scan（~/.config/zed/settings.json） | User settings 検出 |
| T9 | OS 依存パス解決 | macOS/Linux で異なるパス |

---

## 7. リスクと対策

| リスク | 対策 |
|--------|------|
| Zed の仕様変更 | context7 の最新ドキュメントを参照 |
| settings.json の非管理キー破壊 | 本設計書では generate しない。validate のみ |
| OS 依存パスの誤判定 | プラットフォーム別テストで担保 |
| tasks.json / keymap.json の複雑さ | スコープ外として明確化。将来イテレーション |

---

## 8. 完了定義

- [ ] `zed install` が project/user 両方で動作
- [ ] `skill get-all --format zed` が動作
- [ ] `zed validate` が設定を検証
- [ ] scan が Zed 設定を検出
- [ ] macOS/Linux のパス差異がテストで担保
- [ ] README の Supported Tools に Zed を追加
