# OpenCode エージェント YAML フォーマット不整合 改善 実装計画

## 概要

OpenCode 起動時に `.agent.md` ファイルの `tools` フィールドが配列形式 (`tools: [execute, read]`) だとスキーマエラーになる問題を修正する。  
`ai-adapter agent get` / `agent get-all` の出力時および `opencode alias` 実行時にフォーマットを検証・変換する機能を追加する。

## 現状分析

- `~/.ai-adapter/agents/`: 14 ファイル（すべて正しいオブジェクト形式）
- `.opencode/agents/`: 14 ファイル（すべて正しいオブジェクト形式）
- `.github/agents/`: 未作成（このプロジェクトでは未使用）
- **問題**: 指示書によると他のプロジェクトで 2 ファイル (planner, qa) が配列形式になっており、エラーが発生
- **根本原因**: エージェントファイル生成元の混在（手動/テンプレート/コード生成）と、出力時のフォーマット検証欠如

## アーキテクチャ上の注意点（Plan Architect レビュー反映）

### 1. shutil.copy2() の置き換え
現在の `agent_get`/`get-all` は `shutil.copy2()` で単純コピーしている。
`.agent.md` ファイルに限り、**read-modify-write** に置き換える。
非 `.agent.md` ファイル（例：`.md`, 拡張子なし）は変換対象外とし、既存のコピー動作を維持する。

### 2. 共通ユーティリティは新規 `agent_format.py` に配置
`src/ai_adapter/agent_format.py` を作成し、以下の責務を集約:
- YAML frontmatter のパースと変換
- tools フィールドのフォーマット変換
- ファイル単位 / ディレクトリ単位の検証と修復

`_parse_frontmatter()` を `agent.py` から `agent_format.py` に移動し、`agent.py` と `cli.py` は `agent_format.py` からインポートする。
これにより **循環インポートを防止** し、責務を明確に分離する。

### 3. convert_tools_to_object は tuple[dict, bool] を返す
戻り値に「変換が発生したか」のフラグを含める:
```python
def convert_tools_to_object(tools_value: Any) -> tuple[dict[str, bool], bool]:
    """Returns (converted_dict, was_modified)."""
    if isinstance(tools_value, list):
        return {item: True for item in tools_value if isinstance(item, str)}, True
    if isinstance(tools_value, dict):
        return tools_value, False
    return {}, False  # None, other types → no modification
```
呼び出し元は `was_modified` でファイル書き戻しと警告出力の要否を判断する。

### 4. YAML 再シリアライズ戦略（コメント保持）
frontmatter の変換関数は **frontmatter 文字列全体** を受け取り、正規表現で置換する:
```python
def _convert_tools_in_frontmatter(frontmatter_text: str) -> tuple[str, bool]:
```
- `tools: [...]` の行を検出し、オブジェクト形式のブロックに置換
- これにより YAML のコメントやレイアウトを保持
- `#` を含む行はインラインコメントの可能性があるためスキップ

### 5. 警告メッセージ統一
`click.echo(msg, err=True)` で stderr に出力する。

## タスク一覧（BDD）

---

### Task 1: agent_get / agent_get_all 出力時に tools フィールドを自動変換

**対象ファイル**: `src/ai_adapter/agent.py`, `src/ai_adapter/agent_format.py`（新規）

**期待する振る舞い**:

| # | シナリオ | 入力 | 期待する出力 |
|---|---------|------|------------|
| 1-1 | 正常系: オブジェクト形式の tools はそのまま | `tools:\n  execute: true\n  read: true` | 変換なしで出力（copy2 のまま） |
| 1-2 | 変換: 配列形式の tools をオブジェクト形式に変換 | `tools: [execute, read, agent]` | `tools:\n  execute: true\n  read: true\n  agent: true` に変換 |
| 1-3 | 変換: 空の tools 配列 | `tools: []` | `tools: {}` に変換 |
| 1-4 | 変換: 不正フォーマット（文字列など） | `tools: "invalid"` | 警告を stderr に出力し、元のまま出力 |
| 1-5 | 統合: `agent get` で変換が適用される | `ai-adapter agent get planner` | .github/agents/planner.agent.md の tools がオブジェクト形式に変換されている |
| 1-6 | 統合: `agent get-all` で全ファイル変換 | `ai-adapter agent get-all` | 出力先の全 .agent.md ファイルの tools がオブジェクト形式に変換されている |
| 1-7 | 警告: 変換した場合にユーザに通知 | 配列形式のファイルがあった場合 | stderr に `Warning: converted tools format in <file>` と表示 (click.echo(msg, err=True)) |
| 1-8 | ガード: 非 .agent.md ファイルは変換しない | `.md` ファイル / 拡張子なしファイル | 既存の copy2 動作を維持、変換処理をスキップ |
| 1-9 | ガード: .agent.md で frontmatter に tools がない場合 | tools 未定義 | そのまま出力、変換不要 |
| 1-10 | コメント保持: YAML コメントが消えない | `# comment` 付き frontmatter | テキスト置換によりコメントを保持 |

