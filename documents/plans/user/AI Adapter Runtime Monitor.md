# AI Adapter Runtime Monitor — Design Specification

## 1. Overview

既存プロジェクト `ai-adapter` に、AI Agentの実行状態を横断監視する **Runtime Monitoring機能**を追加する。

Repository:

```text
https://github.com/smapira/ai-adapter-01
```

新規ツールを作成しない。

既存CLIへ以下を追加する。

```bash
ai-adapter monitor
```

本機能はAgentを操作するControl Planeではない。

**Observability Plane** として実装する。

---

# 2. Vision

現在、AI Agentは複数のHost上で並列実行される。

対象Host:

```text
Orca
VS Code
Zed
```

さらに各Host上では異なるAgent Harnessが動作する。

例:

```text
Orca
 ├── OpenCode
 ├── Codex
 └── Claude

VS Code
 ├── Codex
 ├── Claude
 └── Copilot

Zed
 ├── Claude
 ├── Codex
 └── OpenCode
```

ユーザーは各IDEを個別に確認するのではなく、

```text
どのAgentが存在するか
何をしているか
現在動いているか
停止しているか
人間の入力を待っているか
```

をMac全体で俯瞰できる必要がある。

---

# 3. Existing Architecture

既存 `ai-adapter` は主にConfiguration Planeを担当している。

```text
ai-adapter
│
├── agent
├── skill
├── prompt
├── instruction
├── mcp
├── env
├── setup
├── scan
└── doctor
```

既存機能の責務は維持する。

今回Runtime Planeを追加する。

```text
ai-adapter
│
├── Configuration Plane
│   │
│   ├── agent
│   ├── skill
│   ├── prompt
│   ├── mcp
│   ├── env
│   ├── scan
│   └── doctor
│
└── Runtime Plane
    │
    └── monitor
```

責務:

```text
scan
    What exists?
    何がインストール・設定されているか

doctor
    Is it healthy?
    設定・環境が正常か

monitor
    What is happening now?
    今何が実行されているか
```

この境界を崩さないこと。

---

# 4. PoC Objective

PoCの目的はUI開発ではない。

検証対象は以下のみ。

> Orca / VS Code / Zed の3環境で実行されているAgent Sessionを外部から発見・監視できるか。

最重要評価軸:

```text
Coverage > Precision > Features > UI
```

一つのHostを完全対応してから次へ進んではならない。

最初に3環境すべてでSession Discoveryを成立させる。

---

# 5. PoC Success Criteria

以下すべてを満たした場合のみPoC成功とする。

## Mandatory

Orca / VS Code / Zedすべてについて:

```text
Session Discovery
Project Identification
Agent Identification
Activity Detection
```

が可能であること。

最低限、状態を以下へ分類できること。

```text
ACTIVE
INACTIVE
UNKNOWN
```

例:

```text
HOST      PROJECT                  AGENT       STATE
──────────────────────────────────────────────────────
Orca      ec-cube                  OpenCode    ACTIVE
VSCode    kaseifu                  Codex       ACTIVE
Zed       cannabinoid-trends       Claude      INACTIVE
```

---

# 6. Target Status Model

取得可能であれば、より詳細な状態へ正規化する。

```text
WORKING
WAITING
BLOCKED
DONE
IDLE
UNKNOWN
```

Definition:

| Status | Meaning |
|---|---|
| WORKING | Agentが処理中 |
| WAITING | User input / approval待ち |
| BLOCKED | Error / permission等で進行不能 |
| DONE | Task完了 |
| IDLE | Sessionは存在するが活動していない |
| UNKNOWN | 状態を信頼できる方法で判定できない |

重要:

**状態を推測で断定しない。**

判断できない場合は必ず `UNKNOWN` とする。

---

# 7. Needs User

Statusとは独立した属性とする。

```text
needs_user:

true
false
unknown
```

例えば:

```text
WAITING
needs_user=true
```

だけではなく、

```text
BLOCKED
needs_user=true
```

もあり得る。

最終的な監視用途では `needs_user` が最重要シグナルになる。

---

# 8. Canonical Runtime Model

