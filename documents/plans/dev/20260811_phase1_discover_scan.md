# フェーズ 1 実装計画: Discover（`ai-adapter scan` + 問題診断 + init 導線 + doctor 診断部）

- 日付: 2026-08-11
- 作成者: Product Manager
- 状態: ドラフト（Plan Architect レビュー待ち）
- 上位計画: `documents/plans/dev/20260811_ai_adapter_grand_design.md`（承認済み）
- 対象バージョン: v0.23 → v0.30
- 制約: ドキュメント作成フェーズ（本計画は実装前の設計ドキュメント。実装は別途 Implementer 依頼）

---

## 1. 目的

「環境診断ツール」としての価値を確立し、新規ユーザーの入口を作る。
既存の `get-all-rec` が担う「リポジトリとの同期差分」から一歩進め、**実環境（各ツールの設定ディレクトリ）の検出・可視化・診断**を提供する。

---

## 2. アーキテクチャ方針

### 2.1 新コマンド: `ai-adapter scan`

```
scan
 ├─ Claude Code 検出（1-1a）: ~/.claude/
 ├─ Codex / Cursor 検出（1-1b）: ~/.codex/ ~/.cursor/
 ├─ OpenCode / プロジェクト検出（1-1c）: ~/.config/opencode/ .github/ AGENTS.md CLAUDE.md .mcp.json
 └─ 結果統合表示（1-1d）: 一覧 + 件数サマリー
       └─ 問題診断（1-2）: 重複 / 不一致 / 古い Skill（ValidationIssue 活用）
```

### 2.2 セキュリティ原則（必須）

- scan は**ファイル名・frontmatter（name/description/tags）のみ**を読み取る。内容全文は表示しない
- 認証情報ファイルはブラックリストで除外:
  - `~/.codex/auth.json`
  - `~/.claude/.credentials.json`（存在する場合）
  - `~/.cursor/*auth*` / `*key*` に一致するファイル
  - `.env` / `*.pem` / `*.key` / `*secret*` / `*token*` / `*credential*`
- ブラックリストは `src/ai_adapter/scan.py` に定数 `SCAN_IGNORE_PATTERNS` として一元定義

---

## 3. BDD タスク分解

### タスク 1-1a: `scan` — Claude Code 検出

**期待する振る舞い**:
- 入力: `ai-adapter scan`（`~/.claude/` が存在する環境）
- 応答: 以下を検出して結果セットに追加
  - agents（`~/.claude/agents/*.md` 等）
  - skills（`~/.claude/skills/*/SKILL.md`）
  - settings（`~/.claude/settings.json` の存在）
- 入力: `~/.claude/` が存在しない環境
- 応答: Claude Code の検出結果を「未検出」として表示（エラーにしない）

**受け入れ条件**:
- AC1: 検出対象はファイル名・frontmatter のみ（認証ファイル・内容全文は対象外）
- AC2: 未検出はエラーではなく「not detected」表示
- AC3: 検出結果は `ScanResult` データ構造（後述）に格納

**データ（仕様例）**:
- `~/.claude/skills/database-schema/SKILL.md` → name: database-schema / description: "..."
- `~/.claude/settings.json` → 存在フラグのみ

---

### タスク 1-1b: `scan` — Codex / Cursor 検出

**期待する振る舞い**:
- 入力: `ai-adapter scan`（`~/.codex/` または `~/.cursor/` が存在する環境）
- 応答: 以下を検出
  - Codex: `~/.codex/config.toml` / `~/.codex/skills/` / `~/.codex/agents/`
  - Cursor: `~/.cursor/rules/` / `~/.cursor/mcp.json`
- 入力: `~/.codex/auth.json` が存在する環境
- 応答: 認証ファイルは検出結果に含めない（ブラックリスト除外）

**受け入れ条件**:
- AC1: `~/.codex/auth.json` は絶対に scan 結果に表示しない（テストで担保）
- AC2: Codex / Cursor それぞれ未検出時は「not detected」表示

**データ（仕様例）**:
- `~/.codex/config.toml` → 存在フラグ + 主要キー名のみ（値は表示しない）
- `~/.cursor/rules/frontend.mdc` → name: frontend / description: "..."

---

### タスク 1-1c: `scan` — OpenCode / プロジェクト検出

**期待する振る舞い**:
- 入力: `ai-adapter scan`（カレントディレクトリ or `--project-dir` 指定）
- 応答: 以下を検出
  - `~/.config/opencode/opencode.json`（グローバル）
  - プロジェクトの `.github/`（agents / skills / instructions）
  - プロジェクトルートの `AGENTS.md` / `CLAUDE.md` / `.mcp.json`
- 入力: `ai-adapter scan --project-dir /path/to/project`
- 応答: 指定プロジェクトを対象に検出

**受け入れ条件**:
- AC1: `--project-dir` オプションでプロジェクト指定が可能（デフォルトはカレント）
- AC2: プロジェクト未検出項目は「not detected」表示

