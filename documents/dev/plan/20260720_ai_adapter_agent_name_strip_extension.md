# ai-adapter agent 登録名に .agent 拡張子が残る問題

**作成日**: 2026-07-20
**ステータス**: 🐛 確認済み（未修正）
**対象**: `ai-adapter v0.3.0`（`/Users/bookair18/OS/home/Codes/ai-adapter-01/`）

---

## 概要

ファイル名 `reviewer.agent.md` を `ai-adapter agent add` で登録すると、登録名が `reviewer.agent` になる。その結果、直感的な `ai-adapter agent get reviewer` が使えず、`ai-adapter agent get reviewer.agent` と打たなければならない。

---

## 問題の詳細

### 登録時の動作

```bash
ai-adapter agent add .github/agents/reviewer.agent.md
# → 登録名: "reviewer.agent"（.agent.md のうち .md だけ除去される）
```

### 期待する動作

```bash
ai-adapter agent add .github/agents/reviewer.agent.md
# → 登録名: "reviewer"（.agent.md 全体が除去される）
```

### 再現手順

```bash
# 現在の状態
ai-adapter agent list
# → reviewer.agent ← 余分な .agent が付いている

# 直感的な呼び出し → 失敗
ai-adapter agent get reviewer
# → エージェント 'reviewer' が見つかりません。

# 回避策 → 成功
ai-adapter agent get reviewer.agent
# → コピー成功
```

---

## 影響範囲

| エージェントファイル | 現在の登録名 | 本来期待する名前 |
|--------------------|-------------|----------------|
| `implementer.agent.md` | `implementer.agent` | `implementer` |
| `plan-architect.agent.md` | `plan-architect.agent` | `plan-architect` |
| `product-manager.agent.md` | `product-manager.agent` | `product-manager` |
| `researcher.agent.md` | `researcher.agent` | `researcher` |
| `reviewer.agent.md` | `reviewer.agent` | `reviewer` |
| `reviewer-large.agent.md` | `reviewer-large.agent` | `reviewer-large` |
| `super-hacker.agent.md` | `super-hacker.agent` | `super-hacker` |

全7件が影響を受ける。

---

## 修正方針（案）
*.agent.mdのnameプロパティ（例: Implementer）を読み取りその名前を登録名とする
*.agent.mdの保存する際に事前にフォーマットバリデーションする

---

## 関連ファイル

| ファイル | 役割 |
|---------|------|
| `/Users/bookair18/OS/home/Codes/ai-adapter-01/src/ai_adapter/agent.py` | `agent add` / `agent get` の実装 |
| `documents/plans/dev/20260720_ai_adapter_agent_get_deploy_path.md` | 関連イシュー（展開先パス問題） |
| `documents/plans/ai_adapter_integration_guide.md` | インテグレーションガイド |

---

## 受け入れ条件

- [ ] `ai-adapter agent add reviewer.agent.md` → 登録名が `reviewer` になる
- [ ] `ai-adapter agent get reviewer` → そのまま見つかる
- [ ] `ai-adapter agent get reviewer.agent` → これでも見つかる（後方互換性）
- [ ] 全7エージェントの再登録が完了している
- [ ] 既存の他の拡張子（`.yaml`, `.py`, `.sh` など）で登録したファイルに影響がない
