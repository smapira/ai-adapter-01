# フェーズ 3 実装計画: Maintain（`ai-adapter doctor` フル + `--fix` + `optimize` + バージョン追跡）

- 日付: 2026-08-11
- 作成者: Product Manager
- 状態: ドラフト（Plan Architect レビュー待ち）
- 上位計画: `documents/plans/dev/20260811_ai_adapter_grand_design.md`（承認済み）
- 対象バージョン: v0.41 → v0.50
- 制約: ドキュメント作成フェーズ（本計画は実装前の設計ドキュメント。実装は別途 Implementer 依頼）

---

## 1. 目的

環境を継続的に改善する「AI 環境の Dependabot」を実現する。検出した問題の**自動修正**（`doctor --fix`）と、設定の**最適化提案・適用**（`optimize` / `optimize --apply`）、および **バージョン追跡** を提供する。

**方針（グランドデザイン 🔴1 反映）**: `doctor` / `optimize` のローカル実行は **Free**（CLI 機能はすべて無料）。クラウド連携のみが有料。本計画は CLI ローカル実行のみを対象とし、クラウド連携はフェーズ 4 で扱う。

---

## 2. アーキテクチャ方針

### 2.1 `doctor` / `optimize` の関係

```
doctor（ヘルス診断・修正）
 ├─ 診断（1-4 の拡張・読み取り専用）
 └─ --fix（自動修正）

optimize（最適化診断・適用）
 ├─ 診断（分析と改善提案・読み取り専用）
 └─ --apply（提案の自動適用）
```

- `doctor` = 環境の健全性（更新・互換性・破損）を診断し修正
- `optimize` = 設定の複雑性（重複・未使用・ドリフト）を分析し改善
- 両者は `agent_plugins.py` の `ValidationIssue` を共通モデルとして利用。severity は **フェーズ 1 で拡張済みの `error` / `warning` / `info`** を参照する（フェーズ 3 で info 追加をしない）

### 2.2 修正の安全性

- 修正は常に**適用前にプレビュー**（`--dry-run` デフォルト）
- 修正対象は `~/.ai-adapter/` 管理下のファイルに限定（リポジトリ側は変更しない）
- 修正前のスナップショットを保存（ロールバック可能）

**バックアップの配置（Plan Architect 指摘反映）**:
- `~/.ai-adapter/backups/` は **git 同期リポジトリ内**（`Config.remote` で同期対象）にあるため、バックアップが同期・デプロイに混入し、**認証情報が外部漏洩するリスク**がある
- 対策: `config.py` の `add_to_gitignore`（L181）で `backups/` を `.gitignore` に追加し、同期対象から除外する
- あるいは管理外ディレクトリ（例: `~/.cache/ai-adapter/backups/`）に配置する方式を選択する（実装時に決定し、doc に明記）

---

## 3. BDD タスク分解

### タスク 3-1: `ai-adapter doctor`（フル）

**期待する振る舞い**:
- 入力: `ai-adapter doctor`
- 応答: ヘルスサマリー表示
  ```
  Environment Health
  ✓ Skills: 23 (2 updates available)
  ✓ MCP servers: 8
  ✓ Agents: 4
  ✓ Instructions: 3

  Updates available
    react-expert  v1.3 → v1.5
    github-reviewer  v2.0 → v2.2

  Compatibility issues
    ⚠ playwright MCP: incompatible with current configuration

  [Fix all] (Run `ai-adapter doctor --fix`)
  ```
- 入力: `ai-adapter doctor --json`
- 応答: ヘルス状態を JSON で出力
- 入力: `ai-adapter doctor 問題なし環境`
- 応答: 「Environment is healthy.」表示

**受け入れ条件**:
- AC1: 診断カテゴリは skills / mcp / agents / instructions / bins
- AC2: 更新検出は 3-5 のバージョン追跡ロジックを利用
- AC3: 診断結果は `ValidationIssue` モデルで統一（1-4 の拡張）
- AC4: `--json` は CI 連携用にマシンリーダブル

**データ（仕様例）**:
- 更新検出: ローカル Skill の `version`（frontmatter）と参照元（GitHub タグ等）の比較
- 互換性: MCP サーバーの command/args が現行環境で実行可能か（`--version` 等の簡易チェック）

---

### タスク 3-2: `doctor --fix`

**期待する振る舞い**:
- 入力: `ai-adapter doctor --fix`
- 応答: 検出された問題を自動修正
  - 更新可能な Skill を最新版に更新
  - 互換性問題を解消（設定の修正 or 無効化を提案・適用）
  - 重複設定の解消
- 入力: `ai-adapter doctor --fix --dry-run`
- 応答: 適用される修正のプレビュー（実際の変更なし）
- 入力: 修正後の確認
- 応答: 修正結果のサマリー + バックアップ場所の表示