**データ（仕様例）**:
- `.github/agents/reviewer.agent.md` → name: reviewer
- `AGENTS.md` → 存在フラグ（先頭 5 行の内容プレビューは frontmatter のみ）

---

### タスク 1-1d: `scan` — 結果統合表示

**期待する振る舞い**:
- 入力: `ai-adapter scan`
- 応答: 1-1a〜c の結果を統合した一覧 + 件数サマリー
  ```
  AI Environment
  Agents
    ✓ Claude Code: 3 detected
    ✓ Codex: 1 detected
    ✓ Cursor: 0 detected (not installed)
  Skills
    17 detected
    ├─ database-schema
    ├─ frontend
    └─ ...
  MCP
    8 configured
  ```
- 入力: `ai-adapter scan --json`
- 応答: マシンリーダブルな JSON 出力

**受け入れ条件**:
- AC1: `--json` オプションで JSON 出力（CI 連携用）
- AC2: カテゴリ別（Agents / Skills / MCP / Instructions）に整理
- AC3: 未検出カテゴリは件数 0 で表示（省略しない）

**データ（仕様例）**:
- JSON 形式: `{"agents": {"claude": 3, "codex": 1}, "skills": {"total": 17, "items": ["database-schema", ...]}, "mcp": {"total": 8}}`

---

### タスク 1-2: `scan` — 問題診断

**期待する振る舞い**:
- 入力: `ai-adapter scan`
- 応答: 検出結果の末尾に `Potential problems` セクションを表示
  - ⚠ 重複 MCP（複数ツールで同一サーバー定義）
  - ⚠ Claude / Codex 間の設定不一致（同一 Skill の内容差分）
  - ⚠ 古い Skill（`update_date` が閾値より古い or バージョン差分）
  - 問題がない場合は「No potential problems detected.」
- 入力: `ai-adapter scan --json`
- 応答: 問題も JSON に含める

**受け入れ条件**:
- AC1: 診断結果は `agent_plugins.py` の `ValidationIssue` モデルを共通利用（severity: error/warning/info）
- AC2: 診断は読み取り専用（自動修正はフェーズ 3 の `doctor --fix` で実施）
- AC3: 各問題に「検出理由」を添えて表示

**データ（仕様例）**:
- 重複 MCP: `.mcp.json` と `~/.config/opencode/opencode.json` の両方に `github` サーバー定義 → warning
- 設定不一致: `~/.claude/skills/frontend/SKILL.md` と `~/.codex/skills/frontend/SKILL.md` の内容が異なる → warning

---

### タスク 1-3: `scan` の検出結果から `init` 導線

**期待する振る舞い**:
- 入力: `ai-adapter scan`（未初期化環境・検出結果あり）
- 応答: 末尾に提案表示「検出された N 件の設定を ~/.ai-adapter/ に取り込みますか? [y/N]」
- 入力: `y`
- 応答: 検出結果を `~/.ai-adapter/` に取り込み、`ai-adapter init` 相当の初期化を実行
- 入力: `N` / 未初期化でない環境
- 応答: 提案を表示しない

**受け入れ条件**:
- AC1: 提案は対話モードでのみ表示（`--json` 時は非表示）
- AC2: 取り込みは既存の `add_all_rec` / 登録ロジックを再利用
- AC3: 取り込み前に対象一覧を提示し、確認を取る

---

### タスク 1-4: `doctor` — 診断部分（読み取り専用）

**期待する振る舞い**:
- 入力: `ai-adapter doctor`
- 応答: ヘルスサマリー表示
  - ✓ 23 skills / ✓ 8 MCP servers / ✓ 4 agents
  - Updates available（更新可能な Skill/Plugin の一覧）
  - Compatibility issues（非互換の検出）
- 入力: `ai-adapter doctor --json`
- 応答: ヘルス状態の JSON 出力

**受け入れ条件**:
- AC1: 本タスクは診断表示のみ（`--fix` はフェーズ 3 の 3-2 で実装）
- AC2: 既存の `opencode validate` / `plugin validate` と `ValidationIssue` を統合して利用（重複実装なし）
- AC3: 更新検出はローカル登録情報と参照元（GitHub 等）の比較（フェーズ 3 の 3-5 バージョン追跡の前段）

**データ（仕様例）**:
- `ai-adapter doctor` → `✓ Skills: 23 (2 updates available)` / `⚠ playwright MCP incompatible`

---

## 4. データ構造設計

### `ScanResult`（`src/ai_adapter/scan.py` に定義）

```python
@dataclass
class ScanItem:
    tool: str  # "claude" | "codex" | "cursor" | "opencode" | "project"
    category: str  # "agent" | "skill" | "mcp" | "instruction"
    name: str
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    path: Path | None = None


@dataclass
class ScanResult:
    items: list[ScanItem]
    problems: list[ValidationIssue]  # agent_plugins.ValidationIssue を再利用
```

### `ScanIssue` は新設しない

