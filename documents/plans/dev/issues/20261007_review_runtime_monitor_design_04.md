# Runtime Monitor 設計書レビュー: runtime/registry.py がファイル一覧にあるが設計本文が存在しない

## 優先度
🟡 Major

## 対象
- 計画書: `documents/plans/dev/20261007_runtime_monitor_design.md`（§2.2 line 56 / §3 ABC / §13 line 508）
- 上位仕様書: `documents/plans/user/AI Adapter Runtime Monitor.md`（§12 Runtime Architecture / §14 Adapter Contract）
- 関連ファイル: `src/ai_adapter/cli.py:349-371`（`main.add_command` 静的登録）、`src/ai_adapter/providers/__init__.py`（空）、`src/ai_adapter/npx.py:20` / `src/ai_adapter/doctor.py:451-460`（`shutil.which` 可用性プローブ先例）

## 指摘事項
1. **registry.py が未設計:** §2.2 ディレクトリツリーと §13 変更対象ファイルに「Adapter 登録・解決」として登場するが、本文に設計節がなく、登録方式・解決手順・可用性判定・例外時の挙動が一切書かれていない。
2. **既存コードベースの provider 登録パターンとの関係が未整理:** 既存 CLI の登録は `cli.py:349-371` の静的 import + `main.add_command(...)` 一式で、動的レジストリも entry-point プラグインも存在しない（`providers/__init__.py` は空。`pyproject.toml` の `ai_adapter.plugins` entry point も空）。runtime adapter の解決は CLI コマンド登録とは別責務なので registry 自体は妥当だが、この区別が設計書に書かれておらず、過剰設計（プラグイン式自動発見等）に振れやすい。
3. **Host 可用性判定の契約がない:** `RuntimeAdapter` ABC（§3）に「Host がインストール済みかどうか」を判定する手段がない。P0 AC2 / P5 AC1「Host がインストールされていない環境でも crash しない」の実現方法が未定義。既存の先例は `shutil.which`（`npx.py:20`、`doctor.py:451-460`）。

## 改善案
設計書に「§3.x Registry」節を追加し、最小契約を明文化する:

```python
# runtime/registry.py — PoC では静的リスト + 可用性プローブのみ
ADAPTER_TYPES: list[type[RuntimeAdapter]] = [OrcaAdapter, VscodeAdapter, ZedAdapter]

def available_adapters() -> list[RuntimeAdapter]:
    adapters = []
    for cls in ADAPTER_TYPES:
        try:
            adapter = cls()
            if adapter.is_available():
                adapters.append(adapter)
        except Exception:
            continue  # 1 アダプタの故障で monitor 全体を落とさない
    return adapters
```

- **ABC に `is_available() -> bool` を追加**（orca: `shutil.which("orca")`、VS Code / Zed: CLI + アプリ/設定ディレクトリ存在プローブ。判定ロジックは各 adapter 内に閉じる）
- 1 アダプタ例外時は他を継続 + `--debug` に記録（P5 AC1）
- **PoC では entry-point プラグイン機構（`ai_adapter.plugins`）へ runtime adapter を接続しない** — Configuration Plane 用の既存機構であり PoC スコープ外
- CLI コマンド登録は §13 記載どおり `main.add_command(cmd_monitor)`（既存パターン準拠）で問題なし。registry はその内部機構であり別物であることを設計書に一言記す

## 備考
「registry が必要か」への回答: はい。3 ホスト × 未インストール環境対応 × 例外分離という要件は、コアからの直接呼び出しよりレジストリ経由が素直。ただし「解決」の語が示す以上の仕組み（動的発見・設定ファイル由来の登録等）は PoC では不要。
