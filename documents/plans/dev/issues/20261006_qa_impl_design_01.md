# QA: 設計書 01 実装（user scope instructions）

- 日付: 2026-10-06
- チェッカー: QA (Codex QA)
- 対象: `documents/plans/dev/20261006_design_01_user_scope_instructions.md` 対応実装
  （instruction.py / config.py / scan.py / agent_format.py / tests / README）
- 前提: コードレビュー済み（Critical C1 は修正済みと報告）、実装者は 651 テスト通過・ruff/lizard 通過を報告
- 総合判定: **合格（設計書 01 スコープ）** — リポジトリ全体の `ruff check .` はスコープ外ファイルで 1 件失敗（下記 W1）

---

## 1. テスト実行の独立検証 — ✅ PASS

`bash scripts/run_tests.sh` を独立実行:

- **651 passed in 3.75s**（実装者の報告と一致）
- C1 回帰テスト 2 件を確認・通過:
  - `tests/test_instruction.py:396` `test_get_all_scope_user_reverse_order_no_overwrite`
    （STYLE.md → CLAUDE.md 順で登録 → `--force` でも mapped 先を保持し、native 名は `CLAUDE (1).md` に退避）
  - `tests/test_instruction.py:414` `test_get_all_scope_user_reverse_order_prompt`
    （`--force` なしでプロンプト表示、mapped 先を保持）
- 対象 3 ファイル限定の再実行: `tests/test_config.py` `tests/test_instruction.py` `tests/test_scan.py` → **124 passed, 16 subtests passed**
- C1 修正コードも確認: `instruction.py:291-293` に「Collision check FIRST — before the identity shortcut」と明記され、ショートカットより先に `placed`/ディスク存在を判定

## 2. コード品質 — ⚠️ WARNING（W1 のみ。design-01 対象ファイルは全パス）

| コマンド | 結果 |
|---|---|
| `uv run ruff format --check .` | ✅ PASS（73 files already formatted） |
| `uv run ruff check .` | ❌ FAIL — 1 件、`src/ai_adapter/providers/claude.py:14` I001（import 整理）。**未追跡の別設計書（02）用ファイル**。design-01 対象 7 ファイルのみで再実行 → ✅ "All checks passed!" |
| `uv run lizard src/ai_adapter/commands/instruction.py src/ai_adapter/config.py src/ai_adapter/scan.py -C 20` | ✅ PASS（閾値超過なし。対象 3 ファイルの最大 CCN は `instruction_get_all` の 13） |

⚠️ 実装者の「ruff 通過」報告は design-01 ファイル限定であれば正しいが、リポジトリ全体では成立していない。

## 3. パス検証 — ✅ PASS

`src/ai_adapter/config.py` を設計書 §2.1/§2.2 と照合:

| 検証項目 | 実装 | 結果 |
|---|---|---|
| codex → `~/.codex/` | `config.py:142` `Path.home() / f".{tool}"` | ✅ |
| claude → `~/.claude/` | 同上 | ✅ |
| opencode → `~/.config/opencode/` | `config.py:140-141` | ✅ |
| gemini → `~/.gemini/` | 同上（`.{tool}`） | ✅ |
| zed (macOS) → `~/Library/Application Support/Zed/` | `config.py:154-155` | ✅ |
| zed (Linux) → `~/.config/zed/` | `config.py:159`（Windows は `%APPDATA%\Zed` フォールバック付き） | ✅ |
| cursor → 対応外 | `config.py:169-171` `get_user_instruction_path` が ValueError | ✅（設計どおり Exit(2) 維持） |
| codex/opencode/zed → AGENTS.md | `config.py:118-125` `USER_INSTRUCTION_FILENAMES` | ✅ |
| claude → CLAUDE.md | 同上 | ✅ |
| gemini → GEMINI.md | 同上 | ✅ |

テスト担保: `tests/test_config.py:201-268`（全パス + zed OS 分岐 + cursor 拒否）、
`tests/test_instruction.py:213-242`（get の全プラットフォーム配置、zed は Darwin/Linux subTest）

## 4. 構造的一貫性 — ✅ PASS（軽微な指摘 2 件は下記 W2/W3）

- **§2.1 テーブルとの整合**: `resolve_scope_path()` は category=instruction 時、project → プロジェクトルート（`config.py:271-277`）、user → `get_user_tool_dir(tool)`（`config.py:259-264`）。§2.1 のデプロイ先（standard/codex/claude/opencode/gemini/zed/cursor）と完全一致。
- **`--scope user` 時の `add_to_gitignore` 不呼出の担保**:
  - `instruction.py:205`（get）: `if scope == "project": add_to_gitignore(dest)` — ガードあり
  - `instruction.py:389`（get-all）: `if scope == "project": add_to_gitignore(dest)` — ガードあり
  - プログラムで両箇所のガードを検証済み（`guarded_by_project_scope=True`）
  - テスト担保: T11 `test_get_scope_user_skips_gitignore`（L287）、`test_get_all_scope_user_skips_gitignore`（L464）＋ T12 回帰（L295、L455）
