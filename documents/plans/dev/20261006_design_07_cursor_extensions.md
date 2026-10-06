# 設計書 07: Cursor 拡張（.cursorrules + plugin package）

- 日付: 2026-10-06
- 作成者: Product Manager
- 状態: ドラフト
- 上位計画: [platform_parity_master_design](./20261006_platform_parity_master_design.md)
- 優先度: P2
- 想定規模: 小
- 前提: 既存 Cursor provider（MCP export + skill deploy to .cursor/rules/）は動作済み

---

## 1. 目的

Cursor の残ギャップ（legacy `.cursorrules` と plugin package skills）をカバーする。

### 対象ギャップ

| 行 | パス | 現状 |
|----|------|------|
| 48 | `.cursorrules`（Legacy） | ❌ |
| 49 | `skills/<name>/SKILL.md`（plugin package） | ❌ |

**現状**: Cursor は `--format cursor` で以下が動作済み:
- MCP: `.cursor/mcp.json`
- Skills: `.cursor/rules/*.mdc`

---

## 2. アプローチ

### 2.1 `.cursorrules`（Legacy 対応）

Cursor は `.cursorrules`（プロジェクトルートの単一ファイル）をサポート（レガシー）。

**方針**: `instruction get --format cursor-rules` で `.cursorrules` を生成。

```bash
ai-adapter agent get <name> --format cursorrules
# → ./.cursorrules に配置（指定 instruction のみ）

ai-adapter agent get-all --format cursorrules
# → ./.cursorrules に配置（全 instruction を連結）
```

**変換規則**:
- 登録済み instruction（AGENTS.md 等）の内容を連結
- `.cursorrules` はプレーンテキスト（frontmatter なし）
- 各 instruction の間に区切りコメントを挿入

**注意**: `.cursorrules` は**非推奨**（Cursor 公式は `.cursor/rules/*.mdc` を推奨）。
本機能は移行用として提供する。

### 2.2 plugin package skills（重要: 外部仕様の誤りを修正）

**重要（Plan Architect 指摘 C7-1 反映）**: 初稿では「プロジェクトルート `skills/<name>/SKILL.md`」を
Cursor の plugin package として記載したが、これは**仕様外**である。

Cursor の plugin package の正しい構造:
```
<plugin-name>/
  .cursor-plugin/
    plugin.json        # マニフェスト（必須）
  skills/
    <skill-name>/
      SKILL.md
      [scripts/]
      [references/]
  rules/               # 任意
  mcp.json             # 任意
```

- **インストール先**: `~/.cursor/plugins/local/<plugin-name>/`（または marketplace）
- **マニフェスト必須**: `.cursor-plugin/plugin.json` がないとプラグインとして認識されない
- プロジェクトルートの `skills/` は Cursor の**探索対象外**

**方針**: `skill get --format cursor-plugin` で**真の plugin package**を生成する。

```bash
ai-adapter skill get <name> --format cursor-plugin
# → ~/.cursor/plugins/local/<project-name>/ に plugin.json + skills/ を生成
```

**plugin.json マニフェスト例**:
```json
{
  "name": "<project-name>",
  "version": "1.0.0",
  "description": "Managed by ai-adapter"
}
```

**生成フロー**:
1. `~/.cursor/plugins/local/<project-name>/.cursor-plugin/plugin.json` を生成
2. `~/.cursor/plugins/local/<project-name>/skills/<name>/SKILL.md` にコピー
3. Cursor のプラグイン読み込みを促すメッセージを出力

**既存実装との違い**:
- `--format cursor`: `.cursor/rules/*.mdc` に変換（rules 形式）
- `--format cursor-plugin`: `~/.cursor/plugins/local/<name>/` に真の plugin package を生成

---

## 3. BDD タスク分解

### タスク 07-1: `agent get --format cursor-rules`

**期待する振る舞い**:
- 入力: `ai-adapter agent get AGENTS.md --format cursorrules`
- 応答: `./.cursorrules` に配置
  - **指定された instruction のみ**をプレーンテキストとして出力
  - frontmatter は除去
- 入力: `ai-adapter agent get-all --format cursorrules`
- 応答: 登録済み instruction を全て連結して `./.cursorrules` に出力
  - `.cursorrules` は単一ファイルのため、連結が自然なのは get-all
- 入力: 既存 `.cursorrules` があり `--force` なし
- 応答: 確認プロンプト

**重要（Plan Architect 指摘 M7-1/M7-2 反映）**:
- `get <name>` は指定インストラクションのみ出力（セマンティクス整合）
- 全件連結は `get-all` に分離
- フォーマット名は `cursorrules`（`cursor` と区別。`cursor` は Exit(2) のまま）

**受け入れ条件**:
- AC1: frontmatter（`---\n...\n---`）を除去
- AC2: instruction 間に `# --- <name> ---` の区切りを挿入
- AC3: `--format standard`（ルート配置）は変更なし

**データ（仕様例）**:
```
# store: AGENTS.md + STYLE.md
$ ai-adapter agent get AGENTS.md --format cursorrules
Instruction content written to ./.cursorrules

# .cursorrules 内容（AGENTS.md のみ）
Project coding guidelines...

$ ai-adapter agent get-all --format cursorrules
All instructions written to ./.cursorrules

# .cursorrules 内容（連結）
# --- AGENTS ---
Project coding guidelines...

# --- STYLE ---
Style preferences...
```

