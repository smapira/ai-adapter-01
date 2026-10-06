# プラットフォーム差異解消 マスターデザイン

- 日付: 2026-10-06
- 作成者: Product Manager
- 状態: ドラフト（Plan Architect レビュー待ち）
- 上位計画: `documents/plans/dev/20260811_ai_adapter_grand_design.md`
- 根拠資料: `platforms-Table 1_実装状況.csv`（ai-adapter コードベース突き合わせ結果）
- 対象バージョン: v0.24 以降の段階的リリース
- 制約: ドキュメント作成フェーズ（実装は別途 Implementer 依頼）

---

## 1. 目的

プラットフォーム仕様書（MECE）と ai-adapter の実装状況を突き合わせた結果、
**未実装 38 / 部分実装 12 / 互換対応 7** のギャップが特定された。
本マスターはギャップを実装単位に再編し、各個別設計書への入口を提供する。

**ゴール**: プラットフォームごとの設定パス差異を吸収し、
`~/.ai-adapter/` 一元管理から各 AI ツールのネイティブパスへ確実にデプロイできる状態にする。

---

## 2. アーキテクチャ原則（全設計書共通）

### 2.1 ソースオブトゥルース

- 唯一の正本は `~/.ai-adapter/`（config.json + 各ストアディレクトリ）
- プラットフォーム固有パスは**デプロイ先/検出先**であり、マスターデータにしない
- 例外: User スコープの指示ファイル（`~/.codex/AGENTS.md` 等）はデプロイ先としてのみ扱う

### 2.2 Provider パターン（既存 cursor/openclaw/codex/opencode に準拠）

```
src/ai_adapter/providers/<platform>.py
├── resolve_*_output_path(path: str | None) -> Path
├── export_*(data: list[Model]) -> dict          # 形式変換（純関数寄り）
├── merge_into_*(path, data, force=False) -> None # 既存ファイル保持マージ
├── deploy_*(items, force=False) -> None          # ディレクトリ展開
└── @click.group (任意: install/uninstall/validate 等)
```

### 2.3 CLI 統合方針

| ケース | 方針 | 例 |
|--------|------|-----|
| 既存概念にマップできる | 既存コマンドに `--format` を追加 | `skill get --format gemini` |
| プラットフォーム固有操作 | provider サブコマンド | `ai-adapter zed install` |
| User スコープデプロイ | 既存コマンドに `--scope` を追加 | `agent get --scope user` |
| 検出強化 | `scan.py` に `scan_<tool>()` を追加 | `scan_gemini(home)` |

### 2.4 セキュリティ原則（必須）

- 認証情報ファイルは scan・deploy ともに**絶対対象外**
  - `~/.codex/auth.json`, `~/.claude/.credentials.json`, `~/.cursor/*auth*`, `*key*`
- `SCAN_IGNORE_PATTERNS` に一元定義（新規プラットフォームも同様に追加）
- merge 操作は `.bak` バックアップ必須（既存 cursor/openclaw パターン）
- 既存の非管理ファイルは preserve（上書きしない）
- **user スコープデプロイでは `add_to_gitignore` を呼び出さない**
  （home 配下の `.gitignore` を辿って dotfiles リポジトリに誤追記する恐れがあるため）

### 2.4.1 `--scope` の横断基盤（設計書 01 に集約）

`--scope project|user` は instruction（`agent`）のみならず、
`sub-agent` / `skill` / `command` / `mcp` 全般で使用する共通概念とする。

- **scope 解決ヘルパー**は設計書 01（`config.get_user_*_path()`）で一元定義
- 設計書 02/03/04 はその**再利用**として記述する（独自実装しない）
- デフォルトは `project`（既存動作との後方互換）

### 2.5 品質ゲート

- テストは必ず `bash scripts/run_tests.sh` 経由
- ruff format → ruff lint → sandboxed tests → lizard CCN ≤ 20
- 新規 provider は単体テスト必須（`tests/test_<platform>.py`）
- **既存テスト数（実測）**: 606 件（`pytest --collect-only` 確認。設計書初稿の「337」は誤り）
- 各設計書の完了定義には **ruff / lizard CCN / カバレッジ** の確認を含める

