# ai-adapter sync エラー調査報告書

**作成日**: 2026-07-20  
**対象**: `~/.ai-adapter/` の GitHub 同期 (`ai-adapter sync`)

---

## エラー概要

```
ai-adapter sync
Step 3: リモートの変更を取り込み中...
ERROR: pull --rebase 失敗: The requested URL returned error: 403
```

`~/.ai-adapter/` を GitHub リモート (`smapira/my-agent-config`) と同期する際、
`git pull --rebase origin main` が **403 Forbidden** で失敗。

---

## 原因分析

### 原因1: 認証方式の問題（primary）

| 項目 | 設定値 |
|------|--------|
| `config.json` の remote | `git@github.com:smapira/my-agent-config.git` （SSH） |
| 実際の git remote URL | `https://github.com/smapira/my-agent-config.git` （HTTPS） |

ユーザーが手動で `git remote set-url origin https://...` を実行したため、
**SSH 鍵認証 → HTTPS 認証** に変わっていた。

HTTPS で GitHub に書き込みアクセスするには **Personal Access Token (PAT)** が必須。
ユーザー名＋パスワードでは 2021年8月以降 403 が返る。

### 原因2: ブランチ名のハードコード（secondary）

```
HEAD → refs/heads/master   （ローカルは master）
git pull --rebase origin main  （スクリプトは main 固定）
```

`git.py` の `pull_rebase()` と `push()` がブランチ名 `main` をハードコードしている。

```python
# pull_rebase
_run_git(["pull", "--rebase", "origin", "main"], cwd=path)

# push
_run_git(["push", "origin", "main"], cwd=path)
```

ローカルは `master` ブランチなので、リモートに `main` があっても齟齬が生じる。

### 原因3: config.json と実 Git remote の不一致

`config.json` は SSH URL (`git@github.com:...`) を保存しているが、
実際の `.git/config` は HTTPS URL を指しており、同期が取れていない。

---

## 修正内容

### 対応1: remote URL を SSH に戻す

```bash
cd ~/.ai-adapter
git remote set-url origin git@github.com:smapira/my-agent-config.git
```

config.json の値と一致させる。

### 対応2: git.py のブランチ名を動的に取得

`pull_rebase()` と `push()` で `main` 固定ではなく、
`get_current_branch()` で現在のブランチ名を使うよう修正。

---

## 参考: 関連ソース

| ファイル | 該当箇所 |
|---------|---------|
| `src/ai-adapter-01/src/ai_adapter/sync.py` | Step 3: pull --rebase 呼び出し |
| `src/ai-adapter-01/src/ai_adapter/git.py` | `pull_rebase()` L100-111, `push()` L113-114 |
| `~/.ai-adapter/config.json` | `"remote": "git@github.com:smapira/my-agent-config.git"` |
| `~/.ai-adapter/.git/config` | `url = https://github.com/smapira/my-agent-config.git` |
