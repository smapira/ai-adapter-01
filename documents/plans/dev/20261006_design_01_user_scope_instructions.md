# 設計書 01: User スコープ指示ファイル対応

- 日付: 2026-10-06
- 作成者: Product Manager
- 状態: ドラフト
- 上位計画: [platform_parity_master_design](./20261006_platform_parity_master_design.md)
- 優先度: P0
- 想定規模: 小（1 コマンド拡張 + テスト）

---

## 1. 目的

User スコープの指示ファイル（プラットフォーム固有ディレクトリ配下の AGENTS.md / CLAUDE.md / GEMINI.md 等）を
`agent`（instruction）コマンドからデプロイ・取得できるようにする。

### 対象ギャップ

| プラットフォーム | パス | 仕様上の category |
|-----------------|------|------------------|
| OpenAI Codex | `~/.codex/AGENTS.md` | Instructions (User) |
| Claude Code | `~/.claude/CLAUDE.md` | Instructions (User) |
| OpenCode | `~/.config/opencode/AGENTS.md` | Instructions (User) |
| Gemini CLI | `~/.gemini/GEMINI.md` | Instructions / Context (User) |
| Zed | `~/.config/zed/AGENTS.md` | Instructions (User) |

**現状**: instruction デプロイはプロジェクトルートのみ。User スコープは未対応。

---

## 2. アプローチ

### 2.1 CLI 拡張: `--format` + `--scope` オプション

既存 `agent`（= instruction）コマンドに `--format` のプラットフォーム選択肢と
`--scope` を追加する。**`--tool` は新設しない**（`--format` に一本化し、
既存の `--format standard|cursor` と役割を統合）。

```bash
# 現状（プロジェクトルート、変更なし）
ai-adapter agent get AGENTS.md
ai-adapter agent get-all

# 新規: プラットフォーム指定 + User スコープ
ai-adapter agent get AGENTS.md --format codex --scope user
ai-adapter agent get CLAUDE.md --format claude --scope user
ai-adapter agent get GEMINI.md --format gemini --scope user
ai-adapter agent get-all --format opencode --scope user
ai-adapter agent get-all --format zed --scope user

# インポート（User スコープ → ストア）
ai-adapter agent add ~/.codex/AGENTS.md
ai-adapter scan  # 既存: User スコープファイルを検出可能にする
```

**`--format` 選択肢の定義**（既存 `standard|cursor` に追加）:

| format | デプロイ先（--scope project） | デプロイ先（--scope user） | ファイル名マッピング |
|--------|------------------------------|---------------------------|---------------------|
| `standard`（デフォルト） | プロジェクトルート | —（非対応） | 元のファイル名を保持 |
| `codex` | プロジェクトルート（AGENTS.md） | `~/.codex/` | `AGENTS.md` / 任意名 |
| `claude` | プロジェクトルート（CLAUDE.md） | `~/.claude/` | `CLAUDE.md` / 任意名 |
| `opencode` | プロジェクトルート（AGENTS.md） | `~/.config/opencode/` | `AGENTS.md` / 任意名 |
| `gemini` | プロジェクトルート（GEMINI.md） | `~/.gemini/` | `GEMINI.md` / 任意名 |
| `zed` | プロジェクトルート（AGENTS.md） | OS 依存 Zed ディレクトリ | `AGENTS.md` / 任意名 |
| `cursor` | —（非対応、Exit(2) 維持） | —（非対応） | — |

**get-all のファイル名マッピング方針**:
- `--scope user` の get-all は、**ツールが読むファイル名**にマッピングしてコピーする
  - claude: `CLAUDE.md`（`AGENTS.md` 等は `CLAUDE.md` にリネーム）
  - codex / opencode / zed: `AGENTS.md`（`CLAUDE.md` 等は `AGENTS.md` にリネーム）
  - gemini: `GEMINI.md`（他は `GEMINI.md` にリネーム）
- マッピング後の同名衝突時は「残りを任意名で配置」し、ユーザーに警告
- `--scope project` の get-all は従来どおり元のファイル名を保持（後方互換）

### 2.2 新規パスヘルパー（config.py）

