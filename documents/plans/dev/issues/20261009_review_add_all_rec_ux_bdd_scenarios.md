# add-all-rec UX 改善計画 レビュー（BDD シナリオ S1-S5 の妥当性）

## 優先度
🟡 中（シナリオ自体は現行実装と矛盾なし。実装前に S5 の exit code 定義を追記すべき）

## 対象
- 計画書: `documents/plans/dev/20261009_add_all_rec_ux.md`
- 関連ファイル: `src/ai_adapter/commands/add_all_rec.py`、`src/ai_adapter/commands/get_all_rec.py`、`tests/test_cli.py`

## 検証結果（問題なしと確認した点）

1. **S1-S4 は現行実装と矛盾しない**。現行の出力
   （`created.` → agents/bin/skills skip 3行 → `.mcp.json` skip → root instructions skip → `Total: 0`）
   と T1/T2 の変更内容（`.github/` 無し時は created.+3 skip が1行に置換、total==0 で総括行を差し替え）が正しく対応している。
   S3 の「`.github/` 存在時は skip 行が従来どおり出る」も実装（`_import_agents` 等が個別に skip 行を echo）と整合。
2. **「`.github/` が無いときに作らない」は既存の設計思想と整合**（観点2の回答）。
   `get_all_rec.py` は deploy 側（宛先に `mkdir(parents=True, exist_ok=True)` するのは正しい）で、
   `add_all_rec.py` は import 側＝ソース読み取りなのでソースを作らないのが対称的で正しい。
   `providers/opencode.py:53-56`（`.github` 無しで ClickException）とも同思想。
   また `.mcp.json` と root instructions は `.github/` に依存しない独立ソースなので、
   `.github/` 無しでも続行する（S2 の）設計は妥当。
3. **total==0 時の get-all-rec hint は適切**（観点4の回答）。プロジェクトにソースが無いとき、
   グローバルストアからデプロイする reverse コマンドへ誘導する自然な導線。ストアが空でも
   hint は情報提示のみで害が無いため条件付けは不要。

## 指摘事項

### 1. 🟡 S5（未初期化）の exit code が未定義、且つ get-all-rec と不整合
計画の S5 は「`.github/` を作成しない」「メッセージを表示」とあるが exit code が書かれていない
（S1 は exit 0 と明記あり）。現行 `cmd_add_all_rec` は config 未初期化時に `return` し exit 0
（成功扱い）だが、`cmd_get_all_rec`（get_all_rec.py:282-284）は
`click.echo("Configuration file not found. Run ai-adapter init first.", err=True)` +
`raise click.ClickException("ai-adapter is not initialized.")` で exit 1。
「config チェックを最前段へ移動」するだけではこの不整合が残る。

**改善案**: get-all-rec に合わせて統一を推奨:

```python
config = _config.load_config()
if config is None:
    click.echo("Configuration file not found. Run ai-adapter init first.", err=True)
    raise click.ClickException("ai-adapter is not initialized.")
```

スコープを広げない場合は最低限、S5 に「exit code は現状どおり 0（変更しない）」と明記し、
T3 の S5 テスト（`test_add_all_rec_uninitialized`）の assert と矛盾させないこと。

### 2. 🟢 メッセージ案が既存の per-category 規約と異なる
計画 T1 の案 `  .github/: not found (skipping agents/, bin/, skills/)` は
既存規約 `  {name}: skip ({reason})`（例: `  agents/: skip (directory not found)`）と語順が異なる。

**改善案**: `  .github/: skip (directory not found)` に揃える（補足の `(skipping agents/, bin/, skills/)`
は括弧付きで残してよい）。providers 系の `Skip: 'x' directory not found.` とも語彙が整合する。
既存テストの `assertIn("not found")` は両案とも通過するためテストへの影響なし。

### 3. 🟢 S1/S2 の Then に「`.mcp.json` / root instructions の skip 行は残る」の明記
S1 の Then は「.github 不存在の報告が 1 行」とだけ書かれており、実装者が
`.github/` 無し時に全カテゴリの skip 行を抑制して本当に 1 行だけ出すと誤読しうる
（S2 では `.mcp.json` が動くことから独立ソースは続行することが分かるが、S1 単体では不明）。

**改善案**: S1 の Then に「`.mcp.json: skip` / `root instructions: skip` の行は従来どおり出る」を追記。

### 4. 🟢 （任意）hint 文言を既存の imperative 規約へ
既存の誘導メッセージは imperative 形式（`Run ai-adapter init first.` 等）。
計画の `Did you mean 'ai-adapter get-all-rec' ...?` は疑問形で既存規約から外れる。

**改善案**: `No items imported. Run 'ai-adapter get-all-rec' to deploy registered items into this project.`
のような imperative 形式にすると規約整合。また「Total: 0 の代わりに」とする replacement より、
`All imports completed: Total: 0` を残した上で hint を1行追加する構成なら出力パーサー互換性も保てる。

## 改善案まとめ
- S5 に exit code の明記（推奨: ClickException + exit 1 で get-all-rec と統一）
- `.github/` 不存在メッセージを `  .github/: skip (directory not found)` 形式へ
- S1 の Then に独立ソース（.mcp.json / root instructions）の skip 行が残る旨を追記
- （任意）hint を imperative 形式に、総括行は置換せず追加

## 備考
- 観点2・4 はいずれも計画の方向性自体は既存設計と整合しており、承認に必要な修正は軽微。
- 本 issue は振る舞い定義（BDD）観点のレビュー。テスト実装方針の指摘は
  `20261009_review_add_all_rec_ux_test_strategy.md` を参照。
