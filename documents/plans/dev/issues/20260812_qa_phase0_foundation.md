# QA 品質チェック: フェーズ 0（基盤完成）実装

## 優先度
🟡 中（重大な問題なし。ドキュメント追記と軽微な堅牢性改善）

## 対象
- 計画書: `documents/plans/dev/20260811_phase0_foundation.md`
- コミット: `52c505f` / `556483d` / `d2171c7` + 未コミット Reviewer 指摘修正 2 件
- 差分範囲: `57e2b42..HEAD` + 未コミット差分
- 主要ファイル:
  - `src/ai_adapter/providers/cursor.py`（新設）
  - `src/ai_adapter/commands/{skill,mcp,get_all_rec,instruction}.py`
  - `README.md` / `pyproject.toml` / `docs/readme-thumbnail.png`
  - `tests/test_cursor.py`（新設）ほかテスト群

## 検証サマリ

| 検証項目 | 結果 |
|---------|------|
| 全テスト実行（`bash scripts/run_tests.sh`） | ✅ 375 passed in 8.95s |
| 構文チェック（py_compile / bash -n） | ✅ OK |
| cli.py コマンド登録と実装の一致 | ✅ skill / mcp / agent(=instruction) / get-all-rec すべて登録済み |
| バージョン整合（pyproject / uv.lock / .venv / CHANGELOG） | ✅ すべて 0.22.0 |
| CHANGELOG 更新 | ✅ 0.22.0 セクション追記済み |
| README 画像 `docs/readme-thumbnail.png` | ✅ 実在（74,487 bytes） |
| README バッジ URL（GitHub Actions / shields.io / agent-plugins.org / python.org） | ✅ 妥当 |
| 比較文書 `documents/wiki/LLM-Tool-Comparison.md` | ✅ 実在 |
| 旧ワークスペースパス（`06_openclaw` / `/OS/media`）残存 | ✅ src/ tests/ README.md pyproject.toml になし |
| 未コミット差分（3 ファイル、19 insertions / 7 deletions） | ✅ Reviewer 指摘修正として妥当（README 画像位置・tag case-insensitive・テスト追加） |

### 実 CLI スモーク（HOME を一時ディレクトリに隔離して実行）

| コマンド | 結果 |
|---------|------|
| `skill add` → `skill search postgres --tag database` | ✅ ヒット |
| `skill list --tag DATABASE`（大文字） | ✅ case-insensitive でヒット |
| `skill get-all --format cursor --force` | ✅ `.cursor/rules/postgres-skill.mdc` 生成（frontmatter 変換・body 保持を確認） |
| `mcp get --format cursor --force` | ✅ `.cursor/mcp.json` 生成（`mcpServers` 構造確認） |
| `agent get --format cursor` | ✅ exit 2 + 明確なエラーメッセージ |
| `get-all-rec --no-summary` | ✅ サマリーなしでデプロイ |
| `get-all-rec`（サマリーあり） | ✅ `=== Summary ===` にカテゴリ別集計表示 |
| `skill search` no-match ヒント | ✅ `Hint:` 表示 |

---

## 発見項目

### 🟡 1. README のコマンドリファレンスに Cursor 形式・新オプションの記載が不足

**対象**: `README.md`（Skill / MCP / get-all-rec セクション）

**指摘事項**:
- 新設した `--format cursor` がコマンドリファレンスの表に未記載（openclaw のみ記載）
  - L360: `skill get-all --format openclaw` はあるが `--format cursor` がない
  - L390: `mcp get --format openclaw` はあるが `--format cursor` がない
- 新設の `skill search --tag <tag>` オプションが L364 の表に未記載
- 新設の `get-all-rec --no-summary` が L236-240 のオプション表に未記載
- Quick Start（L175-177）に openclaw デプロイ例はあるが cursor の例がない