**受け入れ条件**:
- AC1: `--dry-run` は一切の変更を加えない（テストで担保）
- AC2: 修正前スナップショットを `~/.ai-adapter/backups/{timestamp}/` に保存
- AC3: 修正は「更新」「無効化」「削除」の種別を表示し、個別に成功/失敗を報告
- AC4: 破壊的修正（削除）は必ず確認プロンプト（`--force` でスキップ可能）
- AC5: **ローカル実行のみ**（クラウド同期はフェーズ 4）

**データ（仕様例）**:
- `doctor --fix` → `✓ Updated react-expert v1.3 → v1.5` / `✓ Disabled incompatible playwright MCP` / `Backup: ~/.ai-adapter/backups/20260811_120000/`

---

### タスク 3-3: `ai-adapter optimize`（診断）

**期待する振る舞い**:
- 入力: `ai-adapter optimize`
- 応答: 設定の複雑性分析と改善提案
  ```
  Analyzing your AI environment...
  Found:
    ⚠ Duplicate instructions (3 files overlap)
    ⚠ Unused MCP server (playwright: no matching tool)
    ⚠ 4 overlapping skills
    ⚠ Claude / Codex configuration drift

  Recommended:
    1. Merge 3 instruction files
    2. Remove unused playwright MCP
    3. Upgrade github-reviewer
    4. Create shared code-review skill

  Estimated improvement: ↓ configuration complexity 31%
  ```
- 入力: `ai-adapter optimize --json`
- 応答: 分析結果を JSON で出力

**受け入れ条件**:
- AC1: 分析対象は重複 Instruction / 未使用 MCP / 重複 Skill / 設定ドリフト
- AC2: 各提案に「期待効果」（複雑性低減率の見積もり）を添える
- AC3: 読み取り専用（適用は 3-4 の `--apply`）

**データ（仕様例）**:
- 重複 Instruction: 3 ファイルの内容類似度が閾値以上 → マージ提案
- 未使用 MCP: `mcp list` のサーバーがどの Skill/Agent からも参照されていない → 削除提案

---

### タスク 3-4: `optimize --apply`

**期待する振る舞い**:
- 入力: `ai-adapter optimize --apply`
- 応答: 提案を自動適用
  - 重複 Instruction のマージ（内容の統合・バックアップ）
  - 未使用 MCP の無効化（削除ではなく無効化がデフォルト）
  - 重複 Skill の統合
  - 設定ドリフトの統一（優先順: Claude Code を正として Codex に反映）
- 入力: `ai-adapter optimize --apply --dry-run`
- 応答: 適用内容のプレビュー
- 入力: 適用後
- 応答: 変更後の複雑性指標（Before → After）を表示

**受け入れ条件**:
- AC1: `--dry-run` は変更なし
- AC2: 無効化（disable）は削除より安全側（デフォルト動作）
- AC3: マージ・統合は元ファイルをバックアップ
- AC4: 複雑性低減率の計測方法をドキュメント化（コード量・ファイル数・重複数の重み付け）

**データ（仕様例）**:
- `optimize --apply` → `✓ Merged 3 instruction files → 1` / `✓ Disabled unused MCP: playwright` / `Complexity: 42 → 29 (↓31%)`

---

### タスク 3-5: バージョン追跡

**期待する振る舞い**:
- 入力: `ai-adapter version`（または `doctor` 内部で利用）
- 応答: 管理下の Skill / Plugin のバージョン一覧
  ```
  Skill                    Installed   Latest
  react-expert             v1.3        v1.5
  github-reviewer          v2.0        v2.2
  ```
- 入力: 更新可能なバージョンがある場合
- 応答: 更新の有無を一覧に表示（`doctor` の Updates available に連動）

**受け入れ条件**:
- AC1: バージョン情報は frontmatter（`version` フィールド）を正とする
- AC2: 最新版の取得元を**明示的に定義**する（Plan Architect 指摘反映）:
  - ローカル定義: `~/.ai-adapter/` 内の他の Skill が参照する version 情報
  - GitHub リポジトリ: `--source github:user/repo` 指定時はタグ（`v*`）を取得
  - パブリック Registry: フェーズ 4-3（本フェーズでは未対応）
  - 取得元が未定義の Skill は「latest: unknown」表示
- AC3: オフライン時は「最新版不明」として表示（エラーにしない）
- AC4: git 操作は必ず `git.py` の `_run_git` 経由（fan-in 16 の唯一の窓口）

**データ（仕様例）**:
- `~/.ai-adapter/skills/react-expert/SKILL.md` frontmatter: `version: 1.3`
- GitHub タグ: `v1.5` → 更新可能と判定

