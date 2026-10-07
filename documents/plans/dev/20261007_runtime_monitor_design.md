# 開発設計書: AI Adapter Runtime Monitor

- 日付: 2026-10-07
- 作成者: Product Manager
- 状態: ドラフト（Plan Architect レビュー A 反映済み・B 待ち）
- 上位計画: `documents/plans/user/AI Adapter Runtime Monitor.md`（仕様書）
- 対象バージョン: v0.25.0（PoC）
- 制約: ドキュメント作成フェーズ（実装は別途 Implementer 依頼）
- レビュー履歴: Plan Architect A（Critical 0 / Major 8 / Minor 9）— Major #1-#5 反映済み

---

## 1. 目的

既存 `ai-adapter` CLI に **Runtime Monitoring 機能**を追加する。
Orca / VS Code / Zed の 3 ホストで実行されている AI Agent Session を外部から発見・監視する。

**最重要評価軸**: `Coverage > Precision > Features > UI`

**Core Design Rule**: 1 ホストを完成させない。3 ホストすべてで Session Discovery を成立させる Vertical Slice を先に構築する。

---

## 2. アーキテクチャ

### 2.1 レイヤ分離

```
ai-adapter
│
├── Configuration Plane（既存・変更なし）
│   ├── agent / skill / prompt / mcp / env / scan / doctor
│
└── Runtime Plane（新規）
    │
    └── monitor
```

| Plane | 質問 | 例 |
|-------|------|-----|
| Configuration | What exists? | scan, doctor |
| Runtime | What is happening now? | monitor |

**providers/ に Runtime Monitoring コードを追加しない。**

### 2.2 ディレクトリ構造

```
src/ai_adapter/
├── commands/
│   └── monitor.py          # CLI エントリポイント
│
└── runtime/
    ├── __init__.py
    ├── models.py           # Canonical Runtime Model（dataclass）
    ├── normalizer.py       # raw → canonical 変換
    ├── registry.py         # Adapter 登録・解決
    ├── watcher.py          # --watch モード（簡易 TUI）
    │
    └── adapters/
        ├── __init__.py
        ├── base.py         # RuntimeAdapter ABC
        ├── orca.py         # Orca Host Adapter
        ├── vscode.py       # VS Code Host Adapter
        └── zed.py          # Zed Host Adapter
```

### 2.3 Canonical Runtime Model

```python
# runtime/models.py

from enum import Enum

class RuntimeStatus(str, Enum):
    """Canonical status values. Serialization uses lowercase."""
    WORKING = "working"
    WAITING = "waiting"
    BLOCKED = "blocked"
    DONE = "done"
    IDLE = "idle"
    UNKNOWN = "unknown"

class RuntimeConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class RuntimeSource(str, Enum):
    """Canonical observation-source vocabulary."""
    HOOK = "hook"
    CLI = "cli"
    API = "api"
    ACP = "acp"
    METADATA = "metadata"
    TERMINAL = "terminal"
    FILE = "file"
    PROCESS = "process"
    HEURISTIC = "heuristic"

@dataclass
class RuntimeSession:
    session_id: str
    host: str            # orca / vscode / zed / ...
    agent: str           # codex / claude / opencode / copilot / zed-agent
    project: str
    workspace: str
    status: RuntimeStatus
    activity: str        # human-readable current activity
    needs_user: bool | None   # True / False / None(unknown)
    started_at: datetime | None
    last_activity_at: datetime | None
    source: RuntimeSource
    confidence: RuntimeConfidence

@dataclass
class RuntimeCapabilities:
    host: str
    discover: str        # YES / PARTIAL / NO / UNKNOWN
    project: str
    agent: str
    activity: str
    working: str
    waiting: str
    done: str
    needs_user: str
```

**重要**: `ide` ではなく `host` を使用する（将来 Terminal / tmux / CI Agent 等を追加可能にするため）。

**normalizer.py の責務**: 3 アダプタ共通の正規化語彙（status/confidence/source の Enum 定数、§2.5 の Source→Confidence マッピング表、JSON シリアライザ）の単一情報源とする。Adapter には raw → `RuntimeSession` のマッピングを閉じる。

