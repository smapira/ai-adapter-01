# Issue #1: `skill get-all` の docstring が古いパスを指している

> **優先度**: 🔴 高  
> **種類**: バグ（ドキュメント不整合）  
> **対象ファイル**: `src/ai_adapter/skill.py`  
> **対象行**: 331行目付近

---

## 問題

`skill get-all` コマンドの docstring が `.claude/skills/` を指しているが、実際の出力先は `.github/skills/` に変更済み（v0.4.1）。

```python
def skill_get_all(force: bool, project_dir: str | None) -> None:
    """全ての登録済みスキルを .claude/skills/ にコピーする。"""  # ← 古いパス
```

## 影響

- `ai-adapter skill get-all --help` を実行したユーザーが誤ったパスを参照する
- CHANGELOG には `.github/skills/` に統一と明記されているため、ドキュメントと実装の矛盾が生じる

## 修正内容

docstring を `.github/skills/` に更新する。

```python
def skill_get_all(force: bool, project_dir: str | None) -> None:
    """全ての登録済みスキルを .github/skills/ にコピーする。"""
```

## 検証

- [ ] `ai-adapter skill get-all --help` で `.github/skills/` が表示される
- [ ] 全テスト PASS