**実装方針**:
1. `agent_format.py` を新規作成（`_parse_frontmatter` を移動元、新関数を追加）
2. `agent_get()` と `agent_get_all()` で、`.agent.md` ファイルにのみ read-modify-write を適用
3. 非 `.agent.md` ファイルは既存の `shutil.copy2()` をそのまま使用
4. `click.echo(msg, err=True)` で警告を stderr に統一

---

### Task 2: opencode alias 実行時にスキーマ検証を追加

**対象ファイル**: `src/ai_adapter/opencode.py`, `src/ai_adapter/agent_format.py`

**期待する振る舞い**:

| # | シナリオ | 入力状態 | 期待する出力 |
|---|---------|---------|------------|
| 2-1 | 正常系: 全ファイルが正しい形式 | `.github/agents/*.agent.md` がすべてオブジェクト形式 | 通常通りシンボリックリンク作成 |
| 2-2 | 警告: 不正フォーマット検出 | 1 ファイル以上が配列形式 | ファイルパス一覧と修復確認プロンプトを表示 |
| 2-3 | 修復: ユーザー承諾後 | `y` を入力 | 元ファイル (.github/agents/) を修正してからリンク作成 |
| 2-4 | 中断: ユーザー拒否後 | `n` を入力 | エラー終了（リンク作成せず） |
| 2-5 | エッジケース: .github/agents/ が空 | エージェントファイルなし | 警告なしでリンク作成 |
| 2-6 | エッジケース: .github/agents/ が存在しない | ディレクトリなし | エラー表示（既存動作） |
| 2-7 | エッジケース: .github/agents/ に .agent.md 以外しかない | `.md` ファイルのみ | 警告なしでリンク作成（対象外のため） |

**実装方針**:
1. `agent_format.py` に実装済みの `batch_validate_and_fix()` を呼び出す
2. `opencode alias` の symlink 作成前に `.github/agents/` の存在確認と検証を追加
3. 問題がある場合、`click.confirm()` でユーザに修復確認
4. 承諾時は `convert_agent_file()` で元ファイルを修正
5. 拒否時は `click.ClickException` でエラー終了

---

### Task 3: agent add / add-rec でもフォーマット保証

**対象ファイル**: `src/ai_adapter/agent.py`, `src/ai_adapter/agent_format.py`

**期待する振る舞い**:

| # | シナリオ | 入力 | 期待する出力 |
|---|---------|------|------------|
| 3-1 | 変換: agent add で .agent.md を追加時に変換 | 配列形式の .agent.md | `~/.ai-adapter/agents/` にオブジェクト形式で保存 |
| 3-2 | 変換: agent add-rec で全 .agent.md を変換 | 配列形式を含むディレクトリ | 全コピー先ファイルが正しい形式に変換されている |
| 3-3 | オプトアウト: --no-convert | `--no-convert` フラグ | 変換せずに元の形式のままコピー |

**実装方針**:
1. `agent_add()` の `shutil.copy2()` 後に変換処理を追加
2. `agent_add_rec()` でも同様の処理を追加
3. `--no-convert` オプションで変換をスキップ可能にする

---

### Task 4: opencode validate サブコマンド（CI 向け）

**対象ファイル**: `src/ai_adapter/opencode.py`, `src/ai_adapter/agent_format.py`

**期待する振る舞い**:

| # | シナリオ | 入力 | 期待する出力 |
|---|---------|------|------------|
| 4-1 | 正常系: 全ファイルが正しい形式 | `.opencode/agents/*.agent.md` | `All agent files are valid.` と exit code 0 |
| 4-2 | 異常系: 不正フォーマット検出 | 配列形式のファイルあり | ファイル一覧と exit code 1 |
| 4-3 | 修復オプション: --fix | `--fix` フラグ付き | 自動修復してから結果表示 |
| 4-4 | スキップ: --project-dir | 指定ディレクトリ | 指定先の agent files を検証 |
| 4-5 | CI 向け: --quiet | `--quiet` フラグ | 出力最小限、exit code のみ |

**実装方針**:
1. `opencode validate` サブコマンドを追加（Task 2 と並行実装可能）
2. `batch_validate_and_fix()` を再利用
3. `--fix` / `--quiet` / `--project-dir` オプションを実装

---

## 共通ユーティリティ関数の設計（`agent_format.py` 新規作成）

### 移動元関数

#### `parse_frontmatter(path: Path) -> dict`（agent.py から移動）
- 既存の `_parse_frontmatter()` をそのまま移動
- 関数名から `_` を外し、公開関数として定義
- `agent.py` は `from ai_adapter.agent_format import parse_frontmatter as _parse_frontmatter` でインポート
- `cli.py` も同様にインポート元を変更

### 新規関数

#### `convert_tools_to_object(tools_value) -> tuple[dict, bool]`
- 常に `(dict, bool)` を返す
- 配列形式 `["execute", "read"]` → `({"execute": true, "read": true}, True)`
- オブジェクト形式 `{"execute": true}` → `({"execute": true}, False)`
- `None` / 未定義 → `({}, False)`
- その他の型 → `({}, False)`

#### `_convert_tools_in_frontmatter(frontmatter_text: str) -> tuple[str, bool]`
- frontmatter 文字列全体を受け取り、`tools: [...]` パターンを検出
- 正規表現で検出し、オブジェクト形式ブロックに置換
- 変更があれば `(modified_text, True)`、なければ `(original_text, False)`

#### `convert_agent_file(path: Path) -> bool`
- `.agent.md` ファイルの frontmatter を読み込み tools 変換
- 流れ: ファイル読み込み → frontmatter 抽出 → `_convert_tools_in_frontmatter()` → 変更時のみ書き戻し
- 変換したら True、不要なら False、エラーなら例外

#### `validate_agent_file(path: Path) -> list[str]`
- `.agent.md` ファイルの frontmatter をパースし、tools の型をチェック
- 配列形式なら `["tools field is array format (expected object)"]` を返す
- 正常なら空リスト

#### `batch_validate_and_fix(directory: Path, fix: bool) -> list[str]`
- ディレクトリ内全 `.agent.md` に対して検証
- `fix=True` なら `convert_agent_file()` で修復も実行
- 問題リストを返す（空リスト = 全正常）

## テスト計画

### 新規テストファイル
- `tests/test_agent_format.py` — ユーティリティ関数のユニットテスト

### 既存テストへの追加
- `tests/test_agent.py` — agent get/get-all/add/add-rec で変換が適用される統合テスト
- `tests/test_opencode.py` — opencode validate / alias 検証のテスト

### テストケース一覧