### 2.6 scan タクソノミー方針（一元決定）

project 配下のプラットフォーム固有ディレクトリの tool 名を以下で統一する。

| 検出パス | tool 名 | 理由 |
|----------|---------|------|
| `<project>/.github/` | `"project"` | 既存 scan_project の慣習を維持 |
| `<project>/.claude/` | `"claude"` | プラットフォーム固有ディレクトリはプラットフォーム名 |
| `<project>/.codex/` | `"codex"` | 同上 |
| `<project>/.gemini/` | `"gemini"` | 同上 |
| `<project>/.zed/` | `"zed"` | 同上 |
| `<project>/.vscode/` | `"vscode"` | 同上 |
| `<project>/AGENTS.md` 等ルート指示 | `"project"` | ルート直下の共有ファイルは project |

**判定基準**: `.github/` のみ特別扱い（Copilot 中心の既存実装の名残）。
新規プラットフォームディレクトリは一律プラットフォーム名とする。

### 2.7 scan 拡張の共通ルール（全設計書必須）

新規プラットフォームを scan に追加する設計書は、以下を**すべて**満たすこと。

1. **`TOOL_ORDER` への append のみ**（タプル全体の再定義を禁止）
   - 既存: `("claude", "codex", "cursor", "opencode", "project")`
   - 設計書 08 実装後: `..., "vscode", "project")`
   - 設計書 05 実装後: `..., "gemini", "project")`
   - 設計書 06 実装後: `..., "zed", "project")`
2. **`TOOL_LABELS` へのラベル追加を必須**
   - `commands/scan.py` は `TOOL_LABELS[tool]` を直接参照するため、ラベル未追加は **KeyError で scan コマンドがクラッシュ**する
3. **`scan_all` への `items.extend(scan_<tool>(...))` 登録を明記**
4. **`SCAN_IGNORE_PATTERNS` への追加を検討**（認証情報・秘密情報を含むパス）

### 2.8 merge ロジックの共通化

JSON サーバーマージ（.bak + preserve）は cursor/openclaw で既に実装されている。
新規プラットフォーム（gemini/vscode/zed 等）で同一パターンが 4 実装目以上になるため、
**`src/ai_adapter/merge_util.py` 等への共通ヘルパー抽出を最初の新規プラットフォーム実装時に検討する**。

```python
# 想定シグネチャ
def merge_json_servers(path: Path, servers_key: str, data: dict, force: bool = False) -> None:
    """Merge server definitions into JSON config preserving unmanaged servers."""
```

### 2.9 doctor.py のパス注意

診断ロジックの実体は **`src/ai_adapter/commands/doctor.py`**（`src/ai_adapter/doctor.py` ではない）。
設計書の変更対象は正しいパスを記載すること。

---

## 3. 実装単位マップ（設計書インデックス）

| # | 設計書 | 対象ギャップ | 優先度 | 想定規模 |
|---|--------|-------------|--------|----------|
| 01 | [user_scope_instructions](./20261006_design_01_user_scope_instructions.md) | User スコープ指示ファイル（5 プラットフォーム横断） | P0 | 小 |
| 02 | [claude_native_paths](./20261006_design_02_claude_native_paths.md) | Claude Code プロジェクト .claude/ パス | P0 | 中 |
| 03 | [codex_native_paths](./20261006_design_03_codex_native_paths.md) | Codex ネイティブ TOML/rules/skills パス | P1 | 中 |
| 04 | [opencode_extensions](./20261006_design_04_opencode_extensions.md) | OpenCode User スコープ + jsonc + 互換 skills | P1 | 小 |
| 05 | [gemini_cli_provider](./20261006_design_05_gemini_cli_provider.md) | Gemini CLI 新規 provider | P1 | 大 |
| 06 | [zed_provider](./20261006_design_06_zed_provider.md) | Zed 新規 provider | P2 | 中 |
| 07 | [cursor_extensions](./20261006_design_07_cursor_extensions.md) | Cursor .cursorrules + plugin package | P2 | 小 |
| 08 | [vscode_editor_and_mcp](./20261006_design_08_vscode_editor_and_mcp.md) | VS Code エディタ設定 + .vscode/mcp.json + .github/instructions デプロイ | P1 | 中 |