Host固有データをCLIへ直接渡してはならない。

必ずCanonical Modelへ変換する。

例:

```json
{
  "session_id": "abc123",
  "host": "zed",
  "agent": "claude",
  "project": "japan-cannabinoid-trends",
  "workspace": "/path/to/project",
  "status": "working",
  "activity": "Running tests",
  "needs_user": false,
  "started_at": "2026-10-06T18:32:00+09:00",
  "last_activity_at": "2026-10-06T18:41:12+09:00",
  "source": "acp",
  "confidence": "high"
}
```

`ide` ではなく `host` を使用する。

理由:

将来的に以下を追加できるため。

```text
Terminal
tmux
OpenClaw
Remote Host
CI Agent
```

---

# 9. Host and Agent Separation

以下を混同してはならない。

## Host

Agentが実行されている環境。

```text
orca
vscode
zed
```

## Agent / Harness

実際にTaskを実行するAgent。

```text
codex
claude
opencode
copilot
zed-agent
```

Canonical Modelでは必ず別フィールドにする。

---

# 10. Confidence Model

状態の取得方法によって信頼度が異なる。

Canonical Modelに必ず以下を持たせる。

```text
HIGH
MEDIUM
LOW
```

目安:

```text
Official Hook
    HIGH

Official CLI / API
    HIGH

ACP Event
    HIGH

Official Session Metadata
    HIGH / MEDIUM

Terminal Activity
    MEDIUM

File Activity
    MEDIUM / LOW

Process Detection
    LOW

Heuristic
    LOW
```

例:

```text
Zed / Claude
WORKING
source=acp
confidence=HIGH
```

対して:

```text
VSCode / Codex
WORKING
source=process
confidence=LOW
```

を区別できること。

---

# 11. Observation Priority

各Adapterは以下の優先順位で情報源を選択する。

```text
1. Official Semantic Event
2. Official API / CLI
3. Official Session Metadata
4. Activity Observation
5. Process Observation
```

概念:

```text
Semantic
   ↓
Metadata
   ↓
Activity
   ↓
Process
```

可能な限り上位のSourceを使用する。

---

# 12. Runtime Architecture

新規Runtime Layerを作成する。

```text
src/
└── ai_adapter/
    │
    ├── commands/
    │   ├── ...
    │   └── monitor.py
    │
    └── runtime/
        │
        ├── __init__.py
        ├── models.py
        ├── normalizer.py
        ├── registry.py
        │
        └── adapters/
            ├── __init__.py
            ├── base.py
            ├── orca.py
            ├── vscode.py
            └── zed.py
```

既存 `providers/` へRuntime Monitoringコードを追加しない。

---

# 13. Providers vs Runtime Adapters

既存:

```text
providers/
```

責務:

```text
設定をどう変換・配置するか
```

例:

```text
AGENTS.md生成
MCP設定変換
OpenCode設定生成
```

新規:

```text
runtime/adapters/
```

責務:

```text
現在何が動いているか
```

例:

```text
Session discovery
Runtime status
Current activity
Needs-user detection
```

両者を混在させないこと。

---

# 14. Runtime Adapter Contract

全Host Adapterは共通interfaceを実装する。

Conceptual Interface:

```python
class RuntimeAdapter:

    def discover(self):
        """Discover running or existing agent sessions."""

    def inspect(self, session):
        """Return detailed session information."""

    def status(self, session):
        """Determine normalized runtime status."""

    def activity(self, session):
        """Return current/recent activity."""

    def capabilities(self):
        """Describe observable capabilities."""
```

実装方法は変更可能だが、Host差分をCoreへ漏らさないこと。

---

# 15. Orca Adapter

File:

```text
runtime/adapters/orca.py
```

Observation priority:

```text
1. Orca Agent Hooks
2. Orca CLI JSON
3. Orca Terminal State
4. Process Observation
```

調査対象例:

```bash
orca status --json
orca worktree ps --json
orca worktree current --json
orca terminal list --json
orca terminal show --terminal <handle> --json
orca agent hooks status --json
```

取得可能な公式情報を最優先する。

Orca内部ファイルの解析は、公式インターフェースで取得できない場合のみ検討する。

