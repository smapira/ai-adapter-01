# LLM 設定ファイル仕様書 — ai-adapter

> **目的**: 各 AI エージェント（Copilot, Claude Code, OpenCode, Cursor, Windsurf, Continue, Aider など）が使用する設定ファイル・ディレクトリの仕様をまとめ、`ai-adapter` とそれらの対応関係を整理する。

---

## 1. 各 LLM ツールの設定ファイル仕様

### 1.1 GitHub Copilot（VS Code 拡張機能）

| 項目 | 仕様 |
|------|------|
| 設定ディレクトリ | `.github/`（プロジェクトルート） |
| 指示ファイル | `.github/instructions/*.md` |
| エージェント定義 | `.github/agents/*.md` |
| スクリプト | `.github/bin/*` |
| 読み込み順 | `.github/instructions/` 内の全 `.md` ファイルを自動読み込み |
| AI エージェント機能 | `.github/agents/` に定義したエージェントを `@エージェント名` で選択可能 |

**`.github/instructions/*.md` のフォーマット:**

```markdown
# プロジェクト固有の指示

## コーディング規約
- 変数名はキャメルケース
- エラーハンドリングは必行う

## テスト
- pytest を使用
- テストカバレッジ 80%以上
```

- プレーンマークダウン形式
- 複数ファイルを配置すると全てマージされて Copilot に渡される

**`.github/agents/*.md` のフォーマット:**

```markdown
---
name: reviewer
description: コードレビュー特化型エージェント
---

あなたはコードレビュアーです。
セキュリティ、パフォーマンス、可読性の観点からコードをレビューしてください。
```

- YAML frontmatter でメタデータを記述
- 本文でエージェントへの指示を記述
- `@reviewer` のように呼び出して使用

**`.github/bin/` の使い方:**

```bash
.github/bin/
├── review-pr.sh          # PRレビュー用スクリプト
├── run-tests.sh          # テスト実行スクリプト
└── format-code.sh        # コード整形スクリプト
```

- エージェントが実行可能なスクリプトを配置
- 実行権限（chmod +x）が必要

---

### 1.2 Claude Code（Anthropic CLI ツール）

| 項目 | 仕様 |
|------|------|
| 設定ファイル | `CLAUDE.md`（プロジェクトルート） |
| 代替ファイル | `.github/copilot-instructions.md`（フォールバック） |
| 対応バージョン | Claude Code CLI（公式） |
| 形式 | マークダウン |
| スコープ | プロジェクト単位 |

**`CLAUDE.md` のフォーマット:**

```markdown
# Claude Code へのプロジェクト指示

## ビルドコマンド
- `npm run build` でビルド
- `npm test` でテスト実行

## コーディング規約
- TypeScript 使用
- 関数には JSDoc コメントを付与
- 非同期処理は async/await を使用

## テスト
- Vitest 使用
- `npm run test:run` で CI 実行
```

**特徴:**
- プロジェクトルートの `CLAUDE.md` を自動検出
- 存在しない場合は `.github/copilot-instructions.md` をフォールバックとして参照
- ビルド・テスト・lint コマンドを明示すると Claude が正確に実行

---

### 1.3 OpenCode（ターミナル AI コーディングエージェント）

| 項目 | 仕様 |
|------|------|
| 設定ディレクトリ | `.opencode/`（プロジェクトルート） |
| 設定ファイル | `.opencode/config.json` |
| ルールディレクトリ | `.opencode/rules/` |
| フックディレクトリ | `.opencode/hooks/` |
| 代替読み込み | `CLAUDE.md`, `.github/copilot-instructions.md` も参照 |
| 形式 | JSON / マークダウン |

**`.opencode/config.json` のフォーマット:**

```json
{
  "model": "claude-sonnet-4-20250514",
  "theme": "dark",
  "rules": ["rules/backend.md", "rules/frontend.md"],
  "hooks": {
    "preCommand": "hooks/pre-command.sh"
  }
}
```

**`.opencode/rules/*.md` のフォーマット:**

```markdown
# バックエンド開発ルール

## アーキテクチャ
- Clean Architecture に従う
- Repository パターンを使用

## DB
- Prisma ORM を使用
- マイグレーションは `prisma migrate dev`
```

**特徴:**
- `config.json` でモデル選択やテーマを設定
- `rules/` に分割したルールファイルを配置
- `hooks/` でコマンド実行前後のスクリプトを設定
- `CLAUDE.md` や `.github/copilot-instructions.md` も自動読み込み