```python
# 現状: get_github_instructions_dir() はプロジェクトルートを返す
# 新規: プラットフォーム別 User インストラクションパス

def get_user_instruction_path(tool: str, filename: str | None = None) -> Path:
    """Return platform-specific user-scope instruction path.

    tool: codex | claude | opencode | gemini | zed | cursor
    filename: default filename per tool (AGENTS.md / CLAUDE.md / GEMINI.md)
    """
```

**パス対応表**:

| tool | ディレクトリ | デフォルトファイル名 |
|------|-------------|---------------------|
| codex | `~/.codex/` | `AGENTS.md` |
| claude | `~/.claude/` | `CLAUDE.md` |
| opencode | `~/.config/opencode/` | `AGENTS.md` |
| gemini | `~/.gemini/` | `GEMINI.md` |
| zed | `~/.config/zed/`（macOS: `~/Library/Application Support/Zed/`） | `AGENTS.md` |
| cursor | —（対応外、既存の Exit(2) 維持） | — |

### 2.3 オプション設計

```
--scope [project|user]     default: project
--format [standard|codex|claude|opencode|gemini|zed|cursor]  default: standard
--project-dir <dir>        default: 無し（cwd）。既存オプションを流用し新規 --path は作らない
```

**`--format` と `--scope` の関係**:
- `--format standard` + `--scope user` → エラー「--format standard does not support --scope user」
- `--format <platform>` + `--scope user` → 対象プラットフォームの User パスへ配置
- `--format cursor` → Exit(2)（Cursor にネイティブ指示ファイル概念なし。既存挙動を維持）

**バリデーション**:
- `--scope user` + `--format standard` → エラー
- `--scope project` + `--format <platform>` → プロジェクトルートへ配置（`--format` はファイル名マッピングに使用）
- `--project-dir` は **project スコープのみ**有効。`--scope user` 時は無視（警告表示）

**`add_to_gitignore` の扱い**:
- `--scope project` → 従来どおり `add_to_gitignore(dest)` を呼ぶ
- `--scope user` → **呼び出さない**（home 配下の `.gitignore` を辿って dotfiles リポジトリに誤追記する恐れがあるため）

---

## 3. BDD タスク分解

### タスク 01-1: `--format` + `--scope` オプションの導入

**期待する振る舞い**:
- 入力: `ai-adapter agent get AGENTS.md`（現状どおり）
- 応答: プロジェクトルートへ AGENTS.md を配置（後方互換）
- 入力: `ai-adapter agent get AGENTS.md --format codex --scope user`
- 応答: `~/.codex/AGENTS.md` を配置
- 入力: `ai-adapter agent get AGENTS.md --format standard --scope user`
- 応答: エラー終了。「--format standard does not support --scope user」
- 入力: `ai-adapter agent get AGENTS.md --format cursor`
- 応答: Exit(2) で明確なエラーメッセージ（既存挙動）

**受け入れ条件**:
- AC1: `--format` / `--scope` 省略時、既存動作と完全互換（既存テストが全て通過）
- AC2: `--format <platform> --scope user` で `<platform>` の User パスへ配置される
- AC3: `--format cursor` は Exit(2) で明確なエラーメッセージ
- AC4: デプロイ前に既存ファイル確認プロンプト（`--force` で省略可）
- AC5: `--scope user` 時は `add_to_gitignore` を呼び出さない（home の .gitignore を汚染しない）

**データ（仕様例）**:
```
# store: ~/.ai-adapter/instructions/AGENTS.md
$ ai-adapter agent get AGENTS.md --format codex --scope user
Instruction 'AGENTS' copied to /Users/me/.codex/AGENTS.md.

$ ai-adapter agent get CLAUDE.md --format claude --scope user
Instruction 'CLAUDE' copied to /Users/me/.claude/CLAUDE.md.
```

---

### タスク 01-2: `get-all --format <platform> --scope user`

**期待する振る舞い**:
- 入力: `ai-adapter agent get-all --format claude --scope user`
- 応答: 登録済み instruction を `~/.claude/` へ配置
  - **ファイル名をマッピング**: `AGENTS.md` → `CLAUDE.md`（Claude が読む名前に変換）
  - `CLAUDE.md` → `CLAUDE.md`（そのまま）
  - `STYLE.md` → `CLAUDE.md` にマッピング（同名衝突時は `STYLE.md` として配置し警告）