---

## 4. 優先度の根拠

### P0（プラットフォーム差の即効解消）

- **01 User スコープ指示**: 5 プラットフォーム横断で未対応。1 つの `--scope user` で一括解消
- **02 Claude Code パス**: Claude Code は主要ターゲットだが `.claude/` プロジェクト管理が空白

### P1（ネイティブ対応の強化）

- **03 Codex**: AGENTS.md 互換からネイティブ config/rules へ
- **04 OpenCode**: User スコープと jsonc で運用範囲拡大
- **05 Gemini CLI**: 完全未対応プラットフォーム。仕様が確定しているため実装可能
- **08 VS Code**: Copilot 中心の現状からエディタ設定と .vscode/mcp.json へ

### P2（後続対応）

- **06 Zed**: 仕様が比較的新しく、依存が少ないため後回し可
- **07 Cursor**: 現状の `--format cursor` で主要ユースケースは充足。legacy/plugin は追加分

---

## 5. クロスカッティング関係

```
01 user_scope_instructions ──┬── 03 codex (AGENTS.md user)
                             ├── 02 claude (CLAUDE.md user)
                             ├── 04 opencode (AGENTS.md user)
                             ├── 05 gemini (GEMINI.md user)
                             └── 06 zed (AGENTS.md user)

08 vscode_editor ── 独立（.vscode/ 管理。Copilot .github/ は現状維持）
05 gemini ── 08 と独立（Gemini は .gemini/ 配下）
```

**依存順序の推奨**: 01 → 02 → 04 → 03 → 08 → 05 → 07 → 06

理由:
1. 01 は横断基盤（`--scope` オプション）を先に定義
2. 02/04 は既存 provider 拡張で小さく検証
3. 03 は 01 の User スコープ実装後の方が効率的
4. 05/06 は新規 provider で規模が大きい

---

## 6. ギャップ → 実装実装単位の対応表

### OpenAI Codex（行 1-9）

| 行 | パス | 現状 | 設計書 |
|----|------|------|--------|
| 2 | `<agent-config>.toml` | ❌ | 03 |
| 3 | `.codex/config.toml` (Project) | ❌ | 03 |
| 4 | `~/.codex/config.toml` | ⚠️ scan のみ | 03 |
| 6 | `~/.codex/AGENTS.md` | ❌ | 01 |
| 7 | `~/.codex/rules/*.rules` | ❌ | 03 |
| 8 | `.agents/skills/` (Project) | 🔄 AGENTS.md 経由 | 03 |
| 9 | `~/.agents/skills/` / `~/.codex/skills` | ⚠️ scan のみ | 03 |

### OpenCode（行 10-20）

| 行 | パス | 現状 | 設計書 |
|----|------|------|--------|
| 12 | `~/.config/opencode/agents/` | ❌ | 04 |
| 14 | `~/.config/opencode/commands/` | ❌ | 04 |
| 15 | `opencode.jsonc` | ⚠️ json のみ | 04 |
| 16 | `~/.config/opencode/opencode.json` | ⚠️ scan のみ | 04 |
| 18 | `~/.config/opencode/AGENTS.md` | ❌ | 01 |
| 19 | `.claude/skills` / `.agents/skills` 互換 | ❌ | 04 |

### Claude Code（行 21-32）

