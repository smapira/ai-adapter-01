# add-all-rec UX 改善計画 レビュー（テスト戦略）

## 優先度
🟡 中（全体としては承認可能。T3 実装時に反映すべき軽微な指摘）

## 対象
- 計画書: `documents/plans/dev/20261009_add_all_rec_ux.md`
- 関連ファイル: `tests/test_cli.py`（TestAddAllRecCommand）、`tests/conftest.py`、`src/ai_adapter/commands/add_all_rec.py`

## 検証結果（問題なしと確認した点）

1. **既存 `test_add_all_rec_no_github` は計画後も落ちない**。
   新メッセージ `  .github/: not found (skipping ...)` に "not found" が含まれ、
   また `_import_mcp_servers` の `skip (file not found)` 行も残るため `assertIn("not found")` は満たされる。
   exit code も config 未初期化時のみ `return` する現状どおり 0 のまま。

2. **setUp/tearDown の `.github` バックアップ機構と新規テストは衝突しない**。
   `tests/conftest.py` の autouse `_isolate_cwd` が unittest.TestCase にも適用され、
   setUp 実行時点ですでに cwd は毎テスト新規の `tmp_path` なので、
   setUp の copytree は実質常に `_github_bak = None`（デッドコードだが無害）。
   tearDown の復元も `_github_bak` 存在時のみ動作するため、
   テスト内で cwd に作る `.github` と干渉しない。`Path.cwd()/.github` を直接触る既存パターンのまま安全。

3. **「`.github/` が作成されない」の assert 方法は適切**。
   `self.assertFalse((Path.cwd() / ".github").exists())` を invoke 後に書けばよく、
   tearDown の復元（バックアップありの場合のみ rmtree→copytree）と衝突しない。
   CliRunner はデフォルトで cwd を変えないので invoke 後の `Path.cwd()` でも安全。

## 指摘事項

### 1. T3 が S1 の「1 行報告」要件をテストしていない
S1 は「not found を含む .github 不存在の報告が 1 行（カテゴリ別3行ではない）」と定義しているが、
T3 のテスト更新には出力の絞り込みの記載がない。`assertIn("not found")` だけでは
`agents/: skip (directory not found)` 等の従来3行が残っていても通ってしまう。

**改善案**: `test_add_all_rec_no_github` に以下を追加する:

```python
self.assertIn("  .github/: not found", result.output)  # 具体的な行でピン留め
self.assertNotIn("agents/: skip", result.output)
self.assertNotIn("bin/: skip", result.output)
self.assertNotIn("skills/: skip", result.output)
self.assertNotIn("created.", result.output)  # mkdir 副作用の出力も消える
```

### 2. S5（未初期化）のテストが T3 に無い
S5 は BDD に定義されているが T3 のテスト一覧に含まれていない。
config チェックの最前段化（mkdir より先）は今回の主要変更の一つなのでテストで固定すべき。

**改善案**: T3 に `test_add_all_rec_uninitialized` を追加する:

```python
def test_add_all_rec_uninitialized(self):
    """S5: config 未初期化なら .github を作らずエラーメッセージを出す。"""
    import shutil
    shutil.rmtree(self.patch_home / ".ai-adapter")  # setUp で init 済みなので解除

    result = self.runner.invoke(main, ["add-all-rec"])
    self.assertEqual(result.exit_code, 0)
    self.assertIn("Configuration file not found", result.output)
    self.assertFalse((Path.cwd() / ".github").exists())
```

### 3. （軽微）既存テストの assert が緩い
現行の `assertIn("not found")` は `.mcp.json: skip (file not found)` 行だけでも通過してしまう。
T3 で更新する際に、指摘1の「具体的な行でピン留め」で自然に解消される。

## 改善案まとめ
- T3 に `assertNotIn("agents/: skip", ...)` 等の「1 行」検証を追加
- T3 に S5 テストを1件追加
- 既存テストの assert を `"  .github/: not found"` の具体行に限定

## 備考
- setUp の `.github` バックアップ機構は conftest 隔離下では機能していないが、
  二重防御として残す方針に問題なし。新規テストでこの機構を拡張・複製する必要はない。
- `test_add_all_rec_mcp` 末尾の `mcp_json.unlink()` は隔離下で不要（無害）。新規テストに同じクリーンアップを真似する必要はない。
