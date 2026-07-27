# レビュー: MCP OpenClaw Export 実装計画

## 優先度
🔴 高

## 対象
- 計画書: `documents/plans/dev/20260727_mcp_openclaw_export.md`
- 関連ファイル: `src/ai_adapter/mcp.py`, `tests/test_mcp.py`, `src/ai_adapter/models.py`

## 指摘事項

Plan Architect としてレビューした結果、**複数の修正が必要**と判断します。
特に出力先パスの曖昧さとファイル名の設計判断の欠落が重大です。

以下、発見項目を優先度順に列挙します。

---

### 🔴 [HIGH-1] 出力先パスの動作が曖昧

**箇所**: Task 2 — 出力先のデフォルト動作

**問題**:
```
出力先: `--path` 指定がなければ `~/.openclaw/openclaw.json.servers` またはカレントディレクトリの `.mcp.json`
```

`または`（or）で2つのデフォルト値を示しているが、どちらが優先されるのか、どういう条件で変わるのかが不明。以下の3通りの解釈が可能:

1. OpenClaw がインストールされていれば `~/.openclaw/openclaw.json.servers`、なければカレントディレクトリの `.mcp.json`
2. 常に `~/.openclaw/openclaw.json.servers` をデフォルトとする
3. 常にカレントディレクトリの `.mcp.json` をデフォルトとする

**改善案**:
- 条件分岐のロジックを明文化する。例: 「`~/.openclaw/` が存在すれば `~/.openclaw/openclaw.json.servers`、存在しなければカレントディレクトリの `openclaw.json.servers`」
- または、`--tool openclaw` では `--path` を必須にしてデフォルトを廃止する

---

### 🔴 [HIGH-2] 出力ファイル名 `openclaw.json.servers` の根拠不明

**箇所**: Task 2 — 出力先ファイル名

**問題**:
OpenClaw の設定ファイルは `openclaw.json` であり、`openclaw.json.servers` というファイルは OpenClaw の公式ドキュメントや設定構造に存在しない。以下の懸念がある:

- `.servers` サフィックスは ai-adapter 独自の命名か？
- OpenClaw がこのファイルを自動読み込みする仕組みはない
- 利用者はこのファイルを手動で `openclaw.json` にマージする必要があるのか？
- 既存の `~/.openclaw/openclaw.json` との関係は？

**改善案**:
- 出力ファイル名の設計意図を明記する
- 以下のいずれかに決定すべき:
  - **A**: `openclaw.json.servers` として出力し、利用者が手動マージ（その場合、マージ手順を README や --help に記載）
  - **B**: `mcp.servers` セクションのみを含む partial JSON として出力（include 機構があれば）
  - **C**: `--tool standard` と同様、`openclaw.json` に直接書き込む（既存設定とのマージ戦略が必要）

---

### 🔴 [HIGH-3] 既存サーバーとのマージ戦略が未定義

**箇所**: 計画書全体（特に Task 2）

**問題**:
ユーザーが既に `~/.openclaw/openclaw.json` に MCP サーバー設定を持っている場合の動作が定義されていない。
- ai-adapter の出力で既存のサーバーを完全上書きするのか？
- サーバー単位でマージするのか？
- 既存設定は保持し、ai-adapter のサーバーのみ追加するのか？

調査レポートでも実値の MCP サーバーが既に存在することが確認されている。

**改善案**:
- マージ戦略を明文化する。推奨: **サーバー名ベースのマージ**（同名は上書き、新規は追加、ai-adapter にない既存サーバーは保持）
- または、Plan の範囲を「新規ファイルとして書き出すのみ、既存ファイルとは干渉しない」と明確に定義する

---

### 🔴 [HIGH-4] `--force` オプションのスコープ未定義

**箇所**: Task 2 — 確認プロンプトの記述

**問題**:
```
出力先にファイルが存在する場合は確認プロンプト（`--force` で上書き）
```
とあるが、以下の点が不明:

- `--force` は `mcp get` 全体のオプションなのか、`--tool openclaw` 限定なのか？
- `--tool standard` でも `--force` が使えるのか？
- 既存の `mcp remove-all` の `--force` と意味が異なる（remove-all → 確認スキップ、get → 上書き許可）
- コードベースの他の `--force` パターン（`agent.py` 等）と一貫性があるか確認されていない

**改善案**:
- `--force` の意味を「出力先ファイルが存在しても上書きを許可する」と定義する
- `mcp get` 全体のオプションとして追加し、`--tool standard` / `--tool openclaw` 両方で機能させる
- `--help` の説明文を `Overwrite output file without confirmation` に統一

---

### 🟡 [MED-1] テスト不足: Scenario 3, 4 が未カバー

**箇所**: Task 3 — テスト一覧

**問題**:
BDD シナリオで定義されているにも関わらず、以下のシナリオに対応するテストがない:

| BDD シナリオ | テスト | 状態 |
|---|---|---|
| Scenario 3: OpenClaw 未インストール時の警告 | なし | ❌ 欠落 |
| Scenario 4: 空の MCP 登録 | なし | ❌ 欠落 |

**改善案**:
以下のテストを追加する:

- `test_export_openclaw_openclaw_not_installed()`: `~/.openclaw/` が存在しない場合の警告表示を検証（--path あり／なし両方）
- `test_export_openclaw_empty_servers()`: `No enabled MCP servers registered.` メッセージと空出力を検証

---

### 🟡 [MED-2] env キー名のバリデーション欠落

**箇所**: Task 1 — `_export_openclaw_mcp()` の振る舞い