### 2.4 Status Model

| Status | Meaning |
|--------|---------|
| WORKING | Agent が処理中 |
| WAITING | User input / approval 待ち |
| BLOCKED | Error / permission 等で進行不能 |
| DONE | Task 完了 |
| IDLE | Session は存在するが活動していない |
| UNKNOWN | 状態を信頼できる方法で判定できない |

**状態を推測で断定しない。判断できない場合は必ず `UNKNOWN` とする。**

### 2.4.1 P2 用の ACTIVE/INACTIVE/UNKNOWN 導出規則

| 表示値 | 対応する Canonical Status |
|--------|--------------------------|
| ACTIVE | working / waiting / blocked |
| INACTIVE | idle / done |
| UNKNOWN | unknown |

**シリアライズ値は小文字に統一する**（Enum の値が小文字であるため自然に担保される）。

### 2.5 Confidence Model

| Source | Confidence |
|--------|------------|
| Official Hook | HIGH |
| Official CLI / API | HIGH |
| ACP Event | HIGH |
| Official Session Metadata | HIGH / MEDIUM |
| Terminal Activity | MEDIUM |
| File Activity | MEDIUM / LOW |
| Process Detection | LOW |
| Heuristic | LOW |

### 2.6 Observation Priority

```
1. Official Semantic Event
2. Official API / CLI
3. Official Session Metadata
4. Activity Observation
5. Process Observation
```

可能な限り上位の Source を使用する。

---

## 3. Runtime Adapter Contract

```python
# runtime/adapters/base.py

from abc import ABC, abstractmethod

class RuntimeAdapter(ABC):
    """Common interface for all host adapters."""

    @abstractmethod
    def discover(self) -> list[RuntimeSession]:
        """Discover running or existing agent sessions."""

    @abstractmethod
    def inspect(self, session_id: str) -> RuntimeSession | None:
        """Return detailed session information."""

    @abstractmethod
    def capabilities(self) -> RuntimeCapabilities:
        """Describe observable capabilities."""

    @property
    @abstractmethod
    def host_name(self) -> str:
        """Return the host identifier (e.g. 'orca', 'vscode', 'zed')."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True when the host CLI/API is reachable."""
```

**Host 差分を Core へ漏らさない。**

**Availability / Error / Timeout 契約（PA Review A Major #1）**:
- `discover()` は例外を送出しない。利用不可の場合は空リストを返す
- registry は `is_available() == False` のホストをスキップする
- `capabilities()` はホスト不在でも宣言を返す（値は `NO` / `UNKNOWN`）
- ホスト CLI の timeout は `unavailable` / `partial` として報告し、CLI レイヤへ例外を渡さない
- 全サブプロセス実行は list 引数・`shell=False`・timeout 必須（runtime 配下の共通ゲートウェイ経由）
- 3 ホストの discovery は `concurrent.futures` で並行実行する
- watch 周期中の結果はキャッシュし、`--interval` オプション（デフォルト 3 秒）で制御する

---

## 4. Host Adapter 設計

**注意**: `providers/vscode.py` / `providers/zed.py` とは別モジュール（設定変換 vs Runtime 監視）。各 adapter の docstring に区別を明記すること。

### 4.1 Orca Adapter (`runtime/adapters/orca.py`)

**Observation Priority**:
1. Orca Agent Hooks
2. Orca CLI JSON
3. Orca Terminal State
4. Process Observation

**調査対象**（実地確認済み）:
```bash
orca status --json
orca worktree ps --json          # workspaceStatus: "in-progress", lastActivityAt
orca worktree current --json
orca terminal list --json        # agentIdentity, worktreePath, lastOutputAt, preview
orca terminal show --terminal <handle> --json
orca agent hooks status --json
```

**取得可能フィールド（実地確認）**:
- `orca terminal list --json`: `agentIdentity`（例 `"opencode"`）, `worktreePath`, `lastOutputAt`, `preview`
- `orca worktree ps --json`: `workspaceStatus`（例 `"in-progress"`）, `lastActivityAt`

**P0–P2 の Orca 腿は実装可能と判断。**