- **scan.py の User instruction 検出**: `_scan_user_instruction`（scan.py:223-232）が `path.is_file()` と `is_ignored(scan_rel)` を適用。claude/codex/opencode の 3 ツールで呼び出し確認（scan.py:271/293/331）。gemini/zed の scan 検出は設計書どおり設計 05/06 に委譲（設計書 §リスク「scan 検出は各設計書で」と整合）。
- **README**: `--scope` / `--format` の新オプションが文書化済み（README.md:259-301、テーブル・マッピング説明・使用例あり）。

## 5. セキュリティ — ✅ PASS

- **home 配下の `.gitignore` 汚染防止**: get/get-all 両コマンドとも `--scope user` では `add_to_gitignore` を経路から除外（上記 4）。mocked テストで `assert_not_called()` まで担保。
- **scan はファイル名のみ**: `_scan_user_instruction` は内容を読まず `path.name` のみ出力（scan.py:226-228 docstring「security rule: filenames only」）。
- **秘密情報の除外**: `SCAN_IGNORE_PATTERNS`（scan.py:36-49）に `.codex/auth.json`、`.claude/.credentials.json`、`.cursor/*auth*`、`*.key` 等を定義、`is_ignored()`（scan.py:92-105）で glob + 秘密語コンポーネント一致の両方を適用。

---

## 発見事項（優先度順）

### ⚠️ W1（🟡 中）: リポジトリ全体の `uv run ruff check .` が失敗

- **場所**: `src/ai_adapter/providers/claude.py:14`（I001 import block un-sorted、`--fix` 可能）
- **内容**: 未追跡の別設計書（02: Claude native paths）用プロバイダファイル。design-01 の実装・テスト・README はすべて ruff パス。ただし QA 項目「`uv run ruff check .` 全パス」はリポジトリ全体では未達で、実装者の「ruff 通過」報告は design-01 スコープ限定の解釈が必要。
- **影響**: design-01 のマージ判断には非影響。設計 02 をコミットする前にリポジトリ全体の静的チェックが赤のまま残る。
- **推奨アクション**: `uv run ruff check --fix src/ai_adapter/providers/claude.py` を実行（Implementer / 設計 02 担当）。design-01 本体の再作業は不要。

### ⚢ W2（🟢 低）: コードコメントの設計書参照が不正確

- **場所**: `src/ai_adapter/config.py:178`「Deploy targets for tool × category (design 01 §2.3; reused by designs 02/03/04)」
- **内容**: 設計書 01 §2.3 は `--scope`/`--format`/`--project-dir` のオプション設計であり、tool × category（agents/skills/commands/prompts/rules）の matrix は定義していない。matrix 本体は設計 02/03/04 由来（`codex skills → .agents/skills` のコメントも design 03 参照）。
- **影響**: コメントのみ。挙動・テストへの影響なし。
- **推奨アクション**: コメントを「design 02/03/04 §（tool × category matrix）」に修正。

### ⚢ W3（🟢 低）: gitignore 安全策が「一元制御」にならず、2 重のガードになっている

- **場所**: `src/ai_adapter/commands/instruction.py:205, 389` vs `src/ai_adapter/config.py:236-253`（`ScopeTarget.use_gitignore`）
- **内容**: 設計書 §リスクで「`resolve_scope_path()` が `use_gitignore=False` を返す仕様で一元制御」とされているが、instruction get/get-all は `resolve_scope_path` を経由せず、独自の `if scope == "project"` ガードで実装。挙動は同一で、コードガード + mocked テストで二重に保護されておりリスクなし。
- **影響**: 挙動・セキュリティとも問題なし。設計の「一元制御」意図が実装とずれているだけ。
- **推奨アクション**: 任意。将来 instruction 系が `ScopeTarget.use_gitignore` を消費するようリファクタするか、設計書側の「一元制御」記述を実装に合わせて緩和。

---

## 総合判定: 合格（設計書 01 スコープ）

651 テスト通過（C1 回帰含む）、パス定義・スコープ matrix・gitignore ガード・scan セキュリティはすべて設計書 01 と整合。設計書 01 の実装としてマージ可。

**推奨アクション**:
1. 設計 02 に属する `src/ai_adapter/providers/claude.py` の ruff I001 を修正してから次フェーズへ（W1、design-01 と独立）
2. W2/W3 のコメント/設計書記述の突合を次回のドキュメント整備時に実施（軽微、実装修正不要）
