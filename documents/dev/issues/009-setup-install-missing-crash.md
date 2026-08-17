# Issue #9: `setup apply --install-missing` が traceback で異常終了する

> **優先度**: 🔴 高
> **種類**: ユーザー向け実行時エラー
> **対象ファイル**: `src/ai_adapter/commands/setup.py`, `src/ai_adapter/commands/skill.py`
> **対象行**: `setup.py` 116行目付近、`skill.py` 520行目付近

---

## 問題

不足している Skill を含むプロファイルに `--install-missing` を付けて適用すると、
Click コマンドである `skill_install` を通常の Python 関数として呼び出すため、
ユーザーに生の traceback が表示される。

```text
TypeError: Context.__init__() got an unexpected keyword argument 'source'
```

## 再現手順

```bash
ai-adapter init
ai-adapter setup apply web-development --yes --install-missing
```

## 影響

- 推奨プロファイルの主要導線が利用できない
- 内部実装の traceback が露出し、復旧方法が分からない
- 途中まで MCP 等が登録された場合、部分適用状態になる可能性がある

## 修正方針

- Click デコレータ付きコマンドを直接呼ばず、Skill インストール処理を通常関数へ分離する
- `skill install` と `setup apply` は同じ内部サービス関数を呼び出す
- 取得元がない Skill は、処理開始前に検証してユーザー向けエラーとして報告する
- プロファイル適用の部分成功・失敗を最後に集計する

## 受け入れ条件

- [ ] `setup apply web-development --yes --install-missing` で traceback が表示されない
- [ ] インストール成功・スキップ・失敗が Skill ごとに表示される
- [ ] 取得元がない場合は実行前または対象処理時に具体的な解決方法が表示される
- [ ] CLI の終了コードが全件成功時は `0`、失敗を含む場合は非 `0` になる
- [ ] `tests/test_setup.py` に実際の `--install-missing` 経路の回帰テストを追加する
- [ ] `bash scripts/run_tests.sh` が成功する