---

# 16. VS Code Adapter

File:

```text
runtime/adapters/vscode.py
```

Observation priority:

```text
1. Agent Hooks
2. Agent Session Metadata
3. Supported Extension / API interface
4. Terminal Activity
5. Process Observation
```

対象:

```text
VS Code Agent
Codex
Claude
Copilot
その他VS Codeが認識するAgent Session
```

Proposed APIへCoreを直接依存させない。

Proposed APIを使用する場合も、

```text
VSCodeAdapter
```

内部へ隔離すること。

---

# 17. Zed Adapter

File:

```text
runtime/adapters/zed.py
```

対象:

```text
Zed Agent
External Agent
Terminal Thread
```

Observation priority:

```text
1. ACP
2. Zed Thread Metadata
3. Agent-specific Hooks
4. Terminal Activity
5. Process Observation
```

External AgentについてはACPを第一候補とする。

例:

```text
Zed
 │
 ACP
 │
 ├── Claude
 ├── Codex
 └── OpenCode
```

ACPでRuntime Stateが十分取得できない場合、その事実自体をPoC結果として記録する。

無理に状態を推測しない。

---

# 18. Fallback Observation

公式インターフェースで取得できない場合のみ使用する。

候補:

```text
ps
pgrep
lsof

terminal activity
file modification time
session metadata timestamp
```

Process存在だけから、

```text
WORKING
WAITING
DONE
```

を判定してはならない。

Process Observerから確実に分かるのは原則:

```text
process exists
process does not exist
```

まで。

---

# 19. Event Model

取得できるイベントは可能な限り以下へ正規化する。

```text
SESSION_DISCOVERED
SESSION_STARTED

AGENT_WORKING
AGENT_WAITING
AGENT_BLOCKED
AGENT_DONE
AGENT_IDLE

USER_ACTION_REQUIRED

ACTIVITY

SESSION_ENDED
```

Host固有Event名をCoreへ漏らさない。

---

# 20. CLI Specification

新規Command:

```bash
ai-adapter monitor
```

標準出力例:

```text
HOST      PROJECT                    AGENT       STATUS       AGE
───────────────────────────────────────────────────────────────
Orca      ec-cube-ai-chat            OpenCode    WORKING      14s
VSCode    kaseifu                    Codex       WAITING       2m
Zed       cannabinoid-trends         Claude      WORKING      31s
Zed       seo-operations             Zed Agent   IDLE          8m
```

情報量を増やしすぎない。

---

# 21. Watch Mode

```bash
ai-adapter monitor --watch
```

簡潔なTUIとして継続更新する。

目標更新周期:

```text
1–3 seconds
```

Semantic Eventを取得できる場合は即時反映してよい。

高度なTUI Framework導入はPoCでは不要。

---

# 22. JSON Mode

機械可読出力:

```bash
ai-adapter monitor --json
```

Canonical ModelをJSONとして出力する。

例:

```json
{
  "sessions": [
    {
      "host": "orca",
      "agent": "opencode",
      "project": "ec-cube",
      "status": "working",
      "needs_user": false,
      "source": "orca-hook",
      "confidence": "high"
    }
  ]
}
```

将来的な他ツール連携の基礎とする。

---

# 23. Capability Mode

PoC検証用として必須。

```bash
ai-adapter monitor --capabilities
```

例:

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

値:

```text
YES
PARTIAL
NO
UNKNOWN
```

PoCの目的はこの表を実測によって埋めることでもある。

---

# 24. Debug Mode

必須。

```bash
ai-adapter monitor --debug
```

例:

```text
[Orca]
session: abc
source: agent-hook
raw-status: working
normalized-status: WORKING
confidence: HIGH

[VSCode]
session: def
source: agent-hook
raw-status: waiting
normalized-status: WAITING
confidence: HIGH

[Zed]
session: ghi
source: terminal-activity
raw-status: activity-detected
normalized-status: WORKING
confidence: MEDIUM
```

「なぜその状態と判定したか」を追跡できること。

---

# 25. Implementation Order

以下の順番を厳守する。

## Phase P0 — Discovery

