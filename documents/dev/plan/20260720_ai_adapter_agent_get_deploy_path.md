# ai-adapter agent get 展開先パス問題

**作成日**: 2026-07-20
**ステータス**: 🐛 バグ確認済み（未修正）
**対象**: `ai-adapter v0.3.0`（`/Users/bookair18/OS/home/Codes/ai-adapter-01/`）

---

## 概要

`ai-adapter agent get <name>` をプロジェクトルートで実行しても、展開先が `~/.ai-adapter/.github/agents/` になってしまい、プロジェクトの `.github/agents/` にコピーされない。

---

## バグの再現手順

### 前提

```bash
# ai-adapter インストール済み、エージェント登録済み
ai-adapter --version  # → 0.3.0
ai-adapter agent list # → reviewer.agent など7件が登録済み

# プロジェクトルートにいる状態
cd /Users/bookair18/OS/media/05_claude
```

### 再現

```bash
ai-adapter agent get reviewer.agent
```

### 実際の結果

```
エージェント 'reviewer.agent' を /Users/bookair18/.ai-adapter/.github/agents/reviewer.agent.md にコピーしました。
```

### 期待する結果

```
エージェント 'reviewer.agent' を /Users/bookair18/OS/media/05_claude/.github/agents/reviewer.agent.md にコピーしました。
```

---

## 原因分析

プロジェクトルート検出ロジックが正常に動作していない。以下の可能性がある：

1. **プロジェクトルート検出の仕組みが未実装** — カレントディレクトリから `.ai-adapter.json` や `.github/` などを探索してプロジェクトルートを特定するロジックがない
2. **展開先が常に `~/.ai-adapter/` 配下に固定されている** — `agent get` の出力先がハードコードされている
3. **CWD 解釈の不具合** — `agent get` 実行時に `cd /Users/bookair18/OS/media/05_claude` にいるにも関わらず、内部で CWD が `~/.ai-adapter/` と認識されている

---

## 影響範囲

| コマンド | 影響 |
|---------|------|
| `ai-adapter agent get <name>` | 🔴 展開先が間違っている。ファイルは `~/.ai-adapter/.github/agents/` に作成される |
| `ai-adapter bin get <name>` | 🟠 同様の不具合の可能性あり（未確認） |
| `ai-adapter skill get <name>` | 🟠 同様の不具合の可能性あり（未確認） |

---

## 修正方針（案）

出力先のパスを現在位置にする

    プロジェクトの `.github/agents/` にコピー

展開先を CLI オプションで指定できるようにする

```bash
ai-adapter agent get reviewer.agent --project-dir /Users/bookair18/OS/media/05_claude
```
---

## 関連ファイル

| ファイル | 役割 |
|---------|------|
| `/Users/bookair18/OS/home/Codes/ai-adapter-01/src/ai_adapter/` | ai-adapter 本体のソースコード |
| `/Users/bookair18/OS/home/Codes/ai-adapter-01/src/ai_adapter/agent.py` | agent サブコマンドの実装（`get` の展開先ロジック） |
| `/Users/bookair18/.ai-adapter/` | ai-adapter のデータディレクトリ（原本） |
| `documents/plans/ai_adapter_integration_guide.md` | インテグレーションガイド（本バグの注意事項を追記予定） |

---

## 受け入れ条件

- [ ] `ai-adapter agent get reviewer.agent` をプロジェクトルートで実行すると `.github/agents/reviewer.agent.md` に展開される
- [ ] プロジェクトルート外で実行した場合でもエラーメッセージが表示される（サイレント失敗しない）
- [ ] `ai-adapter bin get` / `ai-adapter skill get` も同様に正しいパスに展開される
- [ ] プロジェクトルート検出の優先順位がドキュメント化されている