- 入力: 登録 instruction が空
- 応答: 「No instructions registered.」（エラーにしない）

**受け入れ条件**:
- AC1: get-all は**ツールが読むファイル名**にマッピングして User パスへコピー
- AC2: マッピング後の同名衝突時は確認プロンプト + 警告
- AC3: `--env` フィルタは既存仕様を維持
- AC4: `--scope user` 時は `add_to_gitignore` を呼び出さない
- AC5: `--scope project` の get-all は従来どおり元のファイル名を保持（後方互換）

**データ（仕様例）**:
```
登録: AGENTS.md, STYLE.md
$ ai-adapter agent get-all --format claude --scope user
Copied 2 instructions to /Users/me/.claude/.
  AGENTS.md → CLAUDE.md (mapped)
  STYLE.md → CLAUDE.md (conflict, kept as STYLE.md)

# Codex の場合
$ ai-adapter agent get-all --format codex --scope user
Copied 2 instructions to /Users/me/.codex/.
  AGENTS.md → AGENTS.md
  STYLE.md → AGENTS.md (conflict, kept as STYLE.md)
```

---

### タスク 01-3: scan での User スコープ検出強化

**期待する振る舞い**:
- 入力: `ai-adapter scan`（`~/.codex/AGENTS.md` が存在）
- 応答: Codex の instruction として検出（`ScanItem(tool="codex", category="instruction", name="AGENTS.md")`）
- 入力: `~/.gemini/GEMINI.md` が存在（Gemini provider 実装後）
- 応答: Gemini の instruction として検出

**受け入れ条件**:
- AC1: 設計書 05（Gemini）実装前に scan に gemini を追加してはならない（依存関係）
- AC2: 現存ツール（codex/claude/opencode）の User instruction 検出は本設計書で実装
- AC3: 検出はファイル名のみ（内容は読まない）
- AC4: `SCAN_IGNORE_PATTERNS` / `is_ignored()` を適用する（認証情報・秘密情報を含むパスを除外）

**データ（仕様例）**:
```
$ ai-adapter scan --json
{
  "items": [
    {"tool": "codex", "category": "instruction", "name": "AGENTS.md",
     "path": "/Users/me/.codex/AGENTS.md"}
  ]
}
```

---

### タスク 01-4: パスヘルパーと Zed マルチパス対応

**期待する振る舞い**:
- 入力: `get_user_instruction_path("zed")`（macOS）
- 応答: `~/Library/Application Support/Zed/AGENTS.md`
- 入力: `get_user_instruction_path("zed")`（Linux）
- 応答: `~/.config/zed/AGENTS.md`
- 入力: `get_user_instruction_path("gemini", "CONTEXT.md")`
- 応答: `~/.gemini/CONTEXT.md`

**受け入れ条件**:
- AC1: OS 判定は `platform.system()` を使用（macOS / Linux / Windows 対応）
- AC2: Windows の Zed パスは `%APPDATA%\Zed\` を使用
- AC3: パスが存在しないディレクトリでも **作成しない**（デプロイ時のみ mkdir）

**データ（仕様例）**:
```python
# macOS
>>> get_user_instruction_path("zed")
PosixPath('/Users/me/Library/Application Support/Zed/AGENTS.md')

