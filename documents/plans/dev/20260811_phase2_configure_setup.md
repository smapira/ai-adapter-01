# フェーズ 2 実装計画: Configure（`ai-adapter setup` + プロファイル定義 + Pack + skill install）

- 日付: 2026-08-11
- 作成者: Product Manager
- 状態: ドラフト（Plan Architect レビュー待ち）
- 上位計画: `documents/plans/dev/20260811_ai_adapter_grand_design.md`（承認済み）
- 対象バージョン: v0.31 → v0.40
- 制約: ドキュメント作成フェーズ（本計画は実装前の設計ドキュメント。実装は別途 Implementer 依頼）

---

## 1. 目的

「管理ツール」から「便利なツール」への転換。ユーザーが「設定方法を知らなくても」、プロファイル（プリセット）を選ぶだけで Skills / MCP / Agents / Commands の推奨構成を一括導入できるようにする。

---

## 2. アーキテクチャ方針

### 2.1 新コマンド: `ai-adapter setup <profile>`

```
setup
 ├─ profiles/ ディレクトリから YAML 定義を読み込み
 ├─ 推奨構成を提示（--dry-run でプレビュー）
 └─ 既存 add 系コマンドを呼び出して一括導入
```

### 2.2 プロファイル定義の場所

- 標準プロファイル: `src/ai_adapter/profiles/`（パッケージ同梱）
- ユーザープロファイル: `~/.ai-adapter/profiles/`（ユーザーが上書き・追加）
- 解決優先順: ユーザープロファイル > 標準プロファイル

### 2.3 Pack との関係

- Pack は複数プロファイルの組み合わせ（`pack install nextjs-pro` → 複数 profile を順次適用）
- フェーズ 2 では**ローカル Pack** のみ（パブリック Registry はフェーズ 4-4）

---

## 3. BDD タスク分解

### タスク 2-1: `ai-adapter setup <profile>`

**期待する振る舞い**:
- 入力: `ai-adapter setup web-development`
- 応答: プロファイル定義を読み込み、以下の流れで実行
  1. 推奨構成のサマリー表示（Skills: N / MCP: N / Agents: N / Commands: N）
  2. 各項目を既存 add 系コマンドで登録
  3. 適用結果の要約表示
- 入力: `ai-adapter setup 存在しないプロファイル`
- 応答: 「Profile 'xxx' not found. Available profiles: web-development, python, ...」+ 利用可能プロファイル一覧

**受け入れ条件**:
- AC1: プロファイル未指定時は利用可能プロファイル一覧を表示
- AC2: **名前→ソース解決ステップを必須とする**。`skill add` / `agent add` / `command add` は**パス引数必須**（`click.Path(exists=True)`）のため、プロファイルの「名前」参照は以下の解決順でパスに変換する（Plan Architect 指摘反映）:
  1. 導入済み（`~/.ai-adapter/skills/<name>/` が存在）→ そのパスをそのまま利用
  2. 未導入 → `skill install <name>`（2-5）で取得後に利用
  3. 同梱（パッケージ内 `src/ai_adapter/bundled/` に標準スキルがある場合）→ 同梱パスを利用
  4. 解決不能 → エラーメッセージ + プロファイル適用をスキップ
- AC3: 各項目の登録成功/失敗を個別に表示（失敗しても続行）
- AC4: 対話モードでは登録前に確認プロンプト（`--yes` でスキップ可能）

**データ（仕様例）**:
- `web-development` プロファイル:
  ```yaml
  name: web-development
  description: Web 開発向け推奨構成
  skills: [frontend, react, typescript, testing]
  mcp:
    - name: github
      command: npx
      args: ["@modelcontextprotocol/server-github"]
    - name: playwright
      command: npx
      args: ["@modelcontextprotocol/server-playwright"]
  agents: [code-reviewer, frontend-engineer]
  commands: []
  ```

---