---

## 4. データ構造設計

### `HealthReport` / `OptimizationReport`（`src/ai_adapter/doctor.py` に定義）

```python
@dataclass
class VersionInfo:
    name: str
    category: str  # "skill" | "plugin" | "mcp"
    installed: str | None
    latest: str | None
    source: str | None  # 比較元（GitHub tag 等）


@dataclass
class FixAction:
    kind: str  # "update" | "disable" | "remove" | "merge" | "unify"
    target: str
    detail: str
    destructive: bool  # True なら確認必須


@dataclass
class HealthReport:
    issues: list[ValidationIssue]  # agent_plugins 再利用
    updates: list[VersionInfo]
    fixes: list[FixAction]  # doctor --fix が適用する内容


@dataclass
class OptimizationReport:
    issues: list[ValidationIssue]
    recommendations: list[str]  # 改善提案
    estimated_reduction: float  # 複雑性低減率見積もり (%)
    actions: list[FixAction]  # optimize --apply が適用する内容
```

### バックアップ

- `~/.ai-adapter/backups/{timestamp}/` に修正前のファイルを保存
- `doctor --fix` / `optimize --apply` 実行前に自動作成

---

## 5. テスト計画（フェーズ 3）

| タスク | テストファイル | 種別 | 追加数 | 内容 |
|--------|--------------|------|--------|------|
| 3-1 | `tests/test_doctor.py`（新設） | Unit | 15 | ヘルスサマリー・`--json`・ValidationIssue 統合 |
| 3-2 | `tests/test_doctor.py` | Integration | 10 | `--fix` 適用・`--dry-run` 無変更・バックアップ作成 |
| 3-3 | `tests/test_optimize.py`（新設） | Unit | 10 | 複雑性分析（重複/未使用/ドリフト検出） |
| 3-4 | `tests/test_optimize.py` | Integration | 5 | `--apply` 適用・無効化デフォルト・複雑性指標 |
| 3-5 | `tests/test_version.py`（新設） | Unit | 10 | frontmatter 解析・GitHub タグ比較・オフライン表示 |

**安全テスト（必須）**:
- `doctor --fix --dry-run` / `optimize --apply --dry-run` が一切変更を加えないこと
- 破壊的修正（remove）が確認なしで実行されないこと
- 修正前バックアップが作成されること

**実行ゲート**: `scripts/run_tests.sh` で全テスト実行。

---

## 6. 既存コード再利用マップ（フェーズ 3）

| タスク | 再利用資産 | 用途 |
|--------|-----------|------|
| 3-1 | フェーズ 1 の `doctor` 診断部（1-4） | 診断の拡張 |
| 3-1/3-3 | `agent_plugins.py` の `ValidationIssue`（L51）/ severity | 診断結果の共通モデル |
| 3-2 | `skill.py` の get/remove・`mcp.py` の get/remove | 修正時の既存コマンド呼び出し |
| 3-3 | `diff.py` の `compare_all` | 重複・ドリフト検出 |
| 3-4 | `skill.py` / `mcp.py` / `instruction.py` の操作系 | 適用時の既存コマンド |
| 3-5 | `git.py` の `_run_git`（fan-in 16 の唯一の窓口） | GitHub タグ取得等の git 操作 |
| 3-5 | `agent_plugins.py` の frontmatter 解析（`validate_skill_dir` 等） | バージョン情報の読み取り |

---

## 7. リスクと対策

| リスク | 影響 | 対策 |
|--------|------|------|
| 自動修正による設定破壊 | ユーザーの環境喪失 | バックアップ必須・破壊的修正は確認必須・`--dry-run` デフォルト |
| ドリフト統一時の誤った「正」の選択 | 設定不整合 | デフォルトは Claude Code を正とするが、`--prefer` オプションで変更可能 |
| オフライン時のバージョン判定失敗 | 機能不全 | オフラインは「不明」表示で継続（エラーにしない） |
| 複雑性指標の主観性 | 信頼性低下 | 計測方法（コード量・ファイル数・重複数の重み付け）をドキュメント化 |

---

## 8. 実装順序

1. 3-5 バージョン追跡（doctor の更新検出の土台）
2. 3-1 `doctor` フル（1-4 診断部の拡張）
3. 3-2 `doctor --fix`（バックアップ機構 + 自動修正）
4. 3-3 `optimize` 診断（重複・未使用分析）
5. 3-4 `optimize --apply`（適用・複雑性指標）

---

## 9. 次のアクション

1. [ ] Plan Architect レビュー（本計画の妥当性検証）
2. [ ] 承認後、Implementer に実装依頼
3. [ ] Reviewer 検収 → QA チェック