**方針**: 公式インターフェースを最優先。Orca 内部ファイルの解析は公式で取得できない場合のみ検討。

### 4.2 VS Code Adapter (`runtime/adapters/vscode.py`)

**Observation Priority**:
1. Agent Hooks
2. Agent Session Metadata
3. Supported Extension / API interface
4. Terminal Activity
5. Process Observation

**対象**: VS Code Agent / Codex / Claude / Copilot

**方針**: Proposed API へ Core を直接依存させない。VSCodeAdapter 内部へ隔離。

### 4.3 Zed Adapter (`runtime/adapters/zed.py`)

**Observation Priority**:
1. ACP (Agent Client Protocol)
2. Zed Thread Metadata
3. Agent-specific Hooks
4. Terminal Activity
5. Process Observation

**方針**: External Agent は ACP を第一候補。ACP で Runtime State が十分取得できない場合、その事実自体を PoC 結果として記録する。無理に状態を推測しない。

### 4.4 Fallback Observation

公式インターフェースで取得できない場合のみ使用:
- `ps` / `pgrep` / `lsof`
- terminal activity
- file modification time
- session metadata timestamp

**Process 存在だけから WORKING / WAITING / DONE を判定してはならない。**

---

## 5. Event Model（Non-Goals: PoC 後）

**PoC では実装しない。** ポーリングで成立するため、イベント駆動は PoC 後の拡張とする（PA Review A Major #6）。

将来実装時に正規化するイベント:

```
SESSION_DISCOVERED / SESSION_STARTED
AGENT_WORKING / AGENT_WAITING / AGENT_BLOCKED / AGENT_DONE / AGENT_IDLE
USER_ACTION_REQUIRED
ACTIVITY
SESSION_ENDED
```

Host 固有 Event 名を Core へ漏らさない。

---

## 6. CLI 仕様

### 6.1 デフォルトモード

```bash
ai-adapter monitor
```

```text
HOST      PROJECT                    AGENT       STATUS       AGE
───────────────────────────────────────────────────────────────
Orca      ec-cube-ai-chat            OpenCode    WORKING      14s
VSCode    kaseifu                    Codex       WAITING       2m
Zed       cannabinoid-trends         Claude      WORKING      31s
Zed       seo-operations             Zed Agent   IDLE          8m
```

### 6.2 Watch モード

```bash
ai-adapter monitor --watch
```

- 簡潔な TUI として継続更新
- **既定更新周期: 3 秒**（`--interval` オプションで変更可、1–3 秒範囲）
- Semantic Event を取得できる場合は即時反映可（PoC ではポーリングで十分）
- **TUI Framework 導入は PoC では不要**（`click.clear()` + `time.sleep` + 再描画ループ）
- **実装契約**:
  - Orca discovery は `orca terminal list --json` を主経路（1 コマンドで主要フィールド取得）
  - availability チェック結果はサイクル内キャッシュ（毎回 CLI を叩かない）
  - Ctrl+C で最終スナップショットを表示して終了
  - レンダラは純粋関数 `render(sessions) -> str` として分離（テスト可能性）

### 6.3 JSON モード

```bash
ai-adapter monitor --json
```

Canonical Model を JSON として出力。他ツール連携の基礎とする。

**JSON Envelope（仕様書 §22 準拠）**:
```json
{
  "sessions": [
    {
      "session_id": "abc123",
      "host": "orca",
      "agent": "opencode",
      "project": "ec-cube",
      "workspace": "/path/to/ec-cube",
      "status": "working",
      "activity": "Running tests",
      "needs_user": false,
      "started_at": "2026-10-06T18:32:00+09:00",
      "last_activity_at": "2026-10-06T18:41:12+09:00",
      "source": "hook",
      "confidence": "high"
    }
  ]
}
```

- datetime は ISO 8601（tz 保持、`None` → `null`）
- 空の場合は `{"sessions": []}`
- `session_id` はホストスコープ。外部連携キーは `(host, session_id)` の複合
- **JSON 値は lowercase**（`status: "working"`）。テーブル表示のみ UPPERCASE（`WORKING`）
- `--watch` + `--json` / `--capabilities` の併用は usage error
- `--debug` 出力は常に stderr（stdout パイプを壊さない）

