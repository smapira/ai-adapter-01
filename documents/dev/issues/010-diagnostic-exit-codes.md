# Issue #10: 異常状態を報告する診断・展開コマンドが終了コード `0` を返す

> **優先度**: 🔴 高
> **種類**: CLI 契約・自動化互換性
> **対象ファイル**: `src/ai_adapter/cli.py`, `src/ai_adapter/commands/doctor.py`, `src/ai_adapter/commands/get_all_rec.py`

---

## 問題

未初期化状態で以下のコマンドを実行しても、警告文を表示して正常終了する。

```bash
ai-adapter status
ai-adapter doctor
ai-adapter doctor --json
ai-adapter get-all-rec
```

確認時はいずれも終了コード `0` だった。一方、`ai-adapter sync` は同じ未初期化状態で
終了コード `1` を返しており、コマンド間で契約が一貫していない。

## 影響

- CI やシェルスクリプトが未初期化・診断エラーを成功と誤認する
- `--json` を利用する機械処理で、内容を解析しない限り異常を検出できない
- ユーザーが直前の処理に失敗したことへ気づきにくい

## 修正方針

CLI 全体で終了コードの方針を定義する。

| 状態 | 終了コード |
|---|---:|
| 正常・問題なし | `0` |
| 診断上の warning のみ | 方針を決めて統一 |
| 未初期化で目的を実行できない | 非 `0` |
| error または展開失敗 | 非 `0` |

`click.ClickException` または `click.exceptions.Exit` を使い、テキスト出力と JSON 出力で
同じ終了コードになるよう統一する。

## 受け入れ条件

- [ ] 未初期化状態の `status` と `get-all-rec` が非 `0` を返す
- [ ] `doctor` の severity と終了コードの対応が文書化されている
- [ ] `doctor` と `doctor --json` が同一診断結果に対して同じ終了コードを返す
- [ ] CLI ヘルプまたは README に自動化時の終了コードが記載されている
- [ ] 各コマンドの終了コードを検証するテストが追加されている
- [ ] `bash scripts/run_tests.sh` が成功する