---

### 1.4 Cursor（AI ファースト IDE）

| 項目 | 仕様 |
|------|------|
| 設定ディレクトリ | `.cursor/` |
| ルールディレクトリ | `.cursor/rules/` |
| ルールファイル | `.cursor/rules/*.mdc` |
| 設定ファイル | `.cursor/config.json`（未指定） |
| プロジェクトルール | `.cursorrules`（旧形式） |

**`.cursor/rules/*.mdc` のフォーマット:**

```markdown
---
description: フロントエンド開発ルール
globs: src/**/*.{ts,tsx}
---
TypeScript と React のベストプラクティスに従ってください。
- 関数コンポーネント + Hooks を使用
- Tailwind CSS でスタイリング
```

- YAML frontmatter で `description`（説明）と `globs`（適用ファイルパターン）を指定
- `globs` でルールを適用するファイルパターンを制限可能

---

### 1.5 Windsurf（AI IDE）

| 項目 | 仕様 |
|------|------|
| ルールファイル | `.windsurfrules`（プロジェクトルート） |
| ディレクトリ | `.windsurf/`（オプション） |
| 形式 | マークダウン |
| AI モデル | 独自モデル + 外部モデル連携 |

**`.windsurfrules` のフォーマット:**

```markdown
# Windsurf ルール

## フロントエンド
- React + TypeScript
- コンポーネントは atomic 設計

## テスト
- ユニットテスト必須
```

- ルート直置きの単一ファイル形式
- シンプルなマークダウン

---

### 1.6 Continue（VS Code + JetBrains 拡張機能）

| 項目 | 仕様 |
|------|------|
| 設定ファイル | `.continuerc.json`（プロジェクトルート） |
| ディレクトリ | `.continue/` |
| 形式 | JSON |
| モデル設定 | 複数モデルの切り替え可能 |

**`.continuerc.json` のフォーマット:**

```json
{
  "rules": [
    "プロジェクトは TypeScript で記述されています",
    "テストは Vitest を使用します",
    "API は Express + Prisma で構築します"
  ],
  "tabAutocompleteModel": {
    "title": "Tab Autocomplete",
    "provider": "anthropic",
    "model": "claude-sonnet-4"
  }
}
```

- `rules` 配列にプロジェクトルールを記述
- モデルやプロバイダの設定が可能

---

### 1.7 Aider（ターミナル AI ペアプログラミング）

| 項目 | 仕様 |
|------|------|
| 設定ファイル | `.aider.conf.yml` |
| 規約ファイル | `CONVENTIONS.md`（プロジェクトルート） |
| ディレクトリ | `.aider/` |
| 形式 | YAML / マークダウン |

**`CONVENTIONS.md` のフォーマット:**

```markdown
# コーディング規約

## 命名規則
- クラス: PascalCase
- 関数: snake_case

## データベース
- PostgreSQL
- SQLAlchemy 2.0
```

**`.aider.conf.yml` のフォーマット:**

```yaml
model: claude-sonnet-4
edit-format: udiff
auto-commits: true
```

- `CONVENTIONS.md` でコーディング規約を定義
- `.aider.conf.yml` でモデルや挙動を設定

---

## 2. ai-adapter と各 LLM 設定の対応表

### 出力先マッピング

| ai-adapter コマンド | 出力先ディレクトリ | 対応する LLM ツール |
|--------------------|------------------|-------------------|
| `agent add/get` | `.github/agents/` | GitHub Copilot |
| `bin add/get` | `.github/bin/` | GitHub Copilot |
| `get agent` → `.github/agents/` | `.github/agents/` | GitHub Copilot（エージェント機能） |
| `get bin` → `.github/bin/` | `.github/bin/` | GitHub Copilot（ツール実行） |

### 現状の ai-adapter サポート範囲

| LLM ツール | 設定パス | ai-adapter 対応状況 |
|-----------|---------|-------------------|
| GitHub Copilot | `.github/instructions/` `.github/agents/` `.github/bin/` | ✅ 完了（agent, bin） |
| Claude Code | `CLAUDE.md` | ❌ 未対応（今後対応候補） |
| OpenCode | `.opencode/rules/` `.opencode/config.json` | ❌ 未対応（今後対応候補） |
| Cursor | `.cursor/rules/*.mdc` | ❌ 未対応（今後対応候補） |
| Windsurf | `.windsurfrules` | ❌ 未対応（今後対応候補） |
| Continue | `.continuerc.json` | ❌ 未対応（今後対応候補） |
| Aider | `CONVENTIONS.md` `.aider.conf.yml` | ❌ 未対応（今後対応候補） |