| テスト | 内容 | 対象ファイル |
|-------|------|------------|
| `test_convert_tools_array_to_object` | 配列形式 → オブジェクト形式変換 | test_agent_format.py |
| `test_convert_tools_object_preserved` | オブジェクト形式はそのまま | test_agent_format.py |
| `test_convert_tools_empty_array` | 空配列 `[]` → `{}` | test_agent_format.py |
| `test_convert_tools_none` | None → `{}` | test_agent_format.py |
| `test_convert_tools_invalid_type` | 文字列/数値 → `{}` | test_agent_format.py |
| `test_convert_tools_was_modified_flag` | 変換時 True、非変換時 False | test_agent_format.py |
| `test_convert_tools_in_frontmatter_basic` | frontmatter 内の配列置換 | test_agent_format.py |
| `test_convert_tools_in_frontmatter_comment` | YAML コメントが保持される | test_agent_format.py |
| `test_convert_tools_in_frontmatter_no_change` | 既にオブジェクト形式 = 変更なし | test_agent_format.py |
| `test_convert_agent_file_array_to_object` | ファイル単位の変換 | test_agent_format.py |
| `test_convert_agent_file_not_agent_md` | 非 .agent.md はスキップ | test_agent_format.py |
| `test_convert_agent_file_no_frontmatter` | frontmatter なしはスキップ | test_agent_format.py |
| `test_validate_agent_file_valid` | 正常ファイルの検証 | test_agent_format.py |
| `test_validate_agent_file_invalid` | 不正ファイルの検出 | test_agent_format.py |
| `test_validate_agent_file_empty_dir` | 空ディレクトリの検証 | test_agent_format.py |
| `test_batch_validate_and_fix` | バッチ検証+修復 | test_agent_format.py |
| `test_parse_frontmatter_moved` | agent_format からパースできる | test_agent_format.py |
| `test_agent_get_converts_tools` | agent get で変換適用 | test_agent.py |
| `test_agent_get_all_converts_tools` | agent get-all で変換適用 | test_agent.py |
| `test_agent_get_non_agent_md_unchanged` | 非 .agent.md は変換しない | test_agent.py |
| `test_agent_add_converts_tools` | agent add で変換適用 | test_agent.py |
| `test_agent_add_no_convert_flag` | --no-convert でスキップ | test_agent.py |
| `test_opencode_validate_valid` | 全ファイル正常 | test_opencode.py |
| `test_opencode_validate_invalid` | 不正ファイル検出 | test_opencode.py |
| `test_opencode_validate_fix` | --fix で自動修復 | test_opencode.py |
| `test_opencode_validate_quiet` | --quiet モード | test_opencode.py |
| `test_opencode_alias_validates_and_fixes` | alias 実行時に検証+修復 | test_opencode.py |
| `test_opencode_alias_no_github_agents` | .github/agents/ なし | test_opencode.py |

## 実装順序

```
Task 1 ──→ Task 2 ──→ Task 3 ──→ Task 4
  (agent.py     (opencode.py   (agent.py     (opencode.py
   +             +              +              +
   agent_format)  agent_format)  agent_format)  agent_format)
```

### フェーズ 1（優先度高）
1. **Task 1**: `agent_format.py` 新規作成
   - `parse_frontmatter()` を `agent.py` から移動
   - `convert_tools_to_object()` 実装
   - `_convert_tools_in_frontmatter()` 実装
   - `convert_agent_file()` 実装
   - `validate_agent_file()` 実装
   - `batch_validate_and_fix()` 実装
   - テスト: `test_agent_format.py`
2. **Task 1**: `agent.py` の agent_get / agent_get_all に変換ロジック追加（import 差し替え + read-modify-write）
3. **Task 2**: `opencode.py` の alias に検証ロジック追加（`batch_validate_and_fix()` 呼び出し）
4. **Task 4**: `opencode validate` サブコマンド追加（Task 2 と並行実装可能）

### フェーズ 2（優先度中）
5. **Task 3**: agent add / add-rec に変換ロジック追加 + `--no-convert` オプション

## リスクと注意点

1. **YAML コメント消失**: `tools:` の行末インラインコメント（`tools: # comment`）は消失する可能性あり → `#` を含む行はスキップするガードを入れる
2. **frontmatter の YAML がマルチドキュメント**: 現状の `parse_frontmatter()` は最初の `---...---` のみパース。問題ない
3. **opencode alias 既存フローとの整合**: symlink 作成前に `.github/agents/` ディレクトリの存在確認が必要（現状は `.github/` の存在確認のみ）
4. **Windows 対応**: `os.symlink` は Windows で制約あり → 現状コードが Darwin 前提。本タスクでは対応しない
5. **循環インポート**: `parse_frontmatter()` を `agent_format.py` に移動することで防止済み
6. **変換判定**: `convert_tools_to_object()` の `tuple[dict, bool]` 戻り値で「変換発生」を明確に判定可能

---

**作成日**: 2026-07-25  
**ステータス**: 修正版 v2（レビュー済み）  
**優先度**: High  
**カテゴリ**: ai-adapter / opencode / quality