### 6.4 Capability モード

```bash
ai-adapter monitor --capabilities
```

**値は `adapter.capabilities()` 由来の実測値。CLI 層でハードコードしない。**

```text
CAPABILITY       ORCA       VSCODE       ZED
─────────────────────────────────────────────
Discover         YES        YES          YES
Project          YES        YES          YES
Agent            YES        YES          YES
Activity         YES        YES          YES
Working          YES        YES          PARTIAL
Waiting          YES        YES          PARTIAL
Done             YES        YES          PARTIAL
Needs User       YES        YES          UNKNOWN
```

### 6.5 Debug モード

```bash
ai-adapter monitor --debug
```

「なぜその状態と判定したか」を追跡できる出力を提供する。

---

## 7. 実装フェーズ（BDD タスク分解）

### Phase P0-Spike: Discovery 経路検証（タイムボックス 1 日）

**目的**: VS Code / Zed の Session Discovery 経路を実地検証する。

**検証対象**:
- **Orca ✅ 検証済み**: `orca terminal list --json` に `agentIdentity` / `worktreePath` / `lastOutputAt` / `preview` が含まれる。`orca worktree ps --json` に `workspaceStatus: "in-progress"` / `lastActivityAt` が含まれる。設計 §4.1 の 6 コマンドは全て実在。
- **VS Code ⚠️ 未検証**: `code --status` はプロセス/GPU 診断のみ。発見経路の候補:
  - `code --list-extensions` + 拡張の session API
  - VS Code の `.vscode/` プロジェクトメタデータ
  - プロセス観測（fallback）
- **Zed ⚠️ 未検証**: `zed --help` に status/session 系コマンドなし。候補:
  - ACP (Agent Client Protocol) 接続
  - Zed の内部メタデータ（`~/.config/zed/` 配下）
  - プロセス観測（fallback）

**成果物**: 各ホストの discovery 経路と取得可能フィールドの記録。fallback で到達可能な場合はその旨を明記。

### Phase P0: Discovery（最重要）

**期待する振る舞い**:
- 入力: `ai-adapter monitor`（Orca / VS Code / Zed のいずれかに Session が存在）
- 応答: その Session を 1 件以上発見し、Canonical Model で出力する
- 入力: どの Host にも Session が存在しない
- 応答: 空の一覧を表示（エラーにしない）

**受け入れ条件**:
- AC1: Orca / VS Code / Zed の 3 つすべてで Session Discovery が可能
  - 公式インターフェースまたは fallback（`source=process`, `confidence=low`）で発見できれば合格
- AC2: Host がインストールされていない環境でも crash しない
- AC3: `discover()` が返す Session は Canonical Model 形式
- AC4: 判定できない場合は `status="unknown"` とする
- AC5: **最小出力パス**（`runtime_session_to_dict()` による最小 `--json` + プレーン表）が動作する

**DoD**: P0 が完了した時点で、`monitor --json`（最小 envelope）とプレーン表出力が 3 ホスト分の Session を表示できること。

**データ（仕様例）**:
```python
RuntimeSession(
    session_id="abc123",
    host="orca",
    agent="opencode",
    project="ec-cube",
    workspace="/path/to/ec-cube",
    status="unknown",
    activity="",
    needs_user=None,
    started_at=None,
    last_activity_at=None,
    source="cli",
    confidence="high",
)
```

---

### Phase P1: Identity

**期待する振る舞い**:
- 入力: `ai-adapter monitor --json`
- 応答: 各 Session に以下が含まれる
  - `host` / `agent` / `project` / `workspace` / `session_id`

**受け入れ条件**:
- AC1: 3 ホストすべてで Host / Project / Agent / Session ID / Workspace を取得可能
- AC2: Host と Agent が別フィールドで区別される

---

### Phase P2: Activity

**期待する振る舞い**:
- 入力: `ai-adapter monitor`
- 応答: 各 Session の状態を `ACTIVE` / `INACTIVE` / `UNKNOWN` に分類

**受け入れ条件**:
- AC1: 3 ホストすべてで ACTIVE / INACTIVE / UNKNOWN を判定可能
- AC2: 判定根拠が `source` フィールドで追跡可能