---

## 3. 今後の拡張方針

### フェーズ: マルチツール対応

`agent get` / `bin get` の出力先を `--tool` オプションで切り替え可能にする。

```bash
# Copilot（.github/ 配下）
ai-adapter agent get reviewer                          # → .github/agents/reviewer.md
ai-adapter bin get deploy.sh                           # → .github/bin/deploy.sh

# Claude Code（CLAUDE.md）
ai-adapter agent get reviewer --tool claude            # → CLAUDE.md にマージ
ai-adapter agent get reviewer --tool claude --mode merge  # → CLAUDE.md に追記

# OpenCode（.opencode/ 配下）
ai-adapter agent get reviewer --tool opencode          # → .opencode/rules/reviewer.md

# Cursor（.cursor/ 配下）
ai-adapter agent get reviewer --tool cursor            # → .cursor/rules/reviewer.mdc

# Aider（CONVENTIONS.md）
ai-adapter agent get reviewer --tool aider             # → CONVENTIONS.md にマージ
```

### 設定ファイル間の相互運用性

各ツールは以下のルールで他ツールの設定をフォールバックとして参照する:

```
Claude Code の読み込み順:
  1. CLAUDE.md
  2. .github/copilot-instructions.md（フォールバック）

OpenCode の読み込み順:
  1. .opencode/rules/*.md
  2. CLAUDE.md（フォールバック）
  3. .github/copilot-instructions.md（フォールバック）

Cursor の読み込み順:
  1. .cursor/rules/*.mdc
  2. .cursorrules（旧形式、フォールバック）
```

このため、`CLAUDE.md` 1つ書けば複数のツールで共有できる。

---

## 4. agents/ の拡張子ルール

| 拡張子 | 用途 | 対応ツール |
|--------|------|-----------|
| `.md` | マークダウン形式の指示ファイル | GitHub Copilot, OpenCode, Claude Code, Windsurf, Aider |
| `.mdc` | frontmatter 付きマークダウン | Cursor |
| `.json` | JSON 設定ファイル | OpenCode, Continue |
| `.yaml` / `.yml` | YAML 設定ファイル | Aider, ai-adapter |

現在の ai-adapter は `.md` を基本とし、`agent get` では `.md` 優先で検索する。

```python
# agent.py の検索ロジック（参考）
src_md = agents_dir / f"{name}.md"  # .md 優先
src_try = agents_dir / name  # 拡張子なしでも試す
```

---

## 5. 環境変数と設定ファイルの統一

LLM ツール間で共通する設定を環境変数で統一する検討:

```bash
# 共通環境変数（ツール間で共有可能）
AI_ADAPTER_CONFIG=~/.ai-adapter/config.json

# 各ツール固有の環境変数
GITHUB_TOKEN=ghp_xxx          # GitHub API トークン
ANTHROPIC_API_KEY=sk-ant-xxx  # Anthropic（Claude）API キー
OPENAI_API_KEY=sk-xxx         # OpenAI API キー
```

---

## 6. .opencode/ 詳細仕様（参考）

OpenCode の設定は JSON 形式で、以下の構造を持つ:

```json
{
  "model": "claude-sonnet-4-20250514",
  "theme": "dark",
  "tabAutocomplete": true,
  "rulesDir": ".opencode/rules",
  "rules": [
    ".opencode/rules/general.md"
  ],
  "hooks": {
    "preCommand": ".opencode/hooks/pre-command.sh",
    "postCommand": ".opencode/hooks/post-command.sh"
  }
}
```

**`.opencode/rules/` の配置例:**

```
.opencode/
├── config.json
├── rules/
│   ├── general.md           # 全般ルール
│   ├── backend.md           # バックエンド固有ルール
│   └── frontend.md          # フロントエンド固有ルール
└── hooks/
    ├── pre-command.sh       # コマンド実行前フック
    └── post-command.sh      # コマンド実行後フック
```

---

## 7. CLAUDE.md 詳細仕様（参考）

Claude Code が認識する `CLAUDE.md` の推奨構成:

```markdown
# プロジェクト名

## 概要
簡潔なプロジェクト説明

## ビルド・テスト・実行コマンド
- Build: `npm run build`
- Test: `npm run test`
- Lint: `npm run lint`
- Dev: `npm run dev`
- TypeCheck: `npm run typecheck`

## プロジェクト構成
プロジェクトのディレクトリ構成と主要ファイルの役割

## コーディング規約
使用する言語、フレームワーク、命名規則など

## アーキテクチャ上の制約
重要な設計判断や制約事項
```

**注意点:**
- ビルド・テストコマンドは正確に記述すること（Claude が実際に実行するため）
- 長すぎる `CLAUDE.md` は分割して `.github/copilot-instructions.md` に委譲するのも手
- `CLAUDE.md` はプロジェクトルートに 1 つのみ

---

## 8. .github/copilot-instructions.md 標準仕様

GitHub Copilot と Claude Code の両方で読まれる共通指示ファイル:

| ツール | 読み込み条件 |
|--------|------------|
| GitHub Copilot | `.github/instructions/` 配下の全 `.md`（デフォルト） |
| Claude Code | `CLAUDE.md` がない場合のフォールバック |
| OpenCode | `CLAUDE.md` がない場合のフォールバック |

このファイルはプロジェクト横断的な指示を記述するのに適している。

---

## 9. ai-adapter の .opencode / CLAUDE.md 対応計画（※将来）

```python
# 将来的な config.py の拡張イメージ
def get_opencode_rules_dir() -> Path:
    """カレントプロジェクトの .opencode/rules/ を返す。"""
    return Path.cwd() / ".opencode" / "rules"


def get_claude_md_path() -> Path:
    """カレントプロジェクトの CLAUDE.md を返す。"""
    return Path.cwd() / "CLAUDE.md"


def get_cursor_rules_dir() -> Path:
    """カレントプロジェクトの .cursor/rules/ を返す。"""
    return Path.cwd() / ".cursor" / "rules"
```

各出力先へのコピー処理は `--tool` オプションで切り替える形を想定:

```bash
# 将来のイメージ
ai-adapter agent add --tool copilot instructions.md     # → .github/agents/
ai-adapter agent add --tool claude instructions.md      # → CLAUDE.md にマージ
ai-adapter agent add --tool opencode instructions.md    # → .opencode/rules/
ai-adapter agent add --tool cursor instructions.md     # → .cursor/rules/
```

---

## 10. エージェント設定仕様（Agent Configuration）

### 10.1 エージェント定義の基本構造

AI エージェントは、名前・役割・指示・ツールセットを定義した設定ファイルで構成される。  
ツールごとにフォーマットは異なるが、共通して以下の要素を持つ:

| 要素 | 説明 | 必須 |
|------|------|------|
| `name` | エージェント名（識別子） | ✅ |
| `description` | 役割・目的の説明 | ✅ |
| `instructions` | エージェントへの指示内容 | ✅ |
| `tools` / `commands` | 使用可能なツール・コマンド一覧 | ❌ |
| `model` | 使用する AI モデルの指定 | ❌ |
| `temperature` | 応答のランダム性パラメータ | ❌ |
| `globs` / `applyTo` | 適用対象ファイルパターン | ❌ |

### 10.2 VS Code GitHub Copilot エージェント

**`.github/agents/*.md` (YAML frontmatter + Markdown):**

```markdown
---
name: reviewer
description: コードレビュー特化型エージェント
---

あなたはコードレビュアーです。
セキュリティ、パフォーマンス、可読性の観点からコードをレビューしてください。

## レビューチェックリスト
- SQL インジェクション対策
- メモリリーク
- エッジケースのハンドリング
```

- Copilot Chat で `@reviewer` のように呼び出して使用
- YAML frontmatter で `name` と `description` を定義
- frontmatter 以降の本文がエージェントへの指示（system prompt）
- `@` で参照可能にするにはエージェント名が一意である必要がある

### 10.3 VS Code Agent カスタマイズファイル

VS Code の Agent モードでは以下のカスタマイズファイルをサポートする:

| ファイル | パス（例） | 用途 |
|---------|-----------|------|
| `.instructions.md` | `.github/copilot-instructions.md` など | プロジェクト共通の指示 |
| `.prompt.md` | ユーザープロンプトフォルダ内 | エージェントへの追加プロンプト |
| `.agent.md` | `.github/agents/` 配下 | エージェント定義本体 |
| `SKILL.md` | `.claude/skills/` 配下 | 特定タスク用スキル定義 |
| `copilot-instructions.md` | `.github/` 直下 | Copilot 共通指示 |
| `AGENTS.md` | `.github/` 直下 | エージェント一覧定義 |

