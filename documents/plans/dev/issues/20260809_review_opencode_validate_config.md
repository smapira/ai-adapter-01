# Review: opencode validate — opencode.json スキーマ検証機能追加

## 優先度
🔴 高（権限キーの不一致は検証ロジック全体の正しさに直結）

## 対象
- 計画書: `documents/plans/dev/20260809_opencode_validate_config.md`
- 関連ファイル:
  - `src/ai_adapter/providers/opencode.py`
  - `tests/test_opencode.py`
  - `opencode.json`（実際のスキーマ参照）

---

## 指摘事項

### 🔴 1. VALID_PERMISSION_KEYS が実際の opencode.json と一致しない（致命的）

計画書の検証ロジックで定義されている `VALID_PERMISSION_KEYS`:

```python
VALID_PERMISSION_KEYS = {
    "read",
    "edit",
    "glob",
    "grep",
    "list",
    "bash",
    "task",
    "external_directory",
    "todowrite",
    "question",
    "webfetch",
    "websearch",
    "lsp",
    "doom_loop",
    "skill",
}
```

しかし、**実際の `opencode.json` の permission キー**は以下の通り:

```json
"permission": {
    "execute": "ask",
    "read": "ask",
    "edit": "ask",
    "search": "ask",
    "agent": "ask",
    "browser": "ask",
    "web": "ask",
    "todo": "ask"
}
```

また、**`opencode.py` 内の `_DEFAULT_PERMISSION`** は:

```python
_DEFAULT_PERMISSION = {
    "read": "ask",
    "edit": "ask",
    "glob": "ask",
    "grep": "ask",
    "list": "ask",
    "bash": "ask",
    "task": "ask",
    "webfetch": "ask",
    "websearch": "ask",
    "todowrite": "ask",
}
```

三者がすべて異なる。計画書の `VALID_PERMISSION_KEYS` に従って検証すると、**実在する有効な `opencode.json` が不正判定される**。

#### 改善案

- `_DEFAULT_PERMISSION` のキーを唯一の正規ソースとして使い、計画書の `VALID_PERMISSION_KEYS` を削除する
- もしくは、opencode の公式スキーマ（`https://opencode.ai/config.json`）から動的に取得する
- 最低限、`_DEFAULT_PERMISSION` と実際の `opencode.json` を照合して、両方のキーを許可リストに含める

---

### 🔴 2. BDD と実装コードの権限キーリストが不一致

計画書の BDD Task 3.2 には:

> `permission` のキーは有効な値か？（read, edit, glob, grep, list, bash, task, webfetch, websearch, todowrite）

と10キーが記載されているが、実装コードの `VALID_PERMISSION_KEYS` は15キー（`external_directory`, `question`, `lsp`, `doom_loop`, `skill` を追加）。BDD とコードが乖離しており、レビューの前提が崩れる。

#### 改善案

BDD の検証内容テーブルに許可キーの完全リストを記載するか、「`_DEFAULT_PERMISSION` のキーおよび opencode スキーマで定義されるキー」のように抽象化する。

---

### 🟡 3. MCP 検証で `enabled` / `environment` フィールドが未検証

`_mcp_server_to_opencode()` は以下のフィールドを生成する:

```python
entry = {
    "type": "local",
    "command": [server.command] + server.args,
    "enabled": server.enabled,  # ← 検証対象外
}
if server.env_keys:
    entry["environment"] = {...}  # ← 検証対象外
```

計画書の検証ロジックは `type` と `command` のみチェックしているため、手動で `opencode.json` を編集した際に `enabled` の型ミス（文字列入れなど）や `environment` の構造エラーを見逃す。

#### 改善案

```python
if "enabled" in server and not isinstance(server["enabled"], bool):
    errors.append(f"mcp.{name}: 'enabled' must be a boolean")
if "environment" in server:
    if not isinstance(server["environment"], dict):
        errors.append(f"mcp.{name}: 'environment' must be an object")
    elif not all(isinstance(v, str) for v in server["environment"].values()):
        errors.append(f"mcp.{name}: 'environment' values must be strings")
```

---

### 🟡 4. 実装コードに `--config` オプションが BDD に存在しない

実装方針に:

> 新しいオプション `--config` で制御可能

とあるが、BDD のシナリオテーブル（Task 1〜5）に `--config` オプションの言及がない。Task 4 の「パス存在確認（オプション）」と混同している可能性がある。

#### 改善案

`--config` オプションの BDD を追加する、もしくは実装方針から削除して Task 4 の説明に統合する。

---

### 🟡 5. 権限値の検証が未実装

`_DEFAULT_PERMISSION` の値はすべて `"ask"` だが、計画書の検証ロジックではキーの存在のみチェックし、**値が `"ask"` かどうかは検証しない**。opencode のスキーマで許可される値の範囲を明示的に定義すべき。

#### 改善案

```python
VALID_PERMISSION_VALUES = {"ask", "allow", "deny"}  # opencode スキーマに準拠
for key, value in data["permission"].items():
    if value not in VALID_PERMISSION_VALUES:
        errors.append(f"permission.{key}: invalid value '{value}'")
```

---

### 🟡 6. テストカバレッジの不足

現在のテスト計画には以下のシナリオが欠落している:

| シナリオ | 重要度 | 理由 |
|---------|--------|------|
| 不正な JSON（構文エラー） | 高 | Task 2.2 のテストがない |
| 無効な permission キー | 高 | 現在の検証ロジックの主要機能 |
| MCP サーバーの `type` が無効 | 中 | "local"/"remote" 以外の値 |
| MCP サーバーの `command` が配列でない | 中 | 型エラーのハンドリング |
| `command` セクションの `template` 欠落 | 中 | 必須フィールドの検証 |
| opencode.json が存在しない場合 | 高 | Task 1.2 のテストがない |
| `--config` オプション（もしあれば） | 中 | オプションの動作確認 |

#### 改善案

上記シナリオを追加テストとして計画に含める。特に「不正な JSON」と「opencode.json 不存在」は最低限必要。

---

### 🟢 7. `batch_validate_and_fix` パターンとの整合性

既存の `batch_validate_and_fix` は `list[str]` を返し、呼び出し元で `click.echo` + `SystemExit(1)` するパターン。計画書の `_validate_opencode_config()` も同様に `list[str]` を返す設計だが、**`opencode_validate()` 内での統合方法**が明示されていない。

#### 改善案

`opencode_validate()` 内の統合伪代码を計画書に追記する:

```python
# 既存: .agent.md 検証
errors = batch_validate_and_fix(agents_dir, fix=fix)

# 追加: opencode.json 検証
config_path = base_dir / "opencode.json"
if config_path.exists():
    errors.extend(_validate_opencode_config(config_path))

if errors:
    ...  # 既存パターンに従い出力 + exit 1
```

---

### 🟢 8. `enabled` フィールドの既存テストとの整合

`test_opencode_install_with_mcp_disabled` は `enabled: false` を検証するが、計画書の検証ロジックには `enabled` の型チェックがない。テストを追加する場合、`enabled` が boolean であることを保証する検証を追加すべき。

---

## 総合所見

計画書の骨子は良好だが、**権限キーの不一致（🔴1, 🔴2）は修正必須**。このまま実装すると、ai-adapter 自身が生成した `opencode.json` すら不正判定される。実装に進む前に `_DEFAULT_PERMISSION` と実際の `opencode.json` を照合し、検証ロジックの正規ソースを一本化することを推奨する。

## 備考
- 作成日: 2026-08-09
- レビュアー: Plan Architect
