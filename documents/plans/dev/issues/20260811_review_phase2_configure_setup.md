# フェーズ 2 計画レビュー（Configure: `ai-adapter setup` + プロファイル定義 + Pack + skill install）

## 優先度
🟡 中（🔴 なし / 🟡 2 / 🟢 3）

## 対象
- 計画書: `documents/plans/dev/20260811_phase2_configure_setup.md`

## 指摘事項

### 🟡 2-1: プロファイルの「名前参照」と既存 add コマンドの「パス引数」が乖離している（AC2 が実装不能）

計画はプロファイル定義で Skills / Agents / Commands を**名前**で参照する（§3 データ例: `skills: [frontend, react, typescript, testing]`、`agents: [code-reviewer, frontend-engineer]`）一方、AC2 は「適用は既存の `skill add` / `agent add` / `command add` を呼び出す（新規に登録ロジックを書かない）」とし、§6 再利用マップも同様。しかしコードベース実態は:

- `skill add`（skill.py L85）: **PATH 引数必須**（`PATH: Path to the skill directory containing SKILL.md`）
- `agent add`（agent.py L188）/ `command add`（command.py L66）: 同様にパス引数
- `mcp add`（mcp.py L72）: 名前 + command/args（名前参照が成立するのは MCP のみ）

プロファイルの名前 `frontend` を `skill add` に渡しても解決できない。AC2 の「既存 add を呼び出すだけ」は成立しない。

**改善案**: setup 適用フローに「**名前 → ソース解決**」ステップを明記する:
1. `~/.ai-adapter/skills/<name>` に導入済み → そのパスを add に渡す
2. 未導入 → 2-5 の `skill install <name>`（または標準プロファイル同梱ディレクトリ `src/ai_adapter/profiles/` 配下の資産）から取得
3. 解決不能なら「Skill 'frontend' not found」+ 導入候補を表示
- AC2 を「既存 add を呼び出す。ただし名前→パスの解決（導入済み / install / 同梱）を setup 側で行う」に修正し、解決ロジック自体は新規実装と明記する

### 🟡 2-2: `--dry-run` の再利用参照が不確実 — `opencode.py` に dry-run 相当は存在しない

§6 再利用マップの「2-3 | `opencode.py` の `--dry-run` 相当パターン（**あれば**）」は存在確認ができていない参照。`providers/opencode.py` に dry-run 相当の実装はない（`opencode_validate` は読み取り専用だが「変更なしプレビュー」ではない）。

**改善案**: 「（あれば）」を削除し、`--dry-run` は「変更を加えない実装 + 変更なしをテストで担保」として**新規実装**と明記する。プレビュー表示（2-3 の `Would add:` 形式）は `diff.py` の `compare_*` 系（CategoryDiff 一覧）を流用できる点を再利用マップに追記する。

### 🟢 2-3: 2-5 `skill install --source github:user/repo` に git 操作の再利用が未記載

GitHub リポジトリからの取得は git clone が必要。再利用マップに `git.py` の `clone`（L221）/ `_run_git`（L17）が含まれていない。AGENTS.md の「git 実行は常に `_run_git` 経由（fan-in 16 の唯一の窓口）」に従い、raw subprocess で git を呼ばないこと。

**改善案**: 2-5 の再利用マップに「`git.py` の `clone` / `_run_git`（リポジトリ取得）」を追記する。

### 🟢 2-4: 新コマンドの cli.py 登録とスモークテストが未記載

`setup` / `pack` コマンド新設時に `cli.py` の `main.add_command`（現状 L325-337）への登録と、`tests/test_cli.py` の CLI スモークテスト追加が必要（フェーズ 0 レビュー 🟢0-6 と同種）。

**改善案**: 各タスクの受け入れ条件に「`cli.py` 登録と CLI スモークテスト」を明記する。

### 🟢 2-5: 2-5 AC2 の文言を実在シンボルに合わせる

AC2「`plugin validate` 相当のチェック」はスキル検証なので正確には `agent_plugins.py` の `validate_skill_dir`（L485、実在確認済み）が該当。§6 再利用マップには既にあるため、AC の文言も「`validate_skill_dir`（agent_plugins.py L485）による frontmatter 検証」に統一する。

## 備考
コードベース参照（`skill_add` の PATH 引数、`agent add` / `command add` のパス引数、`mcp add` の名前+引数、`git.py` の `clone` / `_run_git`、`validate_skill_dir` L485、cli.py の add_command 群 L325-337）はすべて実在確認済み。YAML 定義・Pack 逐次適用・標準 5 プロファイル限定・Already registered 表示などの設計は妥当。🟡2-1（名前→ソース解決）は本フェーズの核であり、実装前に必ず設計を確定すること。

## 判定
修正必要（軽微〜中）— 🟡2 件の修正を条件に承認可