**`copilot-instructions.md` のフォーマット:**

```markdown
# プロジェクト共通指示

## コーディング規約
- TypeScript strict モード
- 関数には JSDoc コメント
- 非同期処理は async/await

## テスト
- Vitest
- `npm run test` で実行
```

- プレーンマークダウン形式
- VS Code の設定でパスをカスタマイズ可能
- プロジェクトルートからの相対パスで指定

### 10.4 VS Code ユーザープロンプト設定

VS Code の `github.copilot.chat.customInstructions` 設定でユーザー固有の指示を指定:

```json
// settings.json
{
  "github.copilot.chat.customInstructions": [
    {
      "path": "/Users/username/.github/prompts/default.md",
      "description": "デフォルト指示"
    }
  ]
}
```

または、プロンプトフォルダに `.prompt.md` ファイルを配置:

```
~/.vscode/
└── prompts/
    ├── 01-default.prompt.md       # 常に適用される基本指示
    ├── 02-test-first.prompt.md    # テスト駆動開発用指示
    └── 03-security.prompt.md      # セキュリティレビュー用指示
```

- 数値プレフィックスで読み込み順を制御
- `.prompt.md` 拡張子で VS Code が自動認識
- ユーザーレベルとプロジェクトレベルの両方で設定可能

### 10.5 エージェントの YAML frontmatter 統一仕様（ai-adapter 標準）

ai-adapter が管理するエージェントファイルの標準 frontmatter フォーマット:

```yaml
---
# 必須
name: reviewer                    # エージェント名（一意）
description: コードレビュー特化型  # 簡単な説明

# オプション
model: claude-sonnet-4            # 推奨モデル
temperature: 0.3                  # 応答のランダム性 (0.0-1.0)
globs: "**/*.{ts,tsx}"           # 適用対象ファイル（省略時は全ファイル）
tags: [review, security]          # 分類タグ
version: 1                        # バージョン
author: smapira                   # 作成者
---
```

### 10.6 agent_bindings と環境解決

```yaml
# ~/.ai-adapter/config.yaml 内
agent_bindings:
  - agent: reviewer              # エージェント名
    env: myhome                  # 紐付ける環境名
  - agent: implementer
    env: office
```

- エージェント名と環境を 1:1 で紐付け
- `bin` コマンドで `[env]` 省略時にエージェント名から環境を自動解決
- 同じエージェントを異なる環境で使い分け可能

---

## 11. スキル設定仕様（Skill Configuration）

### 11.1 スキル定義の基本構造

スキルは特定のタスクやドメインに特化した知識パッケージ。  
再利用可能な形で定義され、エージェントが動的にロードできる。

| 要素 | 説明 | 必須 |
|------|------|------|
| `name` | スキル名 | ✅ |
| `description` | スキルの説明 | ✅ |
| `instructions` | スキル実行時の指示 | ✅ |
| `applyTo` | 適用条件（ファイルパターン等） | ❌ |
| `tools` | スキルで使用するツール | ❌ |
| `dependencies` | 依存する他のスキル | ❌ |

### 11.2 SKILL.md フォーマット（YAML frontmatter + Markdown）

```markdown
---
name: database-schema
description: データベーススキーマ設計・レビューの知識
applyTo: "**/*.prisma"
---

# データベーススキーマスキル

## 命名規則
- テーブル名: 複数形スネークケース (`users`, `blog_posts`)
- カラム名: スネークケース (`created_at`, `updated_at`)

## ベストプラクティス
- 外部キーにはインデックスを付与
- ソフトデリート采用時は `deleted_at` カラム
- 時刻は UTC で保存

## マイグレーション
```bash
npx prisma migrate dev --name <migration_name>
```
```

**SKILL.md の配置ルール:**

```
.claude/
└── skills/
    ├── database-schema/
    │   ├── SKILL.md           # スキル定義（必須）
    │   └── examples/
    │       └── schema.prisma  # 参考ファイル
    ├── react-components/
    │   └── SKILL.md
    └── security-review/
        └── SKILL.md
```