### タスク 2-2: `setup` のプロファイル定義形式

**期待する振る舞い**:
- 入力: `src/ai_adapter/profiles/*.yaml`（標準）または `~/.ai-adapter/profiles/*.yaml`（ユーザー）
- 応答: YAML をパースして `Profile` データ構造に変換。不正な YAML は明確なエラーメッセージ

**受け入れ条件**:
- AC1: `Profile` データクラスを定義（`src/ai_adapter/models.py` または新設 `src/ai_adapter/profiles.py`）
- AC2: YAML スキーマの検証（未知キー・必須キー不足で警告/エラー）
- AC3: ユーザープロファイルが標準プロファイルを上書き（同名の場合）

**データ（仕様例）**:
```python
@dataclass
class Profile:
    name: str
    description: str
    skills: list[str]
    mcp: list[MCPServerSpec]
    agents: list[str]
    commands: list[str]
```

---

### タスク 2-3: `setup --dry-run`

**期待する振る舞い**:
- 入力: `ai-adapter setup web-development --dry-run`
- 応答: 適用される内容のプレビュー（何が登録されるか・ソースはどこか）
  ```
  Profile: web-development
  Would add:
    Skills: frontend, react, typescript, testing (4)
    MCP: github, playwright (2)
    Agents: code-reviewer, frontend-engineer (2)
    Commands: (0)
  ```
- 入力: `--dry-run` 後の状態確認
- 応答: **実際の変更は行われていない**（`~/.ai-adapter/` の内容が不変）

**受け入れ条件**:
- AC1: `--dry-run` は一切の変更を加えない（テストで担保）
- AC2: 登録済みの項目は「Already registered」として明示

---

### タスク 2-4: Pack コンセプト導入（ローカル）

**期待する振る舞い**:
- 入力: `ai-adapter pack install nextjs-pro`
- 応答: Pack 定義（複数プロファイルの組み合わせ）を読み込み、順次 `setup` を適用
- 入力: `ai-adapter pack list`
- 応答: 利用可能な Pack 一覧
- 入力: `ai-adapter pack install 存在しないPack`
- 応答: 該当なしメッセージ + 一覧

**受け入れ条件**:
- AC1: Pack は `src/ai_adapter/packs/` または `~/.ai-adapter/packs/` の YAML で定義
- AC2: Pack 適用は `setup` の逐次呼び出しで実装（新規ロジック最小化）
- AC3: 適用中のプロファイル名と進捗を表示

**データ（仕様例）**:
```yaml
# nextjs-pro.pack.yaml
name: nextjs-pro
description: Next.js プロダクション開発向け
profiles: [web-development, typescript-strict, testing]
```

---

### タスク 2-5: `skill install <name>`（ローカル/リポジトリ）

**期待する振る舞い**:
- 入力: `ai-adapter skill install database-schema`
- 応答: ローカルキャッシュまたは指定ソースから Skill を取得し `~/.ai-adapter/skills/` に導入
- 入力: `ai-adapter skill install <name> --source github:user/repo`
- 応答: GitHub リポジトリから取得（パブリックレジストリはフェーズ 4-3）
- 入力: `ai-adapter skill install 存在しないスキル`
- 応答: 該当なしメッセージ

**受け入れ条件**:
- AC1: ソースは「ローカルキャッシュ」または「GitHub リポジトリ」に限定（Registry は 4-3）
- AC2: 導入前に frontmatter を検証（name/description 必須・`plugin validate` 相当のチェック）
- AC3: 既存同名 Skill がある場合は上書き確認

**データ（仕様例）**:
- `skill install database-schema --source github:example/ai-skills` → `~/.ai-adapter/skills/database-schema/` に導入

---

## 4. データ構造設計

### `Profile` / `Pack`（`src/ai_adapter/profiles.py` に定義）