- 診断問題は `agent_plugins.py` の `ValidationIssue`（severity: error/warning）を共通利用
- これによりフェーズ 3 の `doctor --fix` が同じモデルで対応可能

---

## 5. テスト計画（フェーズ 1）

| タスク | テストファイル | 種別 | 追加数 | 内容 |
|--------|--------------|------|--------|------|
| 1-1a〜d | `tests/test_scan.py`（新設） | Unit | 15 | 各ツール検出（tmp_path 使用・実ディレクトリ作成） |
| 1-1b | `tests/test_scan.py` | Unit | 5 | **認証ファイル除外テスト**（`~/.codex/auth.json` 非表示） |
| 1-1d | `tests/test_scan.py` | Unit | 5 | 統合表示・`--json` 出力 |
| 1-2 | `tests/test_scan.py` | Unit | 10 | 問題診断ロジック（重複 MCP / 不一致 / 古い Skill） |
| 1-3 | `tests/test_scan.py` | Unit/Integration | 5 | init 導線（y/N 分岐・取り込み） |
| 1-4 | `tests/test_doctor.py`（新設） | Unit | 10 | ヘルスサマリー・`--json`・ValidationIssue 統合 |

**セキュリティテスト（必須）**:
- `~/.codex/auth.json` が scan 結果に含まれないこと
- `.env` / `*.key` 等のブラックリスト対象が含まれないこと
- frontmatter 以外の内容全文が表示されないこと

**テストの HOME 隔離（必須・Plan Architect 指摘反映）**:
- scan は `Path.home()` 配下（`~/.claude/` `~/.codex/` 等）を読むため、`tests/conftest.py` の cwd 隔離だけでは不十分
- テストでは `monkeypatch.setenv("HOME", tmp_path)` パターンで HOME を隔離する（既存テストの環境変数パッチ方式を踏襲し、`tests/test_scan.py` で共通フィクスチャ `isolated_home` を定義）

**実行ゲート**: `scripts/run_tests.sh` で全テスト実行（sandbox 方式・`.github` 保護）。

---

## 6. 既存コード再利用マップ（フェーズ 1）

| タスク | 再利用資産 | 用途 |
|--------|-----------|------|
| 1-1a〜c | `agent_format.py` の `parse_frontmatter`（L21） | 検出ファイルの frontmatter 解析 |
| 1-1a | `skill.py` の `_parse_skill_metadata`（L29） | `SKILL.md` の name/description/tags 抽出 |
| 1-1c | `config.py` の `get_config_path`（L~） | `~/.ai-adapter/` の解決 |
| 1-2 | `agent_plugins.py` の `ValidationIssue`（L51）/ severity | 診断結果の共通モデル |
| 1-3 | `add_all_rec.py` の登録ロジック | 検出結果の取り込み |
| 1-4 | `opencode.py` の `opencode_validate`・`plugin.py` の `plugin validate` | doctor 診断の統合 |

> **注記（Plan Architect 指摘反映）**: フェーズ 0 のグランドデザイン再利用マップに記載していた「`get_all_rec.py` の検出ロジック」「`opencode.py` の `~/.config/opencode/` パス解決」は**実在しない**（誤認）。実際に流用可能なのは上記の `parse_frontmatter` / `_parse_skill_metadata` であり、scan の検出ロジックは新規実装が必要。グランドデザイン第 8 章の再利用マップも併せて修正する。

## 6.1 ValidationIssue の severity 拡張（info 追加）

- `agent_plugins.py` の `ValidationIssue` は現状 `severity: "error" | "warning"` のみ
- フェーズ 1 で `info` を追加（`ValidationResult` に info カテゴリを追加、出力ラベルは `INFO`）
- **Phase 3 の doctor / optimize はこの拡張済みモデルを参照する**（フェーズ 3 では info 追加をしない）

---

## 7. リスクと対策

| リスク | 影響 | 対策 |
|--------|------|------|
| 認証情報の漏洩 | 重大なセキュリティ事故 | ブラックリスト定数 + 必須セキュリティテスト |
| 各ツールの設定ディレクトリ仕様変更 | 検出ロジックの陳腐化 | `scan.py` に検出ロジック集中・パスは定数化 |
| スキャン範囲の過大化 | パフォーマンス低下 | 深さ制限（デフォルト 2 レベル）・`--max-depth` オプション |
| 誤検出（本当は設定でないファイルを検出） | ユーザー混乱 | 検出は frontmatter 必須（SKILL.md は name/description 必須） |

---

## 8. 実装順序

1. 1-1a → 1-1b → 1-1c（検出ロジックをツール単位に積み上げ）
2. 1-1d（統合表示）
3. 1-2（問題診断）
4. 1-4（doctor 診断部・ValidationIssue 統合）
5. 1-3（init 導線・最後に対話フロー追加）

---

## 9. 次のアクション

1. [ ] Plan Architect レビュー（本計画の妥当性検証）
2. [ ] 承認後、Implementer に実装依頼
3. [ ] Reviewer 検収 → QA チェック
