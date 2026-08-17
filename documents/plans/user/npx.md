# npm / npx Agent Skills 管理仕様書

**Version:** 2.0  
**基準日:** 2026-08-16  
**対象:** `vercel-labs/skills` / `npx skills`  
**ステータス:** 現行公開仕様・現行実装を反映

---

## 1. 目的

本仕様書は、`npx skills` による **Agent Skills の検索・取得・インストール・共有・更新・削除・復元**の仕組みを定義する。

対象はVercel Labsが公開している `skills` CLIである。

公式リポジトリ：

`vercel-labs/skills`

[GitHub — vercel-labs/skills](https://github.com/vercel-labs/skills?utm_source=chatgpt.com)

Skill discoveryサイト：

[skills.sh — The Open Agent Skills Ecosystem](https://skills.sh/?utm_source=chatgpt.com)

---

# 2. 用語

## 2.1 Agent Skill

AI Agentへ特定分野の知識、手順、ワークフロー等を追加するパッケージ。

基本単位はディレクトリであり、中心となるファイルは、

```text
SKILL.md

```

である。

---

## 2.2 `skills`

Agent Skillsを管理するCLI。

主要機能：

```text
検索
取得
検出
インストール
一覧表示
更新
削除
復元
Agentへの配置

```

---

## 2.3 npm

`skills` CLIを配布するために利用されるNode.jsパッケージエコシステム。

---

## 2.4 npx

npm packageとして公開されている `skills` CLIを、グローバルインストールせず実行する手段。

典型的な利用方法：

```bash
npx skills add vercel-labs/agent-skills

```

---

# 3. 基本アーキテクチャ

`npx skills` において、npmがSkill本体の唯一のRegistryになっているわけではない。

基本構造は、

```text
npm Registry
     │
     │ CLI配布
     ▼
   npx skills
     │
     │ Skill Source解決
     ▼
┌───────────────────────┐
│ GitHub                │
│ GitLab                │
│ Generic Git           │
│ HTTP                  │
│ Local filesystem      │
└───────────┬───────────┘
            │
            ▼
        SKILL.md
            │
            ▼
      Skill Installer
            │
            ▼
┌───────────────────────┐
│ Claude Code           │
│ Codex                 │
│ OpenCode              │
│ Cursor                │
│ Cline                 │
│ Gemini CLI            │
│ GitHub Copilot        │
│ その他対応Agent       │
└───────────────────────┘

```

となる。

したがって、

> npm = Skill Registry

ではなく、

> npm/npx = `skills` CLIの配布・実行レイヤー

と理解する必要がある。

---

# 4. Skill Discoveryレイヤー

Skillを探すためのWebインターフェースとして [`skills.sh`](http://skills.sh) が提供されている。

```text
skills.sh
    │
    ├── Skill検索
    ├── Skill一覧
    ├── Ranking
    ├── Install count
    └── Install command

```

Web上でSkillを発見し、

```bash
npx skills add <owner/repository>

```

によって導入する流れを構成する。

---

# 5. Skillの基本構造

最低限、

```text
my-skill/
└── SKILL.md

```

を持つ。

代表的な [`SKILL.md`](http://SKILL.md)：

```markdown
---
name: my-skill
description: Description of what this skill does
---

# My Skill

Instructions for the AI agent.

```

主要メタデータ：

```yaml
name:
description:

```

Skillには必要に応じて追加リソースを含められる。

```text
my-skill/
├── SKILL.md
├── scripts/
├── references/
├── templates/
└── assets/

```

---

# 6. Agent Skills Specification

`skills` CLIはAgent Skills形式を利用する。

ただし、

```text
SKILL.md

```

の基本仕様が共通だからといって、すべてのAgentが完全に同じ機能を実装するわけではない。

概念上、

```text
Common Agent Skills Specification
              +
Agent-specific extensions

```

となる。

例えばAgentによっては、

```text
allowed-tools
hooks
context
subagent関連機能

```

などの追加機能を持つ。

したがってSkillの互換性には、

```text
基本Skill互換性
Agent固有機能互換性

```

の2レベルが存在する。

---

# 7. Skill Source

`skills add` は複数のSource形式を扱う。

## 7.1 GitHub shorthand

```bash
npx skills add vercel-labs/agent-skills

```

形式：

```text
owner/repository

```

---

## 7.2 GitHub URL

```bash
npx skills add \
https://github.com/vercel-labs/agent-skills

```

---

## 7.3 Repository内の特定Skill

```bash
npx skills add \
https://github.com/vercel-labs/agent-skills/tree/main/skills/web-design-guidelines

```

---

## 7.4 GitLab

```bash
npx skills add \
https://gitlab.com/org/repository

```

---

## 7.5 Generic Git

SSH：

```bash
npx skills add \
git@github.com:owner/repository.git

```

HTTPS：

```bash
npx skills add \
https://git.example.com/org/repository.git

```

---

## 7.6 Local Directory

```bash
npx skills add ./my-skills

```

---

## 7.7 HTTP Download

HTTP URLからSkillまたはArchiveを取得する仕組みも存在する。

対象例：

```text
SKILL.md
.zip
.tar
.tar.gz
.tgz

```

Archive展開時には安全性のためサイズやファイル数等に制限が設けられる。

---

# 8. Skill Discovery

Repositoryを取得した後、CLIは [`SKILL.md`](http://SKILL.md) を探索する。

代表例：

```text
repository/
└── skills/
    ├── skill-a/
    │   └── SKILL.md
    │
    └── skill-b/
        └── SKILL.md

```

カテゴリ構造も扱える。

```text
skills/
└── ecommerce/
    └── eccube/
        └── SKILL.md

```

標準探索では深さ制限が存在し、浅い位置のSkillが優先される。

より深い探索が必要な場合には、

```bash
--full-depth

```

を利用できる。

既知のSkill locationとして、

```text
skills/
.agents/skills/
.claude/skills/
.continue/skills/

```

等も探索対象になり得る。

---

# 9. Claude Plugin Discovery

Claude Plugin形式との一定の互換性を持つ。

例えば、

```text
.claude-plugin/
├── marketplace.json

```

または、

```text
.claude-plugin/
└── plugin.json

```

を解析し、宣言されているSkillsを発見できる。

したがって、

```text
Claude Plugin Repository
          │
          ▼
  Claude Plugin Manifest
          │
          ▼
       Skills
          │
          ▼
     skills CLI

```

という経路も存在する。

---

# 10. Skill一覧確認

Repository内のSkillをインストールせず確認する。

```bash
npx skills add \
vercel-labs/agent-skills \
--list

```

用途：

```text
Repository調査
Skill選択
自動化前の確認

```

---

# 11. Skillインストール

基本：

```bash
npx skills add vercel-labs/agent-skills

```

CLIは、

```text
Source取得
    ↓
Skill Discovery
    ↓
Skill選択
    ↓
Agent検出
    ↓
Scope選択
    ↓
Installation

```

を行う。

---

# 12. 特定Skill指定

```bash
npx skills add vercel-labs/agent-skills \
  --skill frontend-design

```

複数：

```bash
npx skills add vercel-labs/agent-skills \
  --skill frontend-design \
  --skill web-design-guidelines

```

全Skill：

```bash
npx skills add vercel-labs/agent-skills \
  --skill '*'

```

---

# 13. Agent指定

特定Agent：

```bash
npx skills add vercel-labs/agent-skills \
  --agent claude-code

```

短縮形：

```bash
npx skills add vercel-labs/agent-skills \
  -a claude-code

```

複数Agent：

```bash
npx skills add vercel-labs/agent-skills \
  -a claude-code \
  -a opencode

```

対象Agentをすべて指定する操作もサポートされる。

CLIには利用可能なAgentを検出する処理が存在する。

---

# 14. 対応Agent

現在の `skills` はClaude CodeだけのInstallerではない。

代表例：

```text
Claude Code
Codex
OpenCode
Cursor
Cline
Gemini CLI
GitHub Copilot
OpenClaw
Continue
Windsurf
Kiro CLI
Roo Code
Zed
Amp
その他多数

```

現行プロジェクトは70以上のAgent integrationを持つ大規模なAgent Skill installerとなっている。

---

# 15. Project Scope

デフォルトはProject Scope。

```bash
npx skills add owner/repository

```

プロジェクト内のAgent Skill locationへ配置される。

用途：

```text
Repository固有Skill
プロジェクト固有Skill
チーム共有
Gitによる管理

```

---

# 16. Global Scope

```bash
npx skills add owner/repository -g

```

または、

```bash
npx skills add owner/repository --global

```

ユーザー単位でSkillを導入する。

用途：

```text
個人共通Skill
全Project共通Skill

```

---

# 17. Agent別Skill Directory

AgentによってSkill directoryは異なる。

代表例：


| Agent          | Project           | Global                       |
| -------------- | ----------------- | ---------------------------- |
| Claude Code    | `.claude/skills/` | `~/.claude/skills/`          |
| Codex          | `.agents/skills/` | `~/.codex/skills/`           |
| OpenCode       | `.agents/skills/` | `~/.config/opencode/skills/` |
| Cursor         | `.agents/skills/` | `~/.cursor/skills/`          |
| Cline          | `.agents/skills/` | `~/.agents/skills/`          |
| Zed            | `.agents/skills/` | `~/.agents/skills/`          |
| GitHub Copilot | `.agents/skills/` | `~/.copilot/skills/`         |
| Gemini CLI     | `.agents/skills/` | `~/.gemini/skills/`          |


`skills` CLIがこの差異を吸収する。

---

# 18. Canonical Skill

複数Agentへ同じSkillを導入する場合、SkillのCanonical copyを基準にできる。

概念：

```text
Canonical Skill
      │
      ├────────→ Claude
      │
      ├────────→ Codex
      │
      ├────────→ OpenCode
      │
      └────────→ Cursor

```

これによりAgentごとに完全に独立したSkillを管理する必要性を減らす。

---

# 19. Symlink方式

標準的な共有方法としてsymlinkを利用できる。

```text
Canonical Skill
      │
      ├── symlink → Claude
      ├── symlink → Codex
      └── symlink → OpenCode

```

利点：

```text
Single Source of Truth
重複削減
更新容易
複数Agent間で共有

```

---

# 20. Copy方式

明示的にCopy方式を選択できる。

```bash
npx skills add owner/repository --copy

```

構造：

```text
Canonical Skill
      │
      ├── copy → Claude
      ├── copy → Codex
      └── copy → OpenCode

```

symlinkが利用できない環境等で利用する。

---

# 21. 非対話インストール

CI/CDやScriptから利用する場合：

```bash
npx skills add \
  vercel-labs/agent-skills \
  --skill frontend-design \
  -a claude-code \
  -g \
  -y

```

`-y` / `--yes` により確認処理を省略できる。

---

# 22. Installed Skills一覧

```bash
npx skills list

```

短縮：

```bash
npx skills ls

```

Global：

```bash
npx skills ls -g

```

Agent限定：

```bash
npx skills ls \
  -a claude-code \
  -a cursor

```

---

# 23. Skill検索

```bash
npx skills find react

```

複数キーワード：

```bash
npx skills find react performance

```

例：

```bash
npx skills find pr review

```

Ownerで絞ることもできる。

```bash
npx skills find react \
  --owner vercel-labs

```

DiscoveryのWeb UIとして [`skills.sh`](http://skills.sh) も利用できる。

---

# 24. Skill Update

基本：

```bash
npx skills update

```

現在のUpdateは単純な再ダウンロードだけではない。

インストール状態としてSourceやhash情報を保持し、Source側のSkill状態と比較して更新を判定する仕組みを持つ。

概念：

```text
Installed Skill
       │
       ▼
Local Skill State
       │
       ▼
skillFolderHash
       │
       ▼
Remote Source
       │
       ▼
Remote Hash / SHA
       │
       ▼
    Compare
       │
   ┌───┴────┐
   │        │
 same     changed
   │        │
 skip     update

```

GitHub SourceについてはGitHub APIを利用した状態確認と、必要に応じたGit取得処理を組み合わせる。

---

# 25. Skill削除

対話式：

```bash
npx skills remove

```

特定Skill：

```bash
npx skills remove web-design-guidelines

```

短縮：

```bash
npx skills rm web-design-guidelines

```

複数：

```bash
npx skills remove \
  frontend-design \
  web-design-guidelines

```

Global：

```bash
npx skills remove \
  -g web-design-guidelines

```

Agent指定：

```bash
npx skills remove \
  --agent claude-code \
  my-skill

```

全削除：

```bash
npx skills remove --all

```

---

# 26. Skillをインストールせず使用

`use` によりSkillを恒久インストールせず利用できる。

```bash
npx skills use \
  vercel-labs/agent-skills@web-design-guidelines

```

Claudeへ渡す例：

```bash
npx skills use \
  vercel-labs/agent-skills@web-design-guidelines \
  | claude

```

Agent指定：

```bash
npx skills use \
  vercel-labs/agent-skills \
  --skill web-design-guidelines \
  --agent claude-code

```

概念：

```text
Remote Skill
     │
     ▼
Temporary directory
     │
     ▼
Skill resolution
     │
     ▼
Agent

```

恒久的なInstalled Skillを作らず利用できる。

---

# 27. Skill作成

Skill templateを生成する。

```bash
npx skills init

```

名前指定：

```bash
npx skills init my-skill

```

生成後、

```text
Repository
└── skills/
    └── my-skill/
        └── SKILL.md

```

としてGit Repository等で配布できる。

---

# 28. Internal Skill

内部利用SkillをDiscoveryから隠す仕組みが存在する。

例：

```yaml
---
name: internal-tool
description: Internal company tool
metadata:
  internal: true
---

```

通常Discoveryでは除外される。

必要に応じて環境変数を利用してInternal Skillを含められる。

```bash
INSTALL_INTERNAL_SKILLS=1 \
npx skills add owner/repository --list

```

社内Repositoryなどで、

```text
Public Skills
Internal Skills

```

を同居させる用途に利用できる。

---

# 29. Private Repository

Private Git Repositoryにも対応する。

GitHub：

```bash
npx skills add acme/private-skills

```

SSH：

```bash
npx skills add \
git@github.com:acme/private-skills.git

```

HTTPS：

```bash
npx skills add \
https://git.example.com/acme/private-skills.git

```

既存Git認証やSSH認証等を利用する。

GitHub環境では必要に応じて、

```text
GITHUB_TOKEN
GH_TOKEN

```

等の認証情報を利用できる。

---

# 30. Skill State Management

現在の `skills` は、単純なファイルコピーだけではなくSkill状態管理を持つ。

大きく、

```text
Global state
Project state

```

が存在する。

---

# 31. Global Skill Lock

Global Skill管理では、

```text
~/.agents/.skill-lock.json

```

が利用される。

主な用途：

```text
Installed Skill情報
Source情報
Hash情報
Update判定

```

---

# 32. Project Lock File

Project単位では、

```text
skills-lock.json

```

による管理機構が存在する。

概念：

```text
my-project/
├── src/
├── package.json
├── skills-lock.json
└── ...

```

Project lock fileは、Skill環境の再現性を高める。

Git Repositoryへ含めることで、

```text
Developer A
Developer B
CI
Agent environment

```

で同じSkill構成を復元する用途を持つ。

---

# 33. Lock Fileの責務

Lock stateには概念上、

```text
Skill identity
Source
Resolved location
Hash
Installation information

```

などが保持される。

Updateでは、

```text
lock state
    +
remote source state

```

を比較する。

これにより単純な、

```text
毎回全部再ダウンロード

```

ではなく、変更状態を判定できる。

---

# 34. Hash-based Update

現在の実装ではSkill folderの状態を表す、

```text
skillFolderHash

```

が重要な役割を持つ。

概念：

```text
Local lock
   │
   └── skillFolderHash = ABC
                │
                ▼
          Remote Source
                │
                └── hash = XYZ
                       │
                       ▼
                  ABC != XYZ
                       │
                       ▼
                     Update

```

変更がなければ不要なUpdateを回避できる。

---

# 35. Project Skill Environment Restore

現在の実装にはProject lock stateからSkill環境を復元する処理が存在する。

コマンド体系として、

```bash
skills install

```

短縮：

```bash
skills i

```

が実装されている。

概念：

```text
Git clone project
       │
       ▼
skills-lock.json
       │
       ▼
skills install
       │
       ▼
Skill sources取得
       │
       ▼
Agent directories
       │
       ▼
Environment restored

```

これはnpmにおける、

```bash
npm install

```

と類似する「宣言済み環境の復元」という役割を持つ。

---

# 36. Experimental Install

実装には、

```text
experimental_install

```

系の処理も存在する。

これはlockfileを利用した復元機能の開発過程・実験系インターフェースとして扱うべきであり、通常利用者向けのStable APIとは区別して仕様を記載する。

---

# 37. node_modules Skill Sync

重要な実験機能として、

```text
experimental_sync

```

が存在する。

これは `node_modules` 内を探索し、SkillをAgent directoryへ同期する。

概念：

```text
npm install
    │
    ▼
node_modules/
    │
    ├── package-a/
    │      └── skills/
    │
    └── package-b/
           └── SKILL.md
                │
                ▼
       experimental_sync
                │
                ▼
        Agent directories

```

したがって現在は、

> npmはCLIを配布するだけ

と完全に限定するのも正確ではない。

正確には、

```text
Stable/main path:
npm → npx skills → Git等 → Skill

Experimental path:
npm → node_modules → skills sync → Agent

```

の両方が存在する。

ただし後者は**実験機能**としてStableなSkill配布方式と区別する必要がある。

---

# 38. npm PackageとAgent Skillの関係

通常のnpm package：

```text
npm Registry
     │
     ▼
npm install
     │
     ▼
node_modules/

```

現在の主要なAgent Skill経路：

```text
npm Registry
     │
     ▼
npx skills
     │
     ▼
Git / HTTP / Local
     │
     ▼
SKILL.md
     │
     ▼
Agent Skill Directory

```

Experimental：

```text
npm Registry
     │
     ▼
npm install
     │
     ▼
node_modules/
     │
     ▼
skills sync
     │
     ▼
Agent Skill Directory

```

この3つを混同しないことが重要である。

---

# 39. Telemetry

`skills` CLIには匿名Telemetryが存在する。

利用状況や公開Skill/Repositoryに関する識別情報等が送信される場合がある。

Telemetryを無効化する場合：

```bash
DISABLE_TELEMETRY=1

```

または、

```bash
DO_NOT_TRACK=1

```

を利用できる。

企業・CI環境ではTelemetry policyを事前に決定することが望ましい。

---

# 40. Security

SkillはAI AgentへInstructionや関連リソースを提供する。

Skillによっては、

```text
scripts
commands
tools
references
Agent-specific capabilities

```

等を含む可能性がある。

したがって、未知のSkillを導入する場合はSourceを確認する必要がある。

特に確認対象：

```text
SKILL.md
scripts/
hooks
MCP configuration
tool permissions
network operations
filesystem operations
shell commands

```

Private Repositoryの場合は認証情報の扱いにも注意する。

---

# 41. CLIコマンド体系

公開・主要機能：

```text
skills
│
├── add
│   └── Skill取得・インストール
│
├── use
│   └── Skillを一時利用
│
├── list / ls
│   └── Installed Skill一覧
│
├── find
│   └── Skill検索
│
├── update
│   └── Skill更新
│
├── remove / rm
│   └── Skill削除
│
└── init
    └── Skill作成

```

現行実装にはさらに、

```text
skills
│
├── install / i
│   └── lock stateからSkill環境を復元
│
├── experimental_install
│   └── Experimental restore
│
└── experimental_sync
    └── node_modules等からSkill同期

```

が存在する。

Stable/Public APIとExperimental機能は区別して扱う。

---

# 42. Skillライフサイクル

```text
                    ┌──────────┐
                    │   find   │
                    └────┬─────┘
                         │
                         ▼
                    Discovery
                         │
                         ▼
                       add
                         │
                         ▼
                    Installed
                    /    │    \
                   /     │     \
                  ▼      ▼      ▼
                use    update   list
                         │
                         ▼
                      Updated
                         │
                         ▼
                       remove
                         │
                         ▼
                      Deleted

```

Project環境ではさらに、

```text
skills-lock.json
       │
       ▼
   Git clone
       │
       ▼
skills install
       │
       ▼
Environment restored

```

という再現ライフサイクルが加わる。

---

# 43. 完全アーキテクチャ

```text
┌─────────────────────────────────────────────┐
│                  Discovery                  │
│                                             │
│                 skills.sh                   │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│               CLI Distribution              │
│                                             │
│            npm Registry / npx               │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│                 skills CLI                  │
│                                             │
│ add / find / list / use / update / remove  │
│ init / install                              │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│               Source Resolver               │
│                                             │
│ GitHub                                      │
│ GitLab                                      │
│ Generic Git                                 │
│ HTTP                                        │
│ Local                                       │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│              Skill Discovery                │
│                                             │
│ SKILL.md                                    │
│ Agent directories                           │
│ Claude plugin manifests                     │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│               State Manager                 │
│                                             │
│ ~/.agents/.skill-lock.json                  │
│ skills-lock.json                            │
│ skillFolderHash                             │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│                Installer                    │
│                                             │
│ Canonical Skill                             │
│ Symlink / Copy                              │
└─────────┬──────────┬──────────┬─────────────┘
          │          │          │
          ▼          ▼          ▼
       Claude      Codex     OpenCode
       Cursor      Cline     Gemini
          │          │          │
          └──────────┼──────────┘
                     ▼
                 AI Agents

```

---

# 44. 責務分離

## npm

```text
skills CLIのPackage配布

```

## npx

```text
skills CLIのオンデマンド実行

```

## skills CLI

```text
Discovery
Source resolution
Installation
Agent detection
State management
Update
Removal
Restore

```

## [skills.sh](http://skills.sh)

```text
Skill discovery/index
検索
ランキング
Install情報表示

```

## Git / GitHub / HTTP

```text
Skill Source

```

## [SKILL.md](http://SKILL.md)

```text
Skill definition
Agent instruction
Metadata

```

## Lock State

```text
Installed state
Source state
Hash
Reproducibility
Update detection

```

## AI Agent

```text
Skill discovery at runtime
Skill execution
Agent-specific behavior

```

---

# 45. 最小利用フロー

## 45.1 探す

```bash
npx skills find eccube

```

または [`skills.sh`](http://skills.sh) で検索。

---

## 45.2 Repository確認

```bash
npx skills add owner/eccube-skills --list

```

---

## 45.3 Skillインストール

```bash
npx skills add owner/eccube-skills \
  --skill eccube-development

```

---

## 45.4 Claude Code限定

```bash
npx skills add owner/eccube-skills \
  --skill eccube-development \
  -a claude-code

```

---

## 45.5 Global

```bash
npx skills add owner/eccube-skills \
  --skill eccube-development \
  -a claude-code \
  -g

```

---

## 45.6 確認

```bash
npx skills list

```

---

## 45.7 更新

```bash
npx skills update

```

---

## 45.8 削除

```bash
npx skills remove eccube-development

```

---

# 46. Team利用フロー

ProjectにSkill stateを保持する場合：

```text
Developer A
    │
    │ Skill追加
    ▼
skills-lock.json
    │
    │ git commit
    ▼
Git Repository
    │
    │ git clone
    ▼
Developer B / CI
    │
    │ skills install
    ▼
同一Skill環境を復元

```

これによりSkillを単なる個人設定ではなく、

```text
Project dependency

```

として扱う方向性が成立している。

---

# 47. 現行方式の特徴

現在の `skills` は単なる、

```text
SKILL.mdコピーCLI

```

ではない。

実際には、

```text
Skill discovery
        +
Multi-source resolution
        +
Multi-agent installation
        +
Project / Global scope
        +
Canonical Skill management
        +
Symlink / Copy
        +
Lock state
        +
Hash-based update
        +
Environment restore
        +
Private repository
        +
Skill search/index
        +
Experimental npm synchronization

```

を持つ。

したがって分類上は、

> **Agent Skills Package Manager**

として扱うのが適切である。

---

# 48. StableとExperimentalの区別

## 現行の主要利用経路

```text
npx skills
     ↓
Git / GitHub / HTTP / Local
     ↓
SKILL.md
     ↓
Agent

```

これは通常利用の中心として扱う。

## Experimental

```text
npm install
     ↓
node_modules
     ↓
experimental_sync
     ↓
Agent

```

などの機能は存在するものの、主要Stable UXと同等には扱わない。

仕様設計や他システムとの連携時には、

```text
Existing implementation

```

と、

```text
Stable public workflow

```

を分ける必要がある。

---

# 49. 本仕様に含めない独自拡張

以下は `skills` の現行機能そのものではないため、本仕様の標準機能には含めない。

```text
ECサイトでのSkill購入
有料Skill
Subscription
購入ライセンス
ユーザー単位DRM
EC-CUBE連携
販売者管理
売上分配
Skillレビュー
独自決済
Skill利用量課金
独自Marketplace API

```

これらを実装する場合は、`skills` の上位レイヤーとして別途仕様化する。

---

# 50. EC型Marketplaceとの境界

既存 `skills` が担当する範囲：

```text
Search
Source resolution
Download
Installation
Agent integration
State management
Update
Removal
Restore

```

EC型Marketplaceが追加する場合の範囲：

```text
商品管理
販売者
購入
決済
License
Entitlement
レビュー
ランキング
Revenue share
Private Skill delivery

```

したがって、

```text
Marketplace
     │
     │ Entitlement / Source提供
     ▼
skills-compatible Source
     │
     ▼
skills CLI
     │
     ▼
Agent

```

という責務分離が可能である。

ただしこのMarketplace部分は**既存** `skills` **の仕様ではなく独自拡張領域**である。

---

# 51. まとめ

2026年8月時点の `npm / npx Agent Skills管理` を正確に表現すると、

```text
npmでSkillそのものを管理する仕組み

```

ではない。

中心となるのは、

```text
npm / npx
     ↓
skills CLI
     ↓
Skill discovery / source resolution
     ↓
Git / HTTP / Local等からSkill取得
     ↓
SKILL.md
     ↓
State / lock管理
     ↓
AgentごとのSkill directoryへ導入
     ↓
Claude / Codex / OpenCode / Cursor / etc.

```

という構造である。

さらに現行実装では、

```text
skills-lock.json
skillFolderHash
skills install
node_modules synchronization

```

まで実装されており、単純なInstallerから**再現性・依存状態・更新管理を持つAgent Skill Package Managerへ発展している**。

一方で、

```text
node_modules → experimental_sync

```

などはExperimental領域であり、通常のStableなSkill導入経路とは分離して評価する必要がある。

### 主要参照先

- [vercel-labs/skills — 公式GitHubリポジトリ](https://github.com/vercel-labs/skills?utm_source=chatgpt.com)
- [skills.sh — Skill discovery/index](https://skills.sh/?utm_source=chatgpt.com)
- [vercel-labs/skills AGENTS.md — 現行実装・開発仕様](https://github.com/vercel-labs/skills/blob/main/AGENTS.md?utm_source=chatgpt.com)