---

### タスク 07-2: `skill get --format cursor-plugin`

**期待する振る舞い**:
- 入力: `ai-adapter skill get db-schema --format cursor-plugin`
- 応答: `~/.cursor/plugins/local/<project-name>/` に plugin package を生成
  - `.cursor-plugin/plugin.json`（マニフェスト）
  - `skills/db-schema/SKILL.md`（スキル本体）
- 入力: スキルに補助ファイル（scripts/ 等）がある
- 応答: 補助ファイルも含めてコピー
- 入力: `~/.cursor/plugins/local/<project-name>/` が既に存在
- 応答: 確認プロンプト（`--force` で省略）

**受け入れ条件**:
- AC1: `~/.cursor/plugins/local/<project-name>/` に plugin.json + skills/ を生成
- AC2: `.cursor-plugin/plugin.json` マニフェストを必ず生成（Cursor が認識するために必須）
- AC3: frontmatter は保持（Cursor plugin は SKILL.md を直接読む）
- AC4: `--format cursor`（rules 変換）は変更なし
- AC5: `skill get`（単数）にも `--format` を追加（`get-all` と同じ選択肢定義を共有）

**データ（仕様例）**:
```
# store: ~/.ai-adapter/skills/db-schema/
#   SKILL.md
#   scripts/query.sql

$ ai-adapter skill get db-schema --format cursor-plugin
Skill 'db-schema' installed as Cursor plugin:
  ~/.cursor/plugins/local/my-project/.cursor-plugin/plugin.json
  ~/.cursor/plugins/local/my-project/skills/db-schema/SKILL.md
```

---

### タスク 07-3: `skill get-all --format cursor-plugin`

**期待する振る舞い**:
- 入力: `ai-adapter skill get-all --format cursor-plugin`
- 応答: 登録済みスキルを全て `~/.cursor/plugins/local/<project-name>/skills/` にコピー

**受け入れ条件**:
- AC1: get と同じ変換ロジック
- AC2: `--env` フィルタが機能
- AC3: `--project-dir` を尊重（出力先の決定に使用）

---

### タスク 07-3: `skill get-all --format cursor-plugin`

**期待する振る舞い**:
- 入力: `ai-adapter skill get-all --format cursor-plugin`
- 応答: 登録済みスキルを全て `./skills/<name>/` にコピー

**受け入れ条件**:
- AC1: get と同じ変換ロジック
- AC2: `--env` フィルタが機能

---

## 4. 変更対象ファイル

| ファイル | 変更内容 |
|----------|----------|
| `src/ai_adapter/providers/cursor.py` | `export_cursorrules()` / `deploy_skills_plugin()` 追加 |
| `src/ai_adapter/commands/instruction.py` | `--format cursor-rules` 選択肢 |
| `src/ai_adapter/commands/skill.py` | `--format cursor-plugin` 選択肢追加（**`skill get`（単数）にも追加**。現状 `skill get` に `--format` は存在しないため新規導入） |
| `tests/test_cursor.py` | 新 format のテスト追加 |
| `tests/test_agent.py` | cursor-rules のテスト |
| `tests/test_skill.py` | cursor-plugin のテスト |

---

## 5. テスト計画

```bash
bash scripts/run_tests.sh tests/test_cursor.py
bash scripts/run_tests.sh tests/test_agent.py -k cursor
bash scripts/run_tests.sh tests/test_skill.py -k cursor
```

### 主要テストケース

| # | ケース | 期待結果 |
|---|--------|----------|
| T1 | `agent get --format cursorrules` | .cursorrules 生成（frontmatter 除去、指定分のみ） |
| T2 | `agent get-all --format cursorrules` | 全 instruction を連結 |
| T3 | `skill get --format cursor-plugin` | `~/.cursor/plugins/local/<name>/` に plugin.json + skills/ 生成 |
| T4 | `skill get --format cursor-plugin`（補助ファイルあり） | 全ファイルコピー |
| T5 | `skill get --format cursor`（回帰） | .cursor/rules/*.mdc |
| T6 | 既存 .cursorrules + force なし | 確認プロンプト |
| T7 | `skill get --format cursor-plugin`（plugin.json 存在確認） | マニフェストが生成されている |

---

## 6. リスクと対策

| リスク | 対策 |
|--------|------|
| `.cursorrules` の非推奨 | README で「legacy / 移行用」と明記。`.cursor/rules/` 推奨を併記 |
| plugin package の形式変更 | Cursor 公式ドキュメントを定期確認 |
| format 選択肢の増加 | ヘプに各 format の出力先を明記 |

---

## 7. 完了定義

- [ ] `agent get/get-all --format cursorrules` が `.cursorrules` を生成
- [ ] `skill get --format cursor-plugin` が `~/.cursor/plugins/local/<name>/` に plugin package を生成
- [ ] `.cursor-plugin/plugin.json` マニフェストが必ず生成される
- [ ] 既存 `--format cursor` のテストが全て通過
- [ ] ruff format / ruff lint / lizard CCN ≤ 20 が通過
- [ ] README の Cursor セクション更新（legacy / plugin の位置づけを明記）
