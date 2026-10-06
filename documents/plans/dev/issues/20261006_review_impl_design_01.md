# コードレビュー: 設計書 01 実装

- 日付: 2026-10-06
- レビュアー: Codex Reviewer
- 対象: 設計書 01 実装（未コミット差分 7 ファイル +857/-40）
- 結果: **要修正（REQUEST CHANGES）** — Critical 1 件

---

## 検証結果

| 検証 | 結果 |
|------|------|
| フルテストスイート | **645 passed** |
| 対象3ファイルのテスト | 118 passed |
| ruff format --check / ruff check | 全パス |
| lizard -C 20 | 変更関数の最大 CCN は 13。閾値超過なし |
| C1 の順序依存バグ | **再現に成功** |

---

## 🔴 Critical

### C1: `get-all --scope user` のファイル名マッピングが登録順に依存し、マッピング済みファイルが無警告で破壊される

**場所**: `src/ai_adapter/commands/instruction.py:293-295`（`_resolve_get_all_dest_name`）

`src_name == mapped_name`（例: Claude で `CLAUDE.md` を登録済み）の場合は、`placed`（この実行で既にマッピング先を占有したか）とディスク上の存在を**確認せず**にマッピング先を返す。

**再現手順（実測）**:
```bash
# store に STYLE.md → CLAUDE.md の順で登録し、
ai-adapter agent get-all --format claude --scope user --force
```

実行結果:
- `STYLE.md` → `~/.claude/CLAUDE.md`（mapped、`placed = {CLAUDE.md}`）
- 続く `CLAUDE.md` は早期 return で衝突を検知せず `~/.claude/CLAUDE.md` を**無警告で上書き**
- 結果: `~/.claude/` に残るのは CLAUDE.md の内容のみ。**STYLE.md のマッピング先が消滅**し、出力にも conflict 警告が出ない

`--force` なしの場合は、自分の操作で直前に作った `CLAUDE.md` に対して `Overwrite 'CLAUDE.md'?` と聞かれ、`n` で **Abort（exit 1）** となってコマンドが途中終了（部分デプロイのまま放棄）。

**設計書違反**: タスク 01-2 AC2「マッピング後の同名衝突時は確認プロンプト + 警告」「残りを任意名で配置」に違反。

**修正方針**:
1. 293 行目のショートカットより先に `placed` / ディスク存在を判定する、または
2. 2パス方式: まず `src_name == mapped_name` のネイティブ名ファイルを配置し、その後で他ファイルをマッピング（衝突時は任意名 + 警告）
3. テストに「STYLE.md → CLAUDE.md の逆順」ケースを追加

---

## 🟡 Major

### M1: テスト不足 — BDD タスク 01-1/01-2 の一部期待挙動が未担保

| 未テスト項目 | 設計書上の根拠 | 実装リスク |
|---|---|---|
| `get-all --format cursor` → Exit(2) | タスク 01-1 AC3 | get-all 経路の回帰が検出できない |
| `get-all --format standard --scope user` → エラー | タスク 01-1 AC / §2.3 | 同上 |
| `get-all --scope project` 時の `add_to_gitignore` 呼び出し | タスク 01-2 AC4 | T12 は get のみ。get-all の project 経路は未検証 |

### M2: `resolve_scope_path` の matrix に設計書 01 外の組み合わせを先行実装している

設計書 01 が定義するのは instruction 系とタスク 01-5 の例程度だが、実装は設計書 02/03/04 由来の組み合わせをハードコードしている。設計書 02-04 承認との整合確認、または matrix を各設計書実装時に追加する運用への切り替えを推奨。

---

## 🟢 Minor

| ID | 指摘 |
|----|------|
| m1 | get-all の identity マッピング行（`AGENTS.md → AGENTS.md`）が出力されない（設計書の出力例と不一致） |
| m2 | `get_user_tool_dir("cursor")` のエラーメッセージが "Unknown tool" で不正確 |
| m3 | 設計書の状態表記が「ドラフト」のまま |
| m4 | `get` の `name` 引数にパス走査の余地（既存問題。`is_safe_store_name` 相当の検証追加を推奨） |

---

## AC 別整合サマリー

| AC | 判定 |
|----|------|
| 01-1 AC1 省略時後方互換 | ✅ |
| 01-1 AC2 platform user パス配置 | ✅ |
| 01-1 AC3 cursor Exit(2) | ✅（get-all はテスト未） |
| 01-1 AC4 上書き確認プロンプト / --force | ✅ |
| 01-1 AC5 user 時 add_to_gitignore 不呼出 | ✅ |
| 01-2 AC1 get-all ファイル名マッピング | ⚠️ 部分（C1 の順序依存バグあり） |
| 01-2 AC2 衝突時プロンプト+警告 | ❌ C1 で無警告上書き |
| 01-2 AC4 user 時 gitignore 不呼出 | ✅ |
| 01-2 AC5 project get-all は元のファイル名維持 | ✅ |
| 01-3 scan user 検出 | ✅ |
| 01-4 パスヘルパー | ✅ |
| 01-5 resolve_scope_path | ✅（M2 の matrix 範囲懸念あり） |
| 完了定義: ruff / lizard CCN≤20 | ✅ |
| 完了定義: README 更新 | ✅ |

---

## 推奨修正事項

1. **[必須] C1 の修正**: `_resolve_get_all_dest_name` の衝突判定を `src_name == mapped_name` ショートカットの**前**に移す
2. **[必須] C1 回帰テスト追加**: 「STYLE.md → CLAUDE.md の逆順登録」ケース（--force あり/なしの両方）
3. **[推奨] M1 のテスト追加**: get-all 経路の cursor/standard スコープ/gitignore 検証
4. **[推奨] M2 の対処**: matrix の設計書対応を明文化
5. **[任意] m1-m4**

---

## 総合判定

**要修正（REQUEST CHANGES）**。C1 の修正完了後に再確認が必要。