```python
@dataclass
class MCPServerSpec:
    name: str
    command: str
    args: list[str]


@dataclass
class Profile:
    name: str
    description: str
    skills: list[str]
    mcp: list[MCPServerSpec]
    agents: list[str]
    commands: list[str]


@dataclass
class Pack:
    name: str
    description: str
    profiles: list[str]
```

### ディレクトリ構成

```
src/ai_adapter/
├── profiles.py          # Profile/Pack データクラス + YAML ロード + 名前→ソース解決
├── profiles/            # 標準プロファイル（YAML）
│   ├── web-development.yaml
│   ├── python.yaml
│   └── ...
├── bundled/             # 同梱スキル（名前解決ステップ 3 のソース。空でも可）
├── commands/setup.py    # setup コマンド
└── commands/pack.py     # pack コマンド
```

### 名前→ソース解決（2-1 AC2 の実装）

- `profiles.py` に `resolve_skill_source(name: str) -> Path | None` を実装
- 解決順: 導入済み（`~/.ai-adapter/skills/<name>/`）→ `skill install`（2-5）→ 同梱（`src/ai_adapter/bundled/<name>/`）
- 解決失敗時はエラーとして AC3 の「個別失敗表示」にフォールバック

---

## 5. テスト計画（フェーズ 2）

| タスク | テストファイル | 種別 | 追加数 | 内容 |
|--------|--------------|------|--------|------|
| 2-1/2-2 | `tests/test_setup.py`（新設） | Integration | 15 | プロファイル適用（tmp_path 使用・`~/.ai-adapter/` 作成） |
| 2-2 | `tests/test_profiles.py`（新設） | Unit | 10 | YAML パース・スキーマ検証・上書き優先順 |
| 2-3 | `tests/test_setup.py` | Unit | 5 | **`--dry-run` が変更を加えないこと** |
| 2-4 | `tests/test_pack.py`（新設） | Integration | 5 | Pack 適用・一覧・該当なし |
| 2-5 | `tests/test_skill.py`（拡張） | Unit | 5 | skill install のソース解決・frontmatter 検証 |

**実行ゲート**: `scripts/run_tests.sh` で全テスト実行。

---

## 6. 既存コード再利用マップ（フェーズ 2）

| タスク | 再利用資産 | 用途 |
|--------|-----------|------|
| 2-1 | `skill.py` / `mcp.py` / `agent.py` / `command.py` の add 系 | プロファイル適用時に既存 add を呼び出す（**パス引数は名前→ソース解決で生成**） |
| 2-2 | `models.py` の既存データクラスパターン | Profile/Pack データクラス設計 |
| 2-3 | `agent_plugins.py` の `ValidationIssue`（severity 拡張済み・フェーズ 1） | `--dry-run` の検証表示 |
| 2-5 | `agent_plugins.py` の `validate_skill_dir`（L485）・`agent_format.py` の `parse_frontmatter`（L21） | 導入前の frontmatter 検証 |

---

## 7. リスクと対策

| リスク | 影響 | 対策 |
|--------|------|------|
| プロファイル定義の過剰設計 | メンテコスト増 | 標準プロファイルは 5 個以内に限定（web-development / python / typescript / testing / data） |
| 既存 add との二重登録 | 設定の重複 | `setup` は登録前に対象の存在チェック（Already registered 表示） |
| GitHub ソースからの取得失敗 | 導入失敗 | `--source` 指定時は git clone の失敗を捕捉し明確なエラー表示 |

---

## 8. 実装順序

1. 2-2 プロファイル定義形式（データ構造の土台）
2. 2-1 `setup <profile>`（適用ロジック）
3. 2-3 `--dry-run`（プレビュー）
4. 2-5 `skill install`（ソース解決）
5. 2-4 Pack（組み合わせ）

---

## 9. 次のアクション

1. [ ] Plan Architect レビュー（本計画の妥当性検証）
2. [ ] 承認後、Implementer に実装依頼
3. [ ] Reviewer 検収 → QA チェック
