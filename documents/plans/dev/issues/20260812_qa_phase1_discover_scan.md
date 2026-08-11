# QA 品質チェック: フェーズ 1（Discover）— `scan` + `doctor`

- 日付: 2026-08-12（再検証 2026-08-12T05:35+09:00）
- 対象: `595fb87..HEAD`（実装コミット: 7b01301 / e8f43a2 / 2f2c1cc / 5d4053a / 66254f0）
- 計画書: `documents/plans/dev/20260811_phase1_discover_scan.md`
- 検証方法: 静的レビュー + `scripts/run_tests.sh`（446 passed / 9.88s）+ 隔離 HOME での実 CLI 動作確認 + Python AST 構文チェック + `_has_secret_component` ロジック検証

## 判定: 条件付き承認（🔴 なし / 🟡 4 件 / 🟢 3 件）

機能・セキュリティの根幹（認証情報の非表示・パストラバーサル防御・CLI 動作）は検証済みで問題なし。
ただし README / CHANGELOG の未更新、Cursor rules の import 構造不整合、symlink 経由の外部読込について
修正を推奨する。すべて Implementer 対応を前提とした発見提案であり、QA 側での修正は行わない。

---

## 検証サマリ

| 項目 | 結果 |
|------|------|
| 全テスト（`scripts/run_tests.sh`） | ✅ 446 passed（9.88s） |
| `ai-adapter scan` / `--json` | ✅ exit 0・出力正常 |
| `ai-adapter doctor` / `--json`（未初期化・初期化済み） | ✅ exit 0・出力正常 |
| 認証ファイル（`~/.codex/auth.json` 等）が scan 結果に出ない | ✅ テキスト・JSON 両方で確認 |
| シークレット値（`sk-...`）・frontmatter 以外の内容が表示されない | ✅ |
| `cli.py` コマンド登録（scan / doctor） | ✅ `main.add_command` 済み・`--help` に表示 |
| `pyproject.toml` (0.22.0) = uv 環境 `__version__` | ✅ 一致 |
| git 作業ツリー | ✅ クリーン（.testbox は ignore 済み） |
| 旧ワークスペースパス（`06_openclaw` 等）・`/Users/bookair18` 絶対パス | ✅ なし |
| README 相対リンク（`documents/wiki/LLM-Tool-Comparison.md`） | ✅ 存在 |
| Python AST 構文チェック（scan.py / doctor.py / commands） | ✅ 全ファイル OK |
| `_has_secret_component` ロジック検証（12 パターン） | ✅ 全ケース一致 |
| Cursor rules symlink 検証（`is_symlink()=True, is_dir()=True`） | ✅ #4 の問題確認済み |

---

## 🟡 中優先度

### 1. README に `scan` / `doctor` コマンドの記述がない

**対象**: `README.md`（Command Reference セクション）

**指摘**: `ai-adapter add-all-rec` / `get-all-rec` 等の記述はあるが、フェーズ 1 で追加された
`ai-adapter scan` と `ai-adapter doctor` の記載がない。新規ユーザーの入口となるコマンドであり、
発見性の観点で README への明記が必須。

**改善案**:
```markdown
### `ai-adapter scan`

環境の AI エージェント設定を検出・診断します（~/.claude, ~/.codex, ~/.cursor,
~/.config/opencode, 現在のプロジェクト）。認証ファイルは読み取りません。
--json で CI 連携用の JSON 出力が可能です。

```bash
ai-adapter scan
ai-adapter scan --json
```

### `ai-adapter doctor`

登録済みストアのヘルス診断（読み取り専用）を表示します。

```bash
ai-adapter doctor
ai-adapter doctor --json
```
```

---

### 2. CHANGELOG 0.22.0 に scan / doctor の記述がない

**対象**: `CHANGELOG.md`（[0.22.0] エントリ、2026-08-12 付）

**指摘**: scan / doctor / info severity 拡張は 0.22.0 として実装されたが、
CHANGELOG 0.22.0 の Added / Changed に記載がない（Cursor integration と README 刷新のみ）。

**改善案**: [0.22.0] の Added に追記:
```markdown
- **`ai-adapter scan`**: 環境検出 + 問題診断（重複 MCP / Skill 不一致 / 古い Skill）
  - 認証ファイル・内容全文は読まない（セキュリティブラックリスト）
  - `--json` / `--project-dir` / 未初期化時の import 導線
- **`ai-adapter doctor`**: ストアのヘルス診断（読み取り専用、`--fix` はフェーズ 3）
- **ValidationIssue severity に `info` を追加**（stale skill 検出用）
```

---

### 3. Cursor rules の import で SKILL.md 構造にならない（機能的バグ）

**対象**: `src/ai_adapter/scan.py` — `_import_skill`（L603〜634）と `scan_cursor`（L288〜297）

**指摘（実 CLI で再現確認済み）**:
- `.cursor/rules/frontend.mdc` は scan で category=`skill` として検出される
- import 時、`_import_skill` が `shutil.copytree(item.path.parent, dest)` を実行するが、
  parent は `.cursor/rules` ディレクトリそのもの
- 結果: `~/.ai-adapter/skills/frontend/frontend.mdc` となり、**SKILL.md 構造
  （`skills/<name>/SKILL.md`）にならない**

影響:
1. ストア側に SKILL.md がないため、doctor の update 検出（`_skill_version` が SKILL.md の
   frontmatter version を読む）から漏れる