**ここで PoC Minimum Success。**

---

### Phase P3: Semantic Status

**期待する振る舞い**:
- 入力: `ai-adapter monitor`
- 応答: 取得可能な Host について `working` / `waiting` / `blocked` / `done` / `idle` / `unknown` に正規化

**受け入れ条件**:
- AC1: 各 Adapter が Observation Priority に従って Source を選択
- AC2: 判定できない場合は `unknown`（推測しない）
- AC3: `confidence` フィールドが Source に応じて HIGH / MEDIUM / LOW を返す

---

### Phase P4: Human Attention

**期待する振る舞い**:
- 入力: `ai-adapter monitor`
- 応答: 各 Session の `needs_user` フィールドが `true` / `false` / `null`(unknown) を返す

**受け入れ条件**:
- AC1: `needs_user` が Status と独立した属性
- AC2: `BLOCKED` + `needs_user=true` の組み合わせも表現可能

---

### Phase P5: Output

**期待する振る舞い**:
- 入力: `ai-adapter monitor --json`
- 応答: Canonical Model の JSON 配列を出力
- 入力: `ai-adapter monitor --watch`
- 応答: 1–3 秒周期で画面を更新
- 入力: `ai-adapter monitor --capabilities`
- 応答: 各 Host の capability テーブルを出力
- 入力: `ai-adapter monitor --debug`
- 応答: 判定根拠を追跡可能なログを出力

**前提**: 最小出力パス（プレーン表 + 最小 `--json`）は P0 DoD で完成済み。本フェーズは残りの出力仕様を完成させる。

**P0-P2 実装時点の延期範囲（QA 指摘反映）**: `--watch`（runtime/watcher.py）/ `--capabilities` / `--debug` は未実装。P5 で実装する。

**受け入れ条件**:
- AC1: 全モードが動作し、Host 未インストール環境でも crash しない
- AC2: `--json` 出力が Canonical Model 仕様に準拠（§6.3 JSON 契約参照）
- AC3: `--capabilities` の値は各 adapter の `capabilities()` 由来。CLI 層でハードコードしない
- AC4: ホスト未インストール時は capability 値を `NO` / `UNKNOWN` とする
- AC5: `--watch` は `render(sessions) -> str` 関数を分離し、ループ本体に sleep 注入可能な構造とする
- AC6: 既定更新周期 3 秒、Ctrl+C で最終スナップショット表示
- AC7: `--watch` + `--json` / `--capabilities` の併用は usage error
- AC8: `--debug` 出力は常に stderr（stdout パイプを壊さない）

---

## 8. テスト計画

### 必須テスト

| テスト | 内容 |
|--------|------|
| Canonical Model | dataclass の構造・シリアライズ |
| Status Normalization | raw → canonical 変換 |
| Adapter Interface | 全 Adapter が共通 interface を実装 |
| Orca raw → Canonical | モックデータでの変換 |
| VS Code raw → Canonical | モックデータでの変換 |
| Zed raw → Canonical | モックデータでの変換 |
| UNKNOWN fallback | 判定不能時の挙動 |
| JSON output | 出力形式の検証 |
| Host 未インストール | crash しないためのテスト |
| Watcher テスト可能性 | `render()` 分離・iteration 上限・`--interval` 注入 |
| Fixture / golden-file | `tests/fixtures/runtime/` に host ごとの raw data を配置 |
| CLI 全モード | CliRunner で「空一覧」「ホスト未インストール」「全 5 モード」を検証 |

### テスト方針

- Host がインストールされていない環境でも test suite が失敗しない設計
- Adapter テストは fixture / mocked raw data を使用
- `scripts/run_tests.sh` 経由で実行

---

## 9. 依存ポリシー

**PoC では依存パッケージ追加を最小化する。**

既存:
- Python 3.10+
- Click
- PyYAML

**標準ライブラリで実現可能なものについて、新規 dependency を追加しない。**
**TUI Framework は PoC では導入しない。**

---

## 10. セーフティ / ステイビリティ

監視機能は原則 **Read Only** とする。

