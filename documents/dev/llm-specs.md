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
src_md = agents_dir / f"{name}.md"    # .md 優先
src_try = agents_dir / name           # 拡張子なしでも試す
```

---

## 5. 環境変数と設定ファイルの統一

LLM ツール間で共通する設定を環境変数で統一する検討:

```bash
# 共通環境変数（ツール間で共有可能）
AI_ADAPTER_CONFIG=~/.ai-adapter/config.yaml

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