| 行 | パス | 現状 | 設計書 |
|----|------|------|--------|
| 22 | `.claude/agents/` (Project) | ❌ | 02 |
| 23 | `~/.claude/agents/` | ⚠️ scan のみ | 02 |
| 24 | `.claude/settings.json` | ❌ | 02 |
| 25 | `.claude/settings.local.json` | ❌ | 02 |
| 26 | `~/.claude/settings.json` | ⚠️ scan + JSON 検査のみ | 02 |
| 28 | `~/.claude/CLAUDE.md` | ❌ | 01 |
| 30 | `.claude/rules/*.md` | ❌ | 02 |
| 31 | `.claude/skills/` (Project) | ❌ | 02 |
| 32 | `~/.claude/skills/` | ⚠️ scan のみ | 02 |

### Gemini CLI（行 33-42）→ 設計書 05

全行 ❌ または 🔄。新規 provider として一括対応。

### Cursor（行 43-49）

| 行 | パス | 現状 | 設計書 |
|----|------|------|--------|
| 48 | `.cursorrules` | ❌ | 07 |
| 49 | plugin package skills/ | ❌ | 07 |

### VS Code / Copilot（行 50-59）

| 行 | パス | 現状 | 設計書 |
|----|------|------|--------|
| 51 | `.claude/agents/` (互換) | ❌ | 02（Claude 側で吸収） |
| 53 | `.vscode/settings.json` | ❌ | 08 |
| 54 | `.github/copilot-instructions.md` | ⚠️ | 08 |
| 55 | `.github/instructions/**/*.instructions.md` | ⚠️ scan のみ | 08 |
| 57 | `.vscode/mcp.json` | ❌ | 08 |

### VS Code エディタ（行 60-63）→ 設計書 08

launch.json / extensions.json / tasks.json は ❌。

### Zed（行 64-72）→ 設計書 06

全行 ❌ または 🔄。新規 provider として一括対応。

---

## 7. 非スコープ（本ロードマップでは実装しない）

| 対象 | 理由 |
|------|------|
| Codex `auth.json` / Claude credentials 管理 | セキュリティ原則により絶対対象外 |
| 各ツールのモデル/API 設定の完全管理 | 本ツールの責務外（設定同期であってプロバイダ管理ではない） |
| `.cursorrules` の自動移行ツール | レガシーのため後続イテレーション |
| Gemini sandbox プロファイルの生成 | 任意性が高く、生成よりも検出・配置許可を優先 |
| Gemini extension の完全マネージド生成 | `~/.gemini/extensions/<name>/` + `gemini extensions install` フローが複雑。Phase B で検討 |
| VS Code エディタ設定（settings.json / launch.json / tasks.json） | ユーザーのエディタ設定破壊リスクが高いため scan 検出のみ |
| Zed tasks.json / keymap.json | 個人設定・プロジェクト固有のため scan 検出のみ |
| Cursor plugin package の marketplace 連携 | local plugin のみ対応。marketplace は将来イテレーション |

---

## 8. 成功基準

| 指標 | 現状 | 目標（本ロードマップ完了時） |
|------|------|---------------------------|
| ✅ 実装済 | 15 / 72 行 | 50 行以上 |
| ❌ 未実装 | 38 / 72 行 | 10 行以下 |
| プラットフォーム別 provider | 4（codex/opencode/cursor/openclaw） | 7（+claude/gemini/zed/vscode） |
| scan 対象ツール | 5（claude/codex/cursor/opencode/project） | 9（+gemini/zed/vscode + project 配下の .claude/.codex） |
| テスト | 606（実測） | 750+ |

---

## 9. レビュー計画

各個別設計書作成後、Plan Architect に分担レビューを依頼する。

| 設計書 | レビュアー | 確認観点 |
|--------|-----------|----------|
| 01-04 | Plan Architect A | 既存 provider パターンとの整合、API 互換性 |
| 05-06 | Plan Architect B | 外部仕様の正確性、新規 provider の設計 |
| 07-08 | Plan Architect A + B | CLI UX 一貫性、移行コスト |

レビュー結果は `documents/plans/dev/issues/20261010_review_platform_parity_*.md` に記録する。