**実行してはならないこと**:
- Agent への入力
- Agent Session 変更
- IDE 設定変更
- Agent 停止
- Terminal command injection
- Permission approval

公式 Hook 導入等で設定変更が必要な場合は:
```
detect → report → user explicitly enables
```

`monitor` 実行だけで既存 IDE 設定を書き換えてはならない。

---

## 11. 既存機能互換性

既存機能を壊してはならない。最低限以下を維持:
- `ai-adapter scan` / `doctor` / `agent` / `skill` / `mcp` / `setup`

Runtime Monitoring の追加は **additive change** とする。

---

## 12. Non-Goals（PoC では実装しない）

- Web UI / GUI / macOS Menu Bar
- Agent start / stop / Prompt send / Permission approval
- Git operation
- Token usage / Cost tracking / CPU / Memory monitoring
- Persistent history / SQLite / Analytics
- Remote monitoring / Notification

要求されていない機能を追加しない。

---

## 12.5 Registry 方針

PoC ではモジュールレベルの静的リストで十分。`ai_adapter.plugins` entry-point 経由の動的ロードは行わない（過剰設計）。

```python
# runtime/registry.py
ADAPTER_TYPES: list[type[RuntimeAdapter]] = [OrcaAdapter, VSCodeAdapter, ZedAdapter]

def create_adapters() -> list[RuntimeAdapter]:
    """Instantiate all adapters. Skip unavailable hosts without raising."""
    adapters = []
    for cls in ADAPTER_TYPES:
        try:
            adapter = cls()
            if adapter.is_available():
                adapters.append(adapter)
        except Exception:
            continue  # 1 アダプタ故障で全体を落とさない
    return adapters
```

- `is_available()` は `shutil.which()` 等でホスト CLI の存在を確認（先例: `npx.py`, `doctor.py`）
- 1 アダプタの例外で全体をクラッシュさせない（例外分離）

## 13. 変更対象ファイル

| ファイル | 変更内容 |
|----------|----------|
| `src/ai_adapter/commands/monitor.py` | **新規** — CLI エントリポイント |
| `src/ai_adapter/runtime/__init__.py` | **新規** |
| `src/ai_adapter/runtime/models.py` | **新規** — Canonical Model |
| `src/ai_adapter/runtime/normalizer.py` | **新規** — raw → canonical 変換 |
| `src/ai_adapter/runtime/registry.py` | **新規** — Adapter 登録・解決 |
| `src/ai_adapter/runtime/watcher.py` | **新規** — --watch モード |
| `src/ai_adapter/runtime/adapters/__init__.py` | **新規** |
| `src/ai_adapter/runtime/adapters/base.py` | **新規** — RuntimeAdapter ABC |
| `src/ai_adapter/runtime/adapters/orca.py` | **新規** |
| `src/ai_adapter/runtime/adapters/vscode.py` | **新規** |
| `src/ai_adapter/runtime/adapters/zed.py` | **新規** |
| `src/ai_adapter/cli.py` | `monitor` コマンド登録 |
| `tests/test_runtime_models.py` | **新規** |
| `tests/test_runtime_adapters.py` | **新規** |
| `tests/test_monitor_cli.py` | **新規** |
| `README.md` | monitor セクション追加 |
| `CHANGELOG.md` | Unreleased エントリ追加 |

---

## 14. PoC Report（実装完了時に提出）

実装完了時、コードだけで終了してはならない。以下を報告する:

```
Cross-IDE Runtime Monitoring PoC

                    ORCA      VSCODE      ZED
──────────────────────────────────────────────
Session discovery
Project
Agent
Workspace
Activity
Working
Waiting
Done
Needs user

Observation source: ...
Known limitations: ...
Unsupported observations: ...
```

**UNKNOWN / PARTIAL / NOT AVAILABLE を隠さない。**

---

## 15. アーキテクチャ原則（最終確認）

```
ai-adapter scan     → What exists?
ai-adapter doctor   → Is it healthy?
ai-adapter monitor  → What is happening now?
```

**本プロジェクトの価値は個々のAgent監視ではない。**
**異なるHostに分散したAI Agentを、単一のRuntime Observability Layerから監視できることにある。**
