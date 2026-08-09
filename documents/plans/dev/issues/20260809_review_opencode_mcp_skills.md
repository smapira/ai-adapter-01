# opencode install MCP・Skills 拡張計画レビュー

## 優先度
🔴 高（複数の指摘事項あり）

## 対象
- 計画書: `documents/plans/dev/20260809_opencode_install_mcp_skills.md`
- 関連ファイル:
  - `src/ai_adapter/providers/opencode.py` (`opencode_install()` 関数)
  - `src/ai_adapter/models.py` (`MCPServer` データクラス)
  - `tests/test_opencode.py` (既存テスト)
  - `src/ai_adapter/commands/mcp.py` (MCP 操作、変換パターン参照)
  - `src/ai_adapter/providers/openclaw.py` (MCP 変換パターン参照)

---

## 指摘事項

### 1. 🔴 skills.paths と既存 instructions の取扱いが未整理

**問題**:
既存の `opencode_install()` (opencode.py L112-114) は skills を `instructions` セクションに `.github/skills/*/SKILL.md` として追加している。計画書は `skills.paths` を新設するが、既存の instructions への追加をどう扱うか記述がない。

```python
# 既存コード (opencode.py L112-114)
if cfg.skills:
    instructions.append(".github/skills/*/SKILL.md")
```

計画書の Task 2 は `skills.paths` を追加するが、この既存ロジックを維持するか削除するかが不明確。

**改善案**:
- `skills.paths` を採用する場合、既存の `instructions` への `.github/skills/*/SKILL.md` 追加は削除すべき
- opencode の `skills.paths` はディレクトリを指し、SKILL.md の自動検索は opencode 側が行うため、instructions に含める必要はない
- 計画書の Task 3.1（非回帰テスト）に「skills が登録されている場合、`instructions` に `.github/skills/*/SKILL.md` が含まれなくなり、`skills.paths` に `.github/skills` が含まれる」シナリオを追加

---

### 2. 🔴 MCPServer の `tools` フィールドが無視される

**問題**:
`MCPServer` データクラス (models.py L187) には `tools: list[str]` フィールドがあり、登録時に `["vscode", "claude", "cursor"]` がデフォルト設定される (mcp.py L123)。計画書の `_convert_mcp_to_opencode()` はこのフィールドを無視し、`enabled` のみで判定する。

opencode は「opencode 専用」の MCP サーバーであるため、他ツール (vscode/cursor) 専用のサーバーまで含めると問題になる可能性がある。

**改善案**:
- フィルタリングロジックを追加: `servers = [s for s in cfg.mcp_servers if "opencode" in s.tools or not s.tools]`
- または、opencode が全ての MCP サーバーを受け入れる仕様であることを明示
- 既存の openclaw プロバイダー (openclaw.py L52-55) は `enabled` フィルタのみで `tools` を見ていないため、現状維持でも一貫性はある。仕様として明文化すべき

---

### 3. 🔴 `_convert_mcp_to_opencode()` の `args` なし時の挙動

**問題**:
計画書の変換ロジック:
```python
"command": [server.command] + server.args,
```

`args` が空リストの場合、`["npx"]` となり正しい。しかし、`server.command` が既にコマンドと引数を含む文字列（例: `"npx @modelcontextprotocol/server-github"`）の場合、`["npx @modelcontextprotocol/server-github"]` となり、opencode の配列形式と不整合になる。

**改善案**:
- `mcp add` の `--command` は単一コマンドのみ受け付けるため、現状では問題にならないが、防御的に `shlex.split()` でパースする余地がある
- 計画書に「`command` は単一トークンのみを前提とし、引数は `args` で指定すること」と注記を追加

---

### 4. 🟡 既存 opencode.json のマージ未対応

**問題**:
現在の `opencode_install()` は既存の `opencode.json` を完全上書きする。ユーザーが手動で追加した MCP サーバーやカスタム設定が消失する。

**改善案**:
- 現在の動作（完全上書き）を維持するなら、計画書に「既存ファイルは上書きする」と明記
- 将来的にマージ機能を追加する場合、openclaw の `merge_into_openclaw_json()` パターンを参考にできる
- 現時点では既存動作と一致するため、優先度は低い

---

### 5. 🟡 テストカバレッジの不足

**問題**:
計画書の BDD テーブルに以下のシナリオが欠落している:

| # | 欠落シナリオ | 理由 |
|---|------------|------|
| - | MCP サーバーの `args` が空リスト | `command: ["npx"]` となることを確認 |
| - | MCP サーバーの `env_keys` が空リスト | `environment` キーが出力されないことを確認 |
| - | Skills が登録されている場合の `instructions` 変化 | `.github/skills/*/SKILL.md` が instructions から消えることの確認 |
| - | MCP + Skills + Agents の全組み合わせ | 複数セクションが正しく共存することの確認 |
| - | MCP サーバーの `name` に特殊文字が含まれる場合 | JSON キーとして適切か |

**改善案**:
上記シナリオを追加。特に「Skills 登録時の instructions 変化」は指摘事項 1 と関連し、動作の整合性を確認するため重要。

---

### 6. 🟡 BDD テーブルの入力データが簡略すぎる

**問題**:
BDD テーブルの「入力データ」列が `mcp_servers: [{name: "github", command: "npx", ...}]` のような簡略記法であり、実際の `MCPServer` コンストラクタ引数と一致しない。

**改善案**:
実際の `MCPServer` コンストラクタを使用した明確な記述に変更:
```python
MCPServer(
    name="github",
    command="npx",
    args=["@modelcontextprotocol/server-github"],
    env_keys=["GITHUB_TOKEN"],
    enabled=True,
    tools=["vscode", "claude", "cursor"],
)
```

---

### 7. 🟢 `_convert_mcp_to_opencode()` の配置場所

**問題**:
計画書は変換関数の配置場所を明記していない。

**改善案**:
既存パターンに従い、`opencode.py` のモジュールレベル関数として配置。`mcp.py` の `_mcp_get_standard()` や `openclaw.py` の `export_mcp()` と同様のパターン。

---

## 改善案サマリー

| # | 優先度 | 指摘 | 対応方針 |
|---|--------|------|----------|
| 1 | 🔴 | skills.paths と instructions の取扱い | `skills.paths` 採用時に instructions からの SKILL.md 追加を削除し、計画書に明記 |
| 2 | 🔴 | `tools` フィールドの無視 | フィルタリング追加、または仕様明文化 |
| 3 | 🔴 | `args` なし時の挙動 | 計画書に前提条件を注記 |
| 4 | 🟡 | 既存ファイル上書き | 計画書に動作を明記 |
| 5 | 🟡 | テストカバレッジ不足 | 5 シナリオを追加 |
| 6 | 🟡 | BDD 入力データ簡略 | 実際のコンストラクタ引数に修正 |
| 7 | 🟢 | 関数配置場所 | `opencode.py` モジュールレベルと明記 |

---

## 備考

- 既存の `_mcp_get_standard()` (mcp.py L156-177) と `_convert_mcp_to_opencode()` の変換ロジックは基本同一。`export_mcp()` (openclaw.py L43-73) も同様。コードの重複を防ぐため、将来的には共通の変換ユーティリティを検討すべき
- opencode.json の `$schema` キーは計画書で言及されていないが、既存コードで設定されているため、変更不要
- 検証方法の手動検証コマンドに `ai-adapter skill add` があるが、実際の CLI は `ai-adapter skill add <path>` 形式であるため、コマンド例を修正すべき