**改善案**:
```markdown
# skill 表に追記
| `skill get-all --format cursor` | Copy all registered skills to `.cursor/rules/*.mdc` |
| `skill search <keyword> --tag <tag>` | Search skills by keyword, narrowed by tag |

# mcp 表に追記
| `mcp get --format cursor` | Export MCP settings to `.cursor/mcp.json` (server-name-based merge) |

# get-all-rec オプション表に追記
| `--no-summary` | Skip the pre-deploy diff summary |
```

---

### 🟡 2. README の Project Structure に新設ファイルが未反映

**対象**: `README.md` L801-848（Project Structure セクション）

**指摘事項**:
- `src/ai_adapter/providers/cursor.py`（新設）が一覧にない（L830-833 は opencode / openclaw / codex の 3 つのみ）
- `tests/test_cursor.py`（新設）が tests/ 一覧にない

**改善案**:
```markdown
│       └── providers/          # External tool integrations
│           ├── opencode.py     # OpenCode integration (install/alias/uninstall)
│           ├── openclaw.py     # OpenClaw integration (MCP + skills export)
│           ├── cursor.py       # Cursor integration (MCP + rules export)
│           └── codex.py        # Codex CLI integration (AGENTS.md generation)
...
│   ├── test_cli.py
│   ├── test_cursor.py          # Cursor provider tests
│   └── test_instruction.py
```

---

### 🟢 3. cursor.py の export_mcp に env key 妥当性検証がない

**対象**: `src/ai_adapter/providers/cursor.py` L66-68

**指摘事項**: openclaw.py は `_warn_invalid_env_key()`（`^[A-Z_][A-Z0-9_]*$` パターン）で env key を検証して警告するが、cursor.py の `export_mcp` には同等の検証がない。プロバイダ間で挙動が不統一。

**改善案**: openclaw.py の `_env_key_pattern` / `_warn_invalid_env_key` を共通モジュール（例: `providers/_util.py`）へ抽出し、cursor.py からも呼ぶ。または cursor.py 内に同様の検証を追加。

---

### 🟢 4. skill 名のパストラバーサル耐性（pre-existing パターン踏襲）

**対象**: `src/ai_adapter/providers/cursor.py` `deploy_skills`（`rules_dir / f"{skill_entry.name}.mdc"`）、`src/ai_adapter/commands/skill.py` `skill_add`（`skills_dir / name`）

**指摘事項**: SKILL.md frontmatter の `name` を無検証でパスセグメントに連結する。`name` に `/` や `..` を含む SKILL.md を読み込んだ場合、意図しないディレクトリに書き込み得る。実リスクは低い（信頼境界がユーザー自身のローカル操作）が、`skill_add` 時点で防ぐのが安全。

**改善案**: `skill_add` / `_parse_skill_metadata` で name を検証:
```python
name = metadata.get("name") or src.name
if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
    raise click.ClickException(f"Invalid skill name in frontmatter: {name!r}")
```

---

### 🟢 5. システム Python 環境のインストール版が旧バージョン（参考情報）

**対象**: 環境（リポジトリ外）

**指摘事項**: グローバル `python3` の `ai-adapter` が 0.19.1 のまま（pyproject は 0.22.0）。`.venv` は 0.22.0 でテスト・スモークとも問題なし。リポジトリ起因の問題ではないが、グローバル利用時は `uv sync` / `uv pip install -e .` の再実行が必要。

**改善案**: 開発環境で `uv sync && uv pip install -e .` を再実行して 0.22.0 に更新。

---

## 判定

**✅ 承認（マイナー指摘あり）**

- ブロッカー・セキュリティ上の重大問題は発見されなかった
- 全 375 テストパス、構文チェック OK、実 CLI スモーク全項目動作
- 未コミット差分（3 ファイル）は Reviewer 指摘修正として妥当
- 🟡 2 件（README 追記）と 🟢 3 件（堅牢性・参考）は次のコミットで対応推奨。README 追記のみ実施し、コード変更は次フェーズ以降に回しても可

## 備考
- テストは `scripts/run_tests.sh` 経由でサンドボックス（`.testbox/`）内で実行済み（リポジトリルートでの `uv run pytest` 直接実行はしていない）
- スモークテストは HOME を `/var/folders/.../T/opencode/qa-smoke/home` に隔離して実行（`~/.ai-adapter` は未変更）
- `.gitignore` への追記・`.github/workflows` への影響なし