# Linux
>>> get_user_instruction_path("zed")
PosixPath('/home/me/.config/zed/AGENTS.md')
```

---

### タスク 01-5: scope 解決ヘルパーの横断提供（設計書 02/03/04 用）

**期待する振る舞い**:
- 入力: `resolve_scope_path(tool, category, scope, project_dir=None)`
- 応答: ツール×カテゴリ×スコープに応じたデプロイ先パスを返す
  - `("claude", "agents", "project", None)` → `<cwd>/.claude/agents/`
  - `("claude", "agents", "user", None)` → `~/.claude/agents/`
  - `("codex", "skills", "user", None)` → `~/.agents/skills/`（仕様準拠パス）

**受け入れ条件**:
- AC1: ヘルパーは `config.py` に一元定義（設計書 02/03/04 は再利用のみ）
- AC2: `add_to_gitignore` の呼び出し可否を返すフラグ（`use_gitignore: bool`）を含む
  - user スコープ → `use_gitignore=False`
  - project スコープ → `use_gitignore=True`
- AC3: 未定義の tool×category 組み合わせは `ValueError`

---

## 4. 変更対象ファイル

| ファイル | 変更内容 |
|----------|----------|
| `src/ai_adapter/config.py` | `get_user_instruction_path()` / `resolve_scope_path()` 追加 |
| `src/ai_adapter/commands/instruction.py` | `--format`（プラットフォーム選択肢追加）+ `--scope` オプション追加 |
| `src/ai_adapter/scan.py` | User instruction 検出（codex/claude/opencode） |
| `tests/test_instruction.py` | scope/format デプロイの新規テスト（**`test_agent.py` ではない**） |
| `tests/test_config.py` | パスヘルパーのテスト（`test_env_support.py` ではない） |
| `tests/test_scan.py` | User instruction 検出テスト |

---

## 5. テスト計画

```bash
bash scripts/run_tests.sh tests/test_instruction.py -k scope
bash scripts/run_tests.sh tests/test_instruction.py -k format
bash scripts/run_tests.sh tests/test_instruction.py -k user
bash scripts/run_tests.sh tests/test_config.py -k user_instruction
bash scripts/run_tests.sh tests/test_scan.py -k instruction
```

**注意**: `agent`（instruction.py）のテストは `tests/test_instruction.py`。
`tests/test_agent.py` は `sub-agent`（agent.py）のテストであり本機能は含まない。

### 主要テストケース

| # | ケース | 期待結果 |
|---|--------|----------|
| T1 | `--format` / `--scope` なしで get | ルートへ配置（後方互換） |
| T2 | `--format codex --scope user` | `~/.codex/AGENTS.md` に配置 |
| T3 | `--format standard --scope user` | ClickException |
| T4 | `--format cursor` | Exit(2) |
| T5 | 既存 User ファイル + `--force` | 上書きされる |
| T6 | 既存 User ファイル（force なし） | 確認プロンプト |
| T7 | macOS Zed パス | Application Support 配下 |
| T8 | scan で `~/.codex/AGENTS.md` 検出 | instruction カテゴリ |
| T9 | get-all --scope user（ファイル名マッピング） | ツールが読む名前に変換 |
| T10 | get-all --scope user（同名衝突） | 警告 + 任意名で配置 |
| T11 | `--scope user` 時の add_to_gitignore | 呼び出されない（mock で検証） |
| T12 | `--scope project` 時の add_to_gitignore | 呼び出される（回帰） |

---

## 6. リスクと対策

| リスク | 対策 |
|--------|------|
| User ディレクトリへの誤配置 | `--scope user` 時は `--format <platform>` を要求 |
| Zed パスの OS 差異 | ヘルパーで一元化 + プラットフォーム別テスト |
| 既存 CLI の破壊的変更 | `--scope` / `--format` は省略時 project / standard。完全後方互換 |
| get-all のファイル名マッピング漏れ | マッピングテーブルを config.py に一元定義 + テストで全プラットフォームをカバー |
| user スコープでの .gitignore 誤追記 | `resolve_scope_path()` が `use_gitignore=False` を返す仕様で一元制御 |
| 設計書 05/06 との依存 | 01 の format マップに gemini/zed を含めるが、scan 検出は各設計書で |

---

## 7. 完了定義

- [ ] `agent get/get-all --format <platform> --scope user` が codex/claude/opencode/gemini/zed で動作
- [ ] get-all のファイル名マッピングが全プラットフォームで動作
- [ ] `--scope user` 時に `add_to_gitignore` が呼ばれない（テストで担保）
- [ ] Zed の macOS/Linux パスがテストで担保
- [ ] 既存 606 テストが全て通過（後方互換）
- [ ] ruff format / ruff lint / lizard CCN ≤ 20 が通過
- [ ] scan が User instruction を検出
- [ ] README の instruction セクション更新
