# ai-adapter sync が変更ありのときにクラッシュする

**作成日**: 2026-07-20
**ステータス**: 🐛 確認済み（未修正）
**対象**: `ai-adapter v0.3.0`（`/Users/bookair18/OS/home/Codes/ai-adapter-01/`）

---

## 概要

`ai-adapter sync` を実行すると、変更がある場合に必ず `GitError: git diff --cached --quiet 失敗` で異常終了する。結果、`sync` コマンドが実質的に使い物にならない。

---

## 再現手順

### 前提

```bash
ai-adapter agent add some-file.md          # 何か変更を加える
```

### 再現

```bash
ai-adapter sync
```

### 実際の結果

```
Step 1: Git リポジトリを確認中...
Step 2: 変更をコミット中...
Traceback (most recent call last):
  ...
ai_adapter.git.GitError: git diff --cached --quiet 失敗:
```

### 期待する結果

```
Step 1: Git リポジトリを確認中...
Step 2: 変更をコミット中...
  変更をコミットしました。
Step 3: リモートの変更を取り込み中...
  pull --rebase 完了。
Step 4: リモートにプッシュ中...
  push 完了。
同期が完了しました。
```

---

## 関連ファイル

| ファイル | 役割 |
|---------|------|
| `/Users/bookair18/OS/home/Codes/ai-adapter-01/src/ai_adapter/git.py` | Git 操作ラッパー（`_run_git`, `add_all` を含む） |
| `/Users/bookair18/OS/home/Codes/ai-adapter-01/src/ai_adapter/sync.py` | sync コマンド本体 |
| `documents/plans/ai_adapter_integration_guide.md` | インテグレーションガイド（回避策を記載） |

---

## 受け入れ条件

- [ ] `ai-adapter sync` が変更ありの状態で正常終了する（commit → push まで）
- [ ] `ai-adapter sync` が変更なしの状態で正常終了する（"変更はありません"）
- [ ] `git diff --cached --quiet` の exit code 1 がエラー扱いされなくなった
- [ ] 既存の他の git 操作（init, push, pull 等）に影響がない
