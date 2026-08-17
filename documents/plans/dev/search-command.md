# ai-adapter search コマンド実装計画

## 概要

登録済みの全カテゴリ（agent, skill, mcp, command, prompt, instruction, bin）を横断してキーワード検索できる `ai-adapter search` コマンドを実装する。
各カテゴリ別の絞り込みにも対応する。

## 仕様

### コマンド構文

```
ai-adapter search <keyword>                    # 全カテゴリを検索
ai-adapter search <keyword> --agent            # agent のみ検索
ai-adapter search <keyword> --skill            # skill のみ検索
ai-adapter search <keyword> --mcp              # mcp のみ検索
ai-adapter search <keyword> --command          # command のみ検索
ai-adapter search <keyword> --prompt           # prompt のみ検索
ai-adapter search <keyword> --instruction      # instruction のみ検索
ai-adapter search <keyword> --bin              # bin のみ検索
ai-adapter search <keyword> --tag <tag>        # タグで絞り込み
ai-adapter search <keyword> --env <env>        # 環境で絞り込み
ai-adapter search <keyword> --json             # JSON 出力
ai-adapter search                              # 全アイテム一覧
```

### 検索対象フィールド

| カテゴリ | 検索対象 |
|---------|---------|
| agent   | name, description |
| skill   | name, description, tags |
| mcp     | name, command |
| command | name, description, content |
| prompt  | name, description, content |
| instruction | name, description, content |
| bin     | name, description |

### 振る舞い

| # | シナリオ | 期待結果 |
|---|---------|---------|
| 1 | `search "review"` | name/description に "review" を含む全アイテムをカテゴリ別に表示 |
| 2 | `search "review" --agent` | agent のみ表示 |
| 3 | `search "review" --skill` | skill のみ表示 |
| 4 | `search "review" --tag seo` | tag に "seo" を持つアイテムのみ表示 |
| 5 | `search "review" --env prod` | env が prod のアイテムのみ表示 |
| 6 | `search "nonexistent"` | 「一致するアイテムがありません」+ ヒント表示 |
| 7 | `search` (keyword なし) | 全アイテムをカテゴリ別に一覧表示 |
| 8 | `search "review" --json` | JSON 形式で出力 |
| 9 | `search "review" --agent --skill` | agent と skill の両方を検索 |

### 正常系・異常系・エッジケース

| 種別 | ケース | 動作 |
|------|-------|------|
| 正常系 | keyword ヒットあり | カテゴリ別にインデント付きで表示 |
| 正常系 | keyword ヒットなし | 「一致するアイテムがありません」 |
| 正常系 | keyword なし | 全アイテム一覧 |
| 正常系 | 複数カテゴリ指定 | 指定したカテゴリのみ検索 |
| 正常系 | JSON 出力 | JSON 形式で出力 |
| 異常系 | config 未初期化 | "Run ai-adapter init first." |
| エッジケース | 大文字小文字 | case-insensitive マッチング |
| エッジケース | 空文字 keyword | 全アイテム一覧と同等 |

## 実装構成

### 新規ファイル

1. `src/ai_adapter/search.py` — コア検索ロジック
2. `src/ai_adapter/commands/search.py` — CLI コマンド定義

### 変更ファイル

3. `src/ai_adapter/cli.py` — search_group 登録
4. `tests/test_cli.py` — テスト追加
5. `tests/test_search.py` — ユニットテスト

## タスク一覧

1. `search.py` を作成（コアロジック）
2. `commands/search.py` を作成（CLI）
3. `cli.py` に search_group を登録
4. テストを書く
5. テスト実行・修正