2. `.cursor/rules/` に複数の .mdc がある場合、**rules ディレクトリ全体が 1 つの skill として
   コピーされる**（1 rule = 1 skill の意図と乖離）

**改善案**: `_import_skill` に「コピー元が SKILL.md を持つディレクトリであること」のガードを追加
（または cursor rule の import を除外して `settings` 相当の扱いに変更）:
```python
# _import_skill 冒頭
src_root = item.path.parent
if not (src_root / "SKILL.md").is_file():
    return False  # SKILL.md 構造でない検出物は skill として取り込まない
```

---

### 4. symlink をたどって外部ディレクトリを scan / import する

**対象**: `src/ai_adapter/scan.py` — `_scan_skills`（L203〜204）・`_import_skill`（L621〜624）

**指摘（実 CLI で再現確認済み）**:
- `~/.claude/skills/linked-link → /path/to/outside` のような symlink があると、
  scan は外部ディレクトリの `SKILL.md` を検出し frontmatter（name/description）を表示する
- import 時、`shutil.copytree(item.path.parent, dest)` はデフォルト引数
  `symlinks=False` のため **symlink をたどって外部ディレクトリの内容全体をストアへコピー**する
- 外部ディレクトリに `.env` / `*.key` 等が含まれる場合、そのまま `~/.ai-adapter/skills/...` に
  取り込まれ、後続の `sync` による git 同期で外部へ流出するリスクがある

**改善案**: scan / import の両方で symlink を拒否:
```python
# _scan_skills 内
if not d.is_dir() or d.is_symlink() or d.name.startswith("."):
    continue

# _import_skill 内（コピー前に）
if item.path.parent.is_symlink():
    return False
```

---

## 🟢 低優先度

### 5. MCP 一覧で同名サーバーがツール別パスなしに並ぶ

**対象**: `src/ai_adapter/commands/scan.py` — `_render_list`（L91〜98）

**指摘**: 複数ツールに同名 MCP（例: `github`）があると
```
MCP
  3 configured
  ├─ context7
  ├─ github
  └─ github
```
のように出所がわからないまま同名が並ぶ（JSON には path があるが表示にない）。

**改善案**: MCP 表示のみツール/パスを添える:
```python
click.echo(f"  {branch} {item.name} ({TOOL_LABELS.get(item.tool, item.tool)})")
```

---

### 6. doctor がストア側 SKILL.md 欠落 skill を無警告でスキップ

**対象**: `src/ai_adapter/doctor.py` — `_find_skill_updates`（L126〜149）

**指摘**: store 側に SKILL.md がない skill（#3 の Cursor rules import で発生しうる状態）は
`store_version is None` で静かにスキップされる。ストアの skill ディレクトリが壊れているのに
doctor が警告しない。

**改善案**: store 側 SKILL.md 欠落を warning issue として報告:
```python
if store_version is None:
    issues.append(
        ValidationIssue("doctor", f"skill '{skill.name}' is missing SKILL.md in the store", severity="warning")
    )
    continue
```

---

### 7. MCP import 時に同一 config ファイルを item ごとに再解析

**対象**: `src/ai_adapter/scan.py` — `_import_mcp`（L657〜667）

**指摘**: 同一 config（例: `.claude/settings.json` 内の mcp が複数）から検出された mcp item ごとに
`_read_mcp_servers_from_file(item.path)` が呼ばれる。小規模データでは実害なし（効率のみ）。

**改善案**: import 前に config パス単位でキャッシュする（任意・優先度低）。

---

## 承認済みとして確認した防御（回帰防止）

- 💡 `is_safe_store_name`（config.py）: frontmatter `name: ../../evil` によるストア脱出・
  rmtree を拒否（`skill add` / `add-rec` / `add-all-rec` / scan import の 4 経路に適用済み・
  tests で decoy 検証済み）
- 💡 `is_ignored` のコンポーネント完全一致: `secretary.agent.md` / `tokensmith.md` を誤って
  除外しない（F1 回帰テストあり）
- 💡 scan はファイル名 + frontmatter のみ表示。内容全文・認証値・JSON 構造は非表示
- 💡 非対話実行（EOF）での import プロンプトは「Import skipped.」+ exit 0（F4 回帰テストあり）
- 💡 HOME 隔離フィクスチャ `isolated_home`（conftest.py）が scan/doctor テストを実環境から隔離

## コード品質メモ（追加観察）

- `_GENERIC_SECRET_COMPONENTS` + コンポーネント単位照合は巧妙で堅牢。substring による誤検出を防ぎつつ、
  `secretary.agent.md` / `tokensmith.md` を正しく検出する。F1 での修正が的確
- `ScanResult.count()` / `by_category()` の API はシンプルで使いやすい
- `doctor.py` の `_compatibility_issues` は既存の `_validate_opencode_config` を再利用しており、
  診断ロジックの二重化を回避している
- `commands/scan.py` の `_render_agents` は「settings-only install」を「installed (no agents/skills)」と
  表示する F2 修正が適切
- コード全体の命名規則・ドキュメント密度・エラーハンドリングは一貫して良好

## 備考

- システム python3 で `import ai_adapter` すると `__version__` が 0.19.1 と表示されるが、
  これはシステム site-packages に古い ai-adapter が install されている環境依存の問題
  （`uv run python` では 0.22.0 で一致）。リポジトリ側の不整合ではない。
  確認は常に `uv run` 経由で行うこと。