- 各スキルは `.claude/skills/<skill-name>/SKILL.md` に配置
- ディレクトリ名がスキル名になる
- 同じディレクトリ内に参考ファイルを同梱可能

### 11.3 VS Code Agent スキル設定

VS Code の Agent カスタマイズ機能におけるスキル定義:

```yaml
# .github/agents/skills.yml または AGENTS.md
skills:
  - name: database-schema
    description: DBスキーマ設計
    path: .claude/skills/database-schema/SKILL.md
    applyTo: "**/*.prisma"
  - name: test-writing
    description: テスト記述
    path: .claude/skills/test-writing/SKILL.md
    applyTo: "**/*.test.ts"
```

**AGENTS.md のフォーマット（YAML frontmatter + Markdown）:**

```markdown
---
agents:
  - name: reviewer
    description: コードレビュー
    instructions: .github/agents/reviewer.md
  - name: implementer
    description: 実装
    instructions: .github/agents/implementer.md
skills:
  - name: database-schema
    description: DB設計知識
    path: .claude/skills/database-schema
---
```

- YAML frontmatter でエージェントとスキルの一覧を定義
- 本文はプロジェクト全体の補足説明として機能

### 11.4 スキルの discovery 機構

各ツールにおけるスキルの検出方法:

| ツール | 検出パス | 検出方法 |
|--------|---------|---------|
| Claude Code | `.claude/skills/*/SKILL.md` | ディレクトリスキャン |
| VS Code Copilot | `.github/agents/*.md` | ファイルスキャン |
| VS Code Agent | 設定で指定された `.prompt.md` | 明示指定 |
| OpenCode | `.opencode/rules/*.md` | ディレクトリスキャン |
| Cursor | `.cursor/rules/*.mdc` | ディレクトリスキャン |

### 11.5 ai-adapter とスキルの統合（将来計画）

ai-adapter でスキルを管理する案:

```bash
# スキルの追加（エージェントと似た操作体系）
ai-adapter skill add database-schema/    # .claude/skills/ にスキルを追加
ai-adapter skill list                    # スキル一覧表示
ai-adapter skill get database-schema     # スキルをプロジェクトに展開
ai-adapter skill remove database-schema  # スキル削除

# エージェントとスキルの紐付け
ai-adapter agent link-skill reviewer database-schema
# → reviewer エージェントが database-schema スキルを自動ロード

# スキル検索
ai-adapter skill search prisma
# → database-schema など関連スキルを表示
```

---

## 12. コマンド・ツール設定仕様（Command / Tool Configuration）

### 12.1 コマンド定義の基本構造

AI エージェントが実行可能なコマンド・ツールの定義。

| 要素 | 説明 | 必須 |
|------|------|------|
| `name` | コマンド名 | ✅ |
| `path` | スクリプトファイルのパス | ✅ |
| `description` | コマンドの説明 | ✅ |
| `env` | 所属環境 | ❌ |
| `args` | 引数の定義 | ❌ |
| `timeout` | タイムアウト時間 | ❌ |

### 12.2 `.github/bin/` スクリプト仕様

GitHub Copilot が認識する実行可能スクリプト:

```bash
.github/bin/
├── review-pr.sh          # PRレビュー（実行権限必要）
├── run-tests.sh          # テスト実行
├── format-code.sh        # コード整形
├── lint-check.sh         # Lintチェック
└── deploy.sh             # デプロイ
```

**スクリプトの要件:**

```bash
#!/bin/bash
# description: このスクリプトの説明
# usage: ai-adapter bin get deploy
# env: myhome

set -euo pipefail

echo "デプロイを開始します..."
# 実際の処理
```

- `chmod +x` で実行権限を付与すること
- シェバング（`#!/bin/bash` 等）を先頭に記述
- `description:` コメントで説明を記載（推奨）
- エラーハンドリングを適切に行う（`set -euo pipefail`）

### 12.3 MCP（Model Context Protocol）ツール定義

MCP は AI エージェントが外部ツールを利用するための標準プロトコル:

```json
// .mcp.json または claude.json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-filesystem", "."]
    },
    "database": {
      "command": "python",
      "args": ["mcp-server.py"],
      "env": {
        "DATABASE_URL": "${DATABASE_URL}"
      }
    }
  }
}
```

**MCP サーバー設定の配置場所:**

