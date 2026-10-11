# add-all-rec UX 改善計画（2026-10-09）

## 背景（観測された問題）

空のプロジェクトで `ai-adapter add-all-rec` を実行すると以下が出力される:

```
'/Users/.../python-scripts-ec/.github/' created.
  agents/: skip (directory not found)
  bin/: skip (directory not found)
  skills/: skip (directory not found)
  .mcp.json: skip (file not found)
  root instructions: skip (no root-level files found)
All imports completed: Total: 0
```

問題点:

1. **不要な副作用**: import コマンド（ソースは `.github/`）なのに `.github/` を新規作成する。
   空ディレクトリを作っただけで「何か成功した」ように見えるが、実際は何もインポートしていない。
2. **ノイズが多い**: `.github/` 自体が無い場合にまでカテゴリごとの skip 行が 3 行出る。
3. **次のアクションが不明**: Total: 0 のとき「このプロジェクトに登録物をデプロイしたいなら
   `get-all-rec` を使うべき」という自然な誘導がない。

## 根拠（コード確認）

- `src/ai_adapter/commands/add_all_rec.py:181-186` — `github_dir.mkdir()` による作成副作用と
  `'created.'` 出力。config チェックより先に実行されている（未初期化でも `.github/` が作られる）。
- `tests/test_cli.py:556-559` — `test_add_all_rec_no_github` が `"not found"` 出力を検証
  （現状は skip 行に含まれるため通っている。メッセージ変更後も維持すること）。

## 振る舞い定義（BDD）

### S1: 何もソースが無い空プロジェクト

- Given: `.github/` なし、`.mcp.json` なし、ルート指示ファイルなし、`~/.ai-adapter` は初期化済み
- When: `ai-adapter add-all-rec`
- Then:
  - `.github/` は**作成されない**（副作用の排除）
  - `.github/` 不存在の報告が **1 行**（`  .github/: skip (directory not found)`、
    カテゴリ別3行ではない）。存在しない `.github/` 配下の個別 skip 行は出さない
  - 独立ソース（`.mcp.json` / ルート指示）の skip 行は従来どおり出る（.github とは独立）
  - 末尾に Total 0 の報告と、`get-all-rec` への hint を表示
  - exit code 0

### S2: `.github/` なし but `.mcp.json` あり

- Given: `.github/` なし、`.mcp.json` に `mcpServers.test-server` あり
- When: `add-all-rec`
- Then:
  - `.github/` は作成されない
  - `.github/` 不存在の 1 行報告のみ（agents/bin/skills の個別 skip 行は出さない）
  - MCP サーバーは通常どおり 1 registered
  - `All imports completed: Total: 1`

### S3: `.github/` はあるが中身が空（Total 0 だがディレクトリは存在）

- Given: `.github/` 存在、`agents/` `bin/` `skills/` なし、`.mcp.json` なし、ルート指示なし
- When: `add-all-rec`
- Then:
  - カテゴリごとの skip 行は現状どおり表示（ディレクトリは存在するので）
  - 末尾が `All imports completed: Total: 0` の代わりに「何もインポートされなかった」旨の
    明確なメッセージ + `get-all-rec` hint

### S4: データあり（正常系）

- Given: `.github/agents/` にファイルあり、`.mcp.json` あり 等
- When: `add-all-rec`
- Then: 現状の出力（`N registered` / `All imports completed: Total: N`）が**変化しない**

### S5: 未初期化

- Given: `~/.ai-adapter` 未初期化
- When: `add-all-rec`
- Then:
  - `.github/` を作成**しない**（config チェックが先）
  - `Configuration file not found. Run ai-adapter init first.` を stderr に表示し、
    `get-all-rec`（get_all_rec.py:282-284）と同じく `ClickException` で **exit 1**

## タスク分解

- [x] T1: `cmd_add_all_rec` の制御フロー修正
  - config チェックを最前段へ移動。未初期化は get-all-rec 同様 err=True + ClickException（exit 1、S5）
  - `.github/` 不存在時に mkdir しない。代わりに 1 行 `  .github/: skip (directory not found)`
    を既存の per-category 規約どおり出力（S1, S2）
  - `.github/` 存在時は従来どおり `_import_agents/_import_bins/_import_skills` を呼ぶ（S3, S4）
- [x] T2: 末尾サマリーメッセージの分岐
  - total > 0: `All imports completed: Total: {total}`（現状維持、S2/S4）
  - total == 0: 総括行 `All imports completed: Total: 0` を維持し、hint 1 行を追加
    `No items imported. Run 'ai-adapter get-all-rec' to deploy registered items into this project.`
    （imperative 形式、S1, S3）
- [x] T3: テスト追加・更新（tests/test_cli.py）
  - `test_add_all_rec_no_github` 更新: `.github/` が作成されないことを assert、
    `  .github/: skip (directory not found)` の具体行を assert、
    `agents/: skip` と `created.` が**出ない**こと assert
  - 新規: `test_add_all_rec_no_github_with_mcp`（S2）
  - 新規: `test_add_all_rec_empty_github_dir`（S3: skip 行 + hint 出力）
  - 新規: `test_add_all_rec_uninitialized`（S5: exit 1 + .github 未作成）
  - 既存 normal-case テストが green であることを確認（S4）
- [x] T4: ドキュメント更新
  - README.md `add-all-rec` セクションに「`.github/` は作成しない / 何も無い場合の hint」を追記
  - CHANGELOG.md [Unreleased] に Changed/Fixed エントリ追記

## スコープ外

- `-h` オプション対応（Click の help_option_names）— 別タスクとして扱う
- `get-all-rec` 側の挙動変更
- python-scripts-ec プロジェクト自体のセットアップ