**問題**:
調査レポート `20260727_openclaw_env_resolution.md` より、OpenClaw の `${VAR}` プレースホルダは `[A-Z_][A-Z0-9_]*` のパターンにしか対応していない（大文字 + アンダースコア + 数字のみ）。しかし計画書ではこのバリデーションに触れていない。

仮に `env_keys` に `myApiKey` のような小文字・キャメルケースのキーが含まれていると、OpenClaw がロード時にエラーになる。

**改善案**:
- `_export_openclaw_mcp()` 内で env キー名を検証し、`[A-Z_][A-Z0-9_]*` にマッチしないキーは警告を出す
- または、安全側に倒して常に `click.echo("Warning: env key 'myApiKey' may not be valid in OpenClaw format")` と出力する

---

### 🟡 [MED-3] `--path` + `--tool openclaw` 時のファイル名未定義

**箇所**: Task 2 — `--path` との組み合わせ

**問題**:
ユーザーが `ai-adapter mcp get --tool openclaw --path /tmp/out` と指定した場合、以下のファイル名は何になるか未定義:

- `/tmp/out/openclaw.json.servers`？
- `/tmp/out/.mcp.json`？
- `/tmp/out/` がディレクトリかどうかで変わる？

**改善案**:
以下を明記する:
- `--tool openclaw` の場合、`--path` で指定されたディレクトリに `openclaw.json.servers` として出力する
- `--tool standard` の場合、従来通り `.mcp.json` として出力する
- `--path` のヘルプを更新する（現在: "Output directory (default: current directory)" → ツール別のファイル名も記載）

---

### 🟡 [MED-4] `--tool` オプション名の将来衝突リスク

**箇所**: Task 2 — `mcp get` に追加する `--tool`

**問題**:
同じ `mcp` グループ内の `mcp list` が既に `--tool` オプションを持っている（意味: フィルタリングツール名）。`mcp get --tool` は意味が異なる（出力形式指定）。同じオプション名がサブコマンドで異なる意味を持つのは混乱を招く可能性がある。

特に将来的に `mcp list --tool vscode` と `mcp list --tool openclaw` が衝突しうる。

**改善案**:
- 現時点では `mcp list` と `mcp get` は別サブコマンドなので問題は軽微
- ただし、将来の拡張を見越して `--format` または `--export-format` への改名を検討する。`click.Choice(["standard", "openclaw"])` は「出力形式」を選んでいるので `--format` の方が適切

---

### 🟢 [LOW-1] `_export_openclaw_mcp()` の命名: ダブルアンダースコアは過剰

**箇所**: Task 1 — 関数名 `_export_openclaw_mcp()`

**問題**:
モジュールレベルのヘルパー関数にダブルアンダースコア（`__`）を使うと Python の name mangling がトリガーされる。`_export_openclaw_mcp` はクラス内部でなくモジュールレベルなので name mangling は発生しないが、規約的に「強いプライベート」のニュアンスが強すぎる。

コードベース内の他モジュール（`opencode.py` の `_validate_and_fix`、`config.py` の `_find_gitignore_path`）はシングルアンダースコアを使っている。

**改善案**:
`_export_openclaw_mcp()` → `_export_openclaw_mcp()` に変更（シングルアンダースコア）

---

### 🟢 [LOW-2] Scenario 3 のタイトルと動作の不一致

**箇所**: Scenario 3

**問題**:
- タイトル: 「OpenClaw 未インストール時の**エラーメッセージ**」
- 動作: 「警告は出すが**処理は続行**」

エラー（処理中断）と警告（処理継続）は異なる。タイトルと実際の動作が一致していない。

**改善案**:
- タイトルを「OpenClaw 未インストール時の警告表示」に変更
- または、`--path` なしの場合はエラーとして中断する、と明確に定義する

---

### 🟢 [LOW-3] Scenario 1 の出力例に `args` キーの揺れ

**箇所**: Task 1 の振る舞いと Scenario 1 の出力例

**問題**:
Task 1 の振る舞いで「`args` が空の場合はキーごと出力しない」と定義しているが、Scenario 1 の出力例では常に `args` が存在するため、省略動作が確認できない。エッジケースとして空 `args` のサーバー（`playwright` は `args` ありなので問題ないが）をテストデータに含めるべき。

**改善案**:
- Scenario 1 のテストデータに `args` が空のサーバーを1つ追加するか、別のエッジケースとして明示する
- または `args` が空で省略された場合の出力例をコメントで示す

---

## 総評

**判定: ⚠️ 条件付き承認**（上記 HIGH 4項目の解決が必要）

### 良い点
- BDD シナリオが正常系・異常系をカバーしており、テストファーストの設計思想が明確
- タスク分割が適切な粒度（ヘルパー関数 / CLI オプション / テスト）
- 後方互換性への配慮（`--tool standard` のデフォルト維持）がされている
- 事前調査（`20260727_openclaw_env_resolution.md`）に基づいた設計判断が良い
- 出力フォーマットに `enabled` フラグを含めるのは OpenClaw の仕様と合致している

### 修正すべき点
1. **出力先パスとファイル名の設計**が未確定（HIGH-1, HIGH-2, MED-3）
2. **既存ファイルとのマージ戦略**が未定義（HIGH-3）
3. **`--force` のスコープと意味**が未定義（HIGH-4）
4. **テストカバレッジ**にギャップあり（MED-1）
5. **env キー名のバリデーション**が必要（MED-2）
6. **`--tool` というオプション名**は将来衝突リスクあり（MED-4）

これらの修正後、再度レビューを依頼してください。