| ツール | 設定ファイル | パス |
|--------|------------|------|
| Claude Desktop | `claude.json` | `~/.claude/claude.json` |
| Claude Code | `.mcp.json` | プロジェクトルート |
| VS Code Copilot | `.vscode/mcp.json` | プロジェクトルート |
| Cursor | `.cursor/mcp.json` | プロジェクトルート |
| Continue | `config.json` | `~/.continue/config.json` |

**MCP サーバーの種類:**

```bash
# ビルトインサーバー（公式提供）
npx @modelcontextprotocol/server-github          # GitHub API
npx @modelcontextprotocol/server-filesystem      # ファイル操作
npx @modelcontextprotocol/server-postgres        # PostgreSQL
npx @modelcontextprotocol/server-sqlite          # SQLite
npx @modelcontextprotocol/server-puppeteer       # ブラウザ操作
npx @modelcontextprotocol/server-memory          # 記憶/ベクトルDB
npx @modelcontextprotocol/server-web-search      # Web検索

# カスタムサーバー（Python / TypeScript で実装）
python mcp-server.py    # Python MCP サーバー
node mcp-server.js      # TypeScript MCP サーバー
```

### 12.4 OpenCode フック（hooks）仕様

コマンド実行前後に自動実行されるスクリプト:

```json
{
  "hooks": {
    "preCommand": ".opencode/hooks/pre-command.sh",
    "postCommand": ".opencode/hooks/post-command.sh"
  }
}
```

**フックスクリプトの例:**

```bash
#!/bin/bash
# .opencode/hooks/pre-command.sh
# コマンド実行前に自動実行される

echo "=== Pre-command hook ==="
# 環境変数のチェック
if [ -z "$DATABASE_URL" ]; then
  echo "Warning: DATABASE_URL が設定されていません"
fi
```

- `preCommand`: コマンド実行直前に実行
- `postCommand`: コマンド実行直後に実行
- 終了コードが 0 以外の場合はコマンド実行を中断可能

### 12.5 ai-adapter の bin コマンド仕様（詳細）

**`bin add` の内部動作:**

```python
# bin.py の処理（概念）
def bin_add(env: str | None, path: str, description: str | None, agent: str | None):
    # 1. 環境の解決（省略時は agent_bindings → default_env）
    resolved_env = resolve_env(config, env, agent)

    # 2. ファイルを ~/.ai-adapter/bin/ にコピー
    src = Path(path).resolve()
    dest = get_bins_dir() / src.name
    shutil.copy2(src, dest)

    # 3. 実行権限を付与
    dest.chmod(0o755)

    # 4. config.json に登録
    config.bins.append(Bin(name=src.name, env=resolved_env, description=desc))
```

**`bin get` の内部動作:**

```python
def bin_get(env: str | None, name: str, agent: str | None):
    # 1. 環境の解決
    resolved_env = resolve_env(config, env, agent)

    # 2. config.json から env + name で検索
    bin_entry = find_bin(config, resolved_env, name)

    # 3. ~/.ai-adapter/bin/<name> → .github/bin/<name> にコピー
    src = get_bins_dir() / bin_entry.name
    dest = get_github_bins_dir() / bin_entry.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    dest.chmod(0o755)
```

### 12.6 ツール定義の標準 YAML フォーマット（ai-adapter 標準）

```yaml
# ~/.ai-adapter/config.json 内の bins セクション
bins:
  - name: review-pr.sh
    env: myhome
    description: "PR レビュー補助スクリプト"
    tags: [review, github]
    timeout: 300                  # タイムアウト（秒）
    args:                        # 引数定義
      - name: pr-number
        type: integer
        description: "PR 番号"
        required: true

  - name: deploy.sh
    env: office
    description: "本番環境デプロイ"
    tags: [deploy, production]
    timeout: 600
    env_vars:                    # 必要な環境変数
      - DEPLOY_KEY
      - DEPLOY_SECRET
```

### 12.7 ai-adapter と MCP の統合（将来計画）

```bash
# MCP サーバーを ai-adapter で管理
ai-adapter mcp add github          # MCPサーバー設定を追加
ai-adapter mcp list                # MCPサーバー一覧
ai-adapter mcp remove github       # MCPサーバー設定を削除

# 環境ごとに MCP サーバーを切り替え
ai-adapter mcp link-env github myhome    # myhome環境でgithub MCPを有効化

# MCP サーバー設定の同期
ai-adapter sync                          # ~/.ai-adapter/ ごと同期
```