```text
Orca
    ↓
1 Session発見

VS Code
    ↓
1 Session発見

Zed
    ↓
1 Session発見
```

**3つ成功するまでStatus詳細実装へ進まない。**

---

## Phase P1 — Identity

3環境について:

```text
Host
Project
Agent
Session ID
Workspace
```

を取得する。

---

## Phase P2 — Activity

3環境について:

```text
ACTIVE
INACTIVE
UNKNOWN
```

を判定する。

ここでPoC Minimum Success。

---

## Phase P3 — Semantic Status

可能なHostについて:

```text
WORKING
WAITING
BLOCKED
DONE
IDLE
UNKNOWN
```

へ拡張する。

---

## Phase P4 — Human Attention

```text
needs_user
```

を実装する。

---

## Phase P5 — Output

最後に:

```text
monitor
--json
--watch
--capabilities
--debug
```

を完成させる。

---

# 26. Explicit Non-Goals

PoCでは実装しない。

```text
Web UI
GUI
macOS Menu Bar

Agent start
Agent stop
Prompt send
Permission approval

Git operation

Token usage
Cost tracking
CPU monitoring
Memory monitoring

Persistent history
SQLite
Analytics
Remote monitoring
Notification
```

要求されていない機能を追加しない。

---

# 27. Dependency Policy

PoCでは依存パッケージ追加を最小化する。

既存:

```text
Python 3.10+
Click
PyYAML
```

標準ライブラリで実現可能なものについて、新規dependencyを追加しない。

TUI FrameworkはPoCでは導入しない。

---

# 28. Safety / Stability

監視機能は原則Read Onlyとする。

以下を実行してはならない。

```text
Agentへの入力
Agent Session変更
IDE設定変更
Agent停止
Terminal command injection
Permission approval
```

公式Hook導入等で設定変更が必要な場合は、

```text
detect
↓
report
↓
user explicitly enables
```

の順にする。

`monitor` 実行だけで既存IDE設定を書き換えてはならない。

---

# 29. Existing Feature Compatibility

既存機能を壊してはならない。

最低限:

```text
ai-adapter scan
ai-adapter doctor
ai-adapter agent
ai-adapter skill
ai-adapter mcp
ai-adapter setup
```

等の既存CLI behaviorを維持する。

Runtime Monitoringの追加はadditive changeとする。

---

# 30. Testing

最低限以下をテストする。

```text
Canonical Model

Status Normalization

Adapter Interface

Orca raw data → Canonical

VS Code raw data → Canonical

Zed raw data → Canonical

UNKNOWN fallback

JSON output
```

Hostがインストールされていない環境でもtest suiteが失敗しない設計にする。

Runtime Adapterのテストではfixture / mocked raw dataを使用可能とする。

---

# 31. Required PoC Report

実装完了時、コードだけで終了してはならない。

以下を報告する。

```text
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

Observation source:

Orca:
...

VS Code:
...

Zed:
...

Known limitations:
...

Unsupported observations:
...
```

特に、

```text
UNKNOWN
PARTIAL
NOT AVAILABLE
```

を隠さない。

---

# 32. Architecture Principle

本機能の核心:

```text
Configuration Plane
        │
        │
        ├── What exists?
        └── How is it configured?


Runtime Plane
        │
        │
        ├── What is running?
        ├── What is it doing?
        └── Does it need me?
```

最終的に `ai-adapter` は以下の3つの問いに答える。

```text
ai-adapter scan
    → What exists?

ai-adapter doctor
    → Is it healthy?

ai-adapter monitor
    → What is happening now?
```

---

# 33. Core Design Rule

このPoCで最も重要なルール:

> Orcaだけを完成させない。
> VS Codeだけを完成させない。
> Zedだけを完成させない。

最初に、

```text
Orca      → 1 session
VS Code   → 1 session
Zed       → 1 session
```

を同一Canonical Modelへ通す。

このVertical Sliceが成立して初めて、詳細Status実装へ進む。

本プロジェクトの価値は個々のAgent監視ではない。

**異なるHostに分散したAI Agentを、単一のRuntime Observability Layerから監視できることにある。**
