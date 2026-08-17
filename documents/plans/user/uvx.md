# uv / uvx ベース Agent Skills パッケージ基盤 開発設計書

**Version:** 1.0  
**基準日:** 2026-08-16  
**対象:** Agent Skills配布・インストール・更新基盤  
**基盤技術:** Python / uv / uvx / PyPI-compatible Package Index

---

# 1. 目的

本システムは、AI Agent向けSkillを、

```bash
uvx skillpkg add eccube-development

```

または、

```bash
uv tool install skillpkg
skillpkg add eccube-development

```

のような操作でインストール・更新・削除できるパッケージ基盤として構築する。

重要なのは、**uv自体にAgent Skills管理機能が存在するわけではない**ことである。

本設計では既存のuvを、

```text
CLI配布
Python runtime管理
依存関係解決
隔離実行環境
Package Indexアクセス
キャッシュ

```

の基盤として利用し、その上に独自の、

```text
Skill Registry
Skill Resolver
Skill Installer
Agent Adapter
Skill Lock
Entitlement

```

を実装する。

---

# 2. 既存機能と新規開発部分

本設計では両者を明確に分離する。

## 2.1 uvが既に提供している機能

uvには現在、

```bash
uv tool run

```

があり、

```bash
uvx

```

はそのエイリアスである。Python製CLIを隔離された環境で実行できる。([Astral Docs](https://docs.astral.sh/uv/guides/tools/?utm_source=chatgpt.com "Using tools | uv - Astral Docs"))

またCLIを恒久的にインストールする、

```bash
uv tool install <package>

```

も存在する。

`uv tool install` はCLIごとに独立したvirtual environmentを作成し、他のプロジェクトやToolの依存関係と分離する。([Astral Docs](https://docs.astral.sh/uv/concepts/tools/?utm_source=chatgpt.com "Tools | uv - Astral Docs"))

Python Package IndexについてはPyPIだけでなく、追加・Private Indexを設定できる。([Astral Docs](https://docs.astral.sh/uv/concepts/indexes/?utm_source=chatgpt.com "Package indexes | uv"))

uvはPython PackageのbuildとPackage Indexへのpublishもサポートする。([Astral Docs](https://docs.astral.sh/uv/guides/package/?utm_source=chatgpt.com "Building and publishing a package | uv"))

---

## 2.2 本プロジェクトで新規開発するもの

以下はuvの機能ではなく、本システム独自実装とする。

```text
Skill CLI
Skill Registry API
Skill Manifest
Skill Package Format
Agent detection
Agent adapters
Skill installation
Skill update
Skill removal
Skill lockfile
Private Skills
Marketplace authentication
License / Entitlement
Security validation

```

---

# 3. 基本コンセプト

アーキテクチャは、

```text
uv = Package Manager

skillpkg = Skill Package Manager

```

とする。

ユーザーから見ると、

```bash
uvx skillpkg add eccube-development

```

だけでSkillをインストールできる。

内部的には、

```text
uvx
 │
 ▼
PyPI / Private Python Index
 │
 ▼
skillpkg CLI
 │
 ▼
Skill Registry API
 │
 ▼
Skill Package
 │
 ▼
Agent Adapter
 │
 ▼
Claude / Codex / OpenCode / etc.

```

となる。

---

# 4. なぜuvxを利用するか

`uvx` は `uv tool run` のエイリアスであり、Python製CLIを隔離環境で実行できる。([Astral Docs](https://docs.astral.sh/uv/reference/cli/?utm_source=chatgpt.com "Commands | uv - Astral Docs"))

したがってユーザーは、

```bash
pip install skillpkg

```

や、

```bash
python -m venv ...

```

を事前に行う必要がない。

最小UXは、

```bash
uvx skillpkg add eccube-development

```

となる。

これは概念的には、

```text
npx skills add ...

```

に対する、

```text
uvx skillpkg add ...

```

という位置付けになる。

ただし後者は**本プロジェクトで新規開発するCLI**である。

---

# 5. 恒久インストール

頻繁に利用するユーザー向けには、

```bash
uv tool install skillpkg

```

を利用する。

その後は、

```bash
skillpkg add eccube-development
skillpkg list
skillpkg update

```

と直接実行できる。

uvはTool単位で独立したvirtual environmentを作成するため、`skillpkg` のPython依存関係がユーザーの既存Python projectと衝突しにくい。([Astral Docs](https://docs.astral.sh/uv/concepts/tools/?utm_source=chatgpt.com "Tools | uv - Astral Docs"))

---

# 6. 全体システム構成

```text
┌────────────────────────────────────────┐
│                User                    │
└──────────────────┬─────────────────────┘
                   │
                   │ uvx skillpkg ...
                   ▼
┌────────────────────────────────────────┐
│                  uv                    │
│                                        │
│ tool run / tool install                │
│ Python runtime                         │
│ dependency resolution                  │
│ cache                                  │
└──────────────────┬─────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────┐
│             skillpkg CLI               │
│                                        │
│ add                                    │
│ install                                │
│ search                                 │
│ list                                   │
│ update                                 │
│ remove                                 │
│ info                                   │
│ doctor                                 │
└──────────────────┬─────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────┐
│          Skill Registry API            │
│                                        │
│ Skill metadata                         │
│ Versions                               │
│ Downloads                              │
│ Entitlement                            │
│ Signing                                │
└──────────────────┬─────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────┐
│             Skill Storage              │
│                                        │
│ Object Storage                         │
│ Git repository                         │
│ Private Storage                        │
└──────────────────┬─────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────┐
│          Agent Adapter Layer           │
└───────┬─────────┬──────────┬───────────┘
        │         │          │
        ▼         ▼          ▼
      Claude    Codex     OpenCode
        │         │          │
        └─────────┼──────────┘
                  ▼
             Agent Skills

```

---

# 7. CLI Package

CLI package名を仮に、

```text
skillpkg

```

とする。

Python Packageとして、

```text
skillpkg/
├── pyproject.toml
├── src/
│   └── skillpkg/
└── tests/

```

を作成する。

---

# 8. pyproject.toml

CLIエントリーポイントを定義する。

```toml
[project]
name = "skillpkg"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    "httpx",
    "pydantic",
    "typer",
]

[project.scripts]
skillpkg = "skillpkg.cli:app"

```

これをbuildしてPackage Indexへ公開する。

uvは、

```bash
uv build

```

および、

```bash
uv publish

```

によるPython Packageのbuild / publishをサポートする。([Astral Docs](https://docs.astral.sh/uv/guides/package/?utm_source=chatgpt.com "Building and publishing a package | uv"))

---

# 9. CLI利用形態

## 一時実行

```bash
uvx skillpkg search eccube

```

---

## 恒久インストール

```bash
uv tool install skillpkg

```

---

## 更新

CLI自体の更新：

```bash
uv tool upgrade skillpkg

```

---

## 削除

```bash
uv tool uninstall skillpkg

```

---

# 10. CLIコマンド体系

```text
skillpkg
│
├── search
│
├── info
│
├── add
│
├── install
│
├── list
│
├── update
│
├── remove
│
├── sync
│
├── doctor
│
├── login
│
└── logout

```

---

# 11. search

Skill検索。

```bash
uvx skillpkg search eccube

```

結果例：

```text
NAME                    VERSION    DOWNLOADS
eccube-development      1.4.2      12,452
eccube-review           1.1.0       3,210
eccube-security         2.0.1       1,914

```

---

# 12. info

```bash
uvx skillpkg info eccube-development

```

表示：

```text
Name: eccube-development
Version: 1.4.2
Author: example
License: MIT

Agents:
✓ Claude Code
✓ Codex
✓ OpenCode

Dependencies:
- github-review >= 1.0

Permissions:
- filesystem: read
- shell: composer

```

---

# 13. add

Skill追加：

```bash
uvx skillpkg add eccube-development

```

バージョン指定：

```bash
uvx skillpkg add eccube-development@1.4.2

```

複数：

```bash
uvx skillpkg add eccube-development seo-review

```

Global：

```bash
uvx skillpkg add eccube-development -g

```

Agent指定：

```bash
uvx skillpkg add eccube-development \
  --agent claude

```

---

# 14. add内部処理

```text
skillpkg add
     │
     ▼
Skill identifier parse
     │
     ▼
Registry metadata取得
     │
     ▼
Version resolve
     │
     ▼
Entitlement確認
     │
     ▼
Package download
     │
     ▼
Integrity検証
     │
     ▼
Manifest validation
     │
     ▼
Agent detection
     │
     ▼
Canonical Skillへ展開
     │
     ▼
Agent directoryへ配置
     │
     ▼
Lockfile更新

```

---

# 15. Skill Package Format

Skill本体のPackage formatを独自に定義する。

例：

```text
eccube-development/
├── skill.toml
├── SKILL.md
├── scripts/
│   ├── inspect.php
│   └── analyze.py
├── references/
│   └── eccube.md
├── templates/
└── assets/

```

---

# 16. skill.toml

例：

```toml
[skill]
name = "eccube-development"
version = "1.4.2"
description = "EC-CUBE development assistant"

[compatibility]
claude-code = ">=1"
codex = ">=1"
opencode = ">=1"

[dependencies.skills]
php-review = ">=1.0,<2"

[requirements]
python = ">=3.11"

[permissions]
filesystem = ["read"]
shell = ["php", "composer"]

[entrypoints]
skill = "SKILL.md"

```

---

# 17. [SKILL.md](http://SKILL.md)

Agentが読むInstructionは [`SKILL.md`](http://SKILL.md) とする。

```markdown
---
name: eccube-development
description: EC-CUBE development workflow and review skill
---

# EC-CUBE Development

...

```

`skill.toml` はPackage Manager用。

[`SKILL.md`](http://SKILL.md) はAgent用。

責務を分離する。

```text
skill.toml
      │
      └── Package Manager metadata

SKILL.md
      │
      └── Agent instructions

```

---

# 18. Registry API

RegistryはSkill metadataを管理する。

API例：

```text
GET /v1/skills
GET /v1/skills/{name}
GET /v1/skills/{name}/versions
GET /v1/skills/{name}/{version}
GET /v1/skills/{name}/{version}/download

```

検索：

```text
GET /v1/search?q=eccube

```

---

# 19. Registry Metadata

```json
{
  "name": "eccube-development",
  "latest_version": "1.4.2",
  "description": "EC-CUBE development assistant",
  "author": {
    "id": "user_123",
    "name": "example"
  },
  "versions": [
    "1.4.2",
    "1.4.1",
    "1.3.0"
  ]
}

```

---

# 20. Skill Storage

Skill binaryはRegistry DBではなくObject Storageに配置する。

```text
Registry DB
     │
     └── Metadata

Object Storage
     │
     ├── eccube-development/1.4.2.tar.gz
     ├── eccube-development/1.4.1.tar.gz
     └── ...

```

例：

```text
S3
Cloudflare R2
Google Cloud Storage

```

---

# 21. Python Package IndexとSkill Registryの分離

本設計では、

```text
Python Package

```

と、

```text
Agent Skill

```

を原則として別Registryにする。

```text
PyPI
 │
 └── skillpkg CLI

Skill Registry
 │
 ├── eccube-development
 ├── seo-agent
 └── github-review

```

理由はSkillが必ずしもPython packageではないため。

Skillには、

```text
Markdown
Shell
PHP
Node.js
Binary
Reference data

```

等を含める可能性がある。

---

# 22. Private Python Index

CLI自体をPrivate配布したい場合、uvは追加Package Indexを設定できる。([Astral Docs](https://docs.astral.sh/uv/concepts/indexes/?utm_source=chatgpt.com "Package indexes | uv"))

例えば企業内CLIを、

```text
https://packages.example.com/simple/

```

で配布できる。

uvはAWS CodeArtifact、Google Artifact Registry、Azure Artifacts、JFrog Artifactory等の代替Package Indexとの認証に関する公式ガイドも提供している。([Astral Docs](https://docs.astral.sh/uv/concepts/authentication/third-party/?utm_source=chatgpt.com "Third-party services | uv - Astral Docs"))

ただしこれは、

```text
skillpkg CLIのPrivate配布

```

に使用するものであり、Skill販売Registryとは分離する。

---

# 23. Agent Adapter

Agentごとの差をAdapter Patternで吸収する。

```python
class AgentAdapter:
    def detect(self) -> bool: ...

    def project_skill_dir(self) -> Path: ...

    def global_skill_dir(self) -> Path: ...

    def install(self, skill): ...

    def uninstall(self, skill): ...
```

---

# 24. Adapter実装

```text
skillpkg/
└── agents/
    ├── base.py
    ├── claude.py
    ├── codex.py
    ├── opencode.py
    ├── cursor.py
    └── gemini.py

```

---

# 25. Agent detection

例えば、

```text
.claude/
.codex/
.opencode/
.cursor/

```

や実行可能CLI等を確認する。

結果：

```text
Detected agents:

✓ Claude Code
✓ Codex
✗ OpenCode

```

複数検出時：

```text
Install to:

[✓] Claude Code
[✓] Codex
[ ] OpenCode

```

---

# 26. Canonical Skill Store

Skill本体はAgent directoryへ直接ダウンロードせず、Canonical Storeを設ける。

Project：

```text
.skills/

```

Global：

```text
~/.local/share/skillpkg/skills/

```

例：

```text
.skills/
└── eccube-development/
    └── 1.4.2/
        ├── skill.toml
        └── SKILL.md

```

---

# 27. Agentへの配置

Canonical Storeから、

```text
Canonical Skill
     │
     ├── symlink → Claude
     ├── symlink → Codex
     └── symlink → OpenCode

```

とする。

Symlinkが利用できない環境ではCopyへfallbackする。

---

# 28. Project Scope

```bash
skillpkg add eccube-development

```

Project単位。

例：

```text
project/
├── .skills/
│   └── eccube-development/
├── skills.toml
└── skills.lock

```

---

# 29. Global Scope

```bash
skillpkg add eccube-development -g

```

配置：

```text
~/.local/share/skillpkg/
├── skills/
├── registry/
└── state.json

```

---

# 30. skills.toml

Projectで利用するSkillを宣言する。

```toml
[skills]
eccube-development = "^1.4"
github-review = "~2.1"

[agents]
claude-code = true
codex = true

```

---

# 31. skills.lock

解決済み状態：

```toml
version = 1

[[skill]]
name = "eccube-development"
version = "1.4.2"
source = "registry"

url = "https://registry.example.com/..."
sha256 = "4e12..."

[[skill]]
name = "github-review"
version = "2.1.5"
source = "registry"

sha256 = "f571..."

```

---

# 32. uv.lockとの関係

ここは重要である。

uvにはPython Project向けの `uv.lock` があり、依存関係をresolveした結果をlockし、syncによって環境へ反映する。([Astral Docs](https://docs.astral.sh/uv/concepts/projects/sync/?utm_source=chatgpt.com "Locking and syncing | uv"))

しかしAgent SkillsはPython dependenciesそのものではないため、

```text
uv.lock

```

に直接Skill状態を書き込まない。

分離する。

```text
uv.lock
    │
    └── Python dependencies

skills.lock
    │
    └── Agent Skill dependencies

```

---

# 33. Python依存を持つSkill

SkillがPython実行コードを持つ場合、

```toml
[runtime.python]
dependencies = [
    "beautifulsoup4>=4",
    "httpx>=0.28"
]

```

と宣言できるようにする。

ここでは2つの方式が考えられる。

###方式A

Skill Package内部に独立Python環境を作る。

###方式B

Skill scriptを `uv run` / `uvx` で実行する。

初期実装ではBを推奨する。

---

# 34. Skill Dependency

Skill同士の依存関係も定義する。

```toml
[dependencies.skills]
web-research = "^2.0"
browser = "^1.5"

```

Resolver：

```text
eccube-agent
   │
   ├── web-research ^2
   │
   └── browser ^1.5

```

---

# 35. Versioning

Semantic Versioningを基本とする。

```text
MAJOR.MINOR.PATCH

```

例：

```text
1.4.2

```

指定：

```bash
skillpkg add foo@1.4.2
skillpkg add foo@^1.4
skillpkg add foo@~1.4

```

---

# 36. Dependency Resolver

```text
Requested Skill
       │
       ▼
Skill Manifest
       │
       ▼
Dependencies
       │
       ▼
Available Versions
       │
       ▼
Constraint resolution
       │
       ▼
Resolved graph

```

Python package dependencyはuvへ委譲し、Skill dependencyのみ `skillpkg` が解決する。

責務：

```text
uv
└── Python dependency resolver

skillpkg
└── Skill dependency resolver

```

---

# 37. install

Repositoryをcloneしたユーザーが、

```bash
uvx skillpkg install

```

を実行。

処理：

```text
skills.lock
    │
    ▼
Skill versions取得
    │
    ▼
Hash検証
    │
    ▼
Canonical Store
    │
    ▼
Agent adapters

```

---

# 38. sync

```bash
uvx skillpkg sync

```

は、

```text
skills.toml
       │
       ▼
Dependency resolve
       │
       ▼
skills.lock更新
       │
       ▼
Installed stateを同期

```

とする。

uvのProject modelではlockingとsyncが依存環境管理の中心になっているため、本システムでも類似したUXを採用する。ただしSkill用の実装は独自である。([Astral Docs](https://docs.astral.sh/uv/concepts/projects/sync/?utm_source=chatgpt.com "Locking and syncing | uv"))

---

# 39. update

全Skill：

```bash
skillpkg update

```

特定Skill：

```bash
skillpkg update eccube-development

```

Dry run：

```bash
skillpkg update --dry-run

```

---

# 40. update処理

```text
Installed version
       │
       ▼
Registry
       │
       ▼
Available versions
       │
       ▼
Version constraint
       │
       ▼
Resolved version
       │
       ▼
Download
       │
       ▼
Hash verify
       │
       ▼
Atomic replace

```

---

# 41. remove

```bash
skillpkg remove eccube-development

```

Global：

```bash
skillpkg remove eccube-development -g

```

処理：

```text
Agent symlink削除
       │
       ▼
Canonical Skill参照確認
       │
       ▼
未使用なら削除
       │
       ▼
lock更新

```

---

# 42. doctor

環境診断：

```bash
skillpkg doctor

```

結果：

```text
uv
✓ installed
✓ version compatible

Python
✓ 3.13

Registry
✓ reachable

Authentication
✓ valid

Agents
✓ Claude Code
✓ Codex

Skills
✓ 14 installed
! 2 updates available

```

---

# 43. Authentication

Public Skill：

```text
Authentication不要

```

Private / Paid Skill：

```bash
skillpkg login

```

Browser OAuth方式を基本とする。

```text
CLI
 │
 ▼
Browser
 │
 ▼
Marketplace
 │
 ▼
OAuth
 │
 ▼
CLI token

```

---

# 44. Token Storage

Tokenは平文configへの保存を可能な限り避ける。

優先順位：

```text
OS Keychain
Keyring
Credential Manager
↓
Encrypted local store
↓
Environment variable

```

例：

```text
SKILLPKG_TOKEN

```

---

# 45. Entitlement

有料Skillの場合：

```text
CLI
 │
 │ Authorization
 ▼
Registry
 │
 ▼
Entitlement Service
 │
 ├── purchased
 │
 ├── subscribed
 │
 └── denied

```

許可された場合のみdownload URLを返す。

---

# 46. Download URL

Private Skillではshort-lived signed URLを利用する。

```text
GET /skills/foo/1.4.2/download

```

↓

```json
{
  "url": "https://storage/...signed...",
  "expires_in": 300
}

```

---

# 47. Integrity

各Skill artifactに、

```text
SHA-256

```

を付与する。

Registry：

```json
{
  "version": "1.4.2",
  "sha256": "..."
}

```

CLI：

```text
Download
  ↓
SHA256
  ↓
Registry hash比較
  ↓
Install

```

不一致の場合：

```text
INSTALL ABORT

```

---

# 48. Signing

第2段階でpublisher signatureを導入する。

```text
Publisher private key
       │
       ▼
Skill artifact
       │
       ▼
Signature
       │
       ▼
Registry

```

CLI：

```text
Artifact
   +
Signature
   +
Publisher public key
        ↓
Verification

```

---

# 49. Permission Manifest

AI Skill特有のリスク対策としてPermissionを明示する。

```toml
[permissions]
filesystem = [
    "read:project"
]

shell = [
    "git",
    "composer"
]

network = [
    "github.com"
]

```

---

# 50. インストール確認

例：

```text
Installing eccube-development 1.4.2

Permissions:

✓ Read project files
! Execute composer
! Network access: github.com

Install? [y/N]

```

---

# 51. Skill Publishing

Publisher：

```bash
skillpkg publish

```

処理：

```text
skill.toml validation
       │
       ▼
SKILL.md validation
       │
       ▼
Security checks
       │
       ▼
Archive creation
       │
       ▼
Hash
       │
       ▼
Upload
       │
       ▼
Registry metadata

```

---

# 52. Python PackageとしてSkillを配る方式

オプションとして、

```text
Skill = Python Package

```

も対応可能。

例えば、

```bash
uv add agent-skill-example

```

ではなく、

```bash
uvx skillpkg import-python agent-skill-example

```

などを将来的に設けられる。

ただし標準Skill formatにはしない。

理由：

```text
Agent Skill ≠ Python Package

```

だからである。

---

# 53. uv Package Indexとの統合

将来的にSkill Publisher SDKやCLI pluginを、

```text
skillpkg-publisher
skillpkg-security

```

等のPython packageとして配布する場合は、PyPIまたはPrivate Package Indexを利用する。

uvは複数Package Indexの設定と明示的Index指定をサポートする。([Astral Docs](https://docs.astral.sh/uv/concepts/indexes/?utm_source=chatgpt.com "Package indexes | uv"))

---

# 54. Cache

uv自身はPackage download等にキャッシュを利用する。([Astral Docs](https://docs.astral.sh/uv/concepts/cache/?utm_source=chatgpt.com "Caching | uv - Astral Docs"))

Skillについては独自Cacheを、

```text
~/.cache/skillpkg/

```

に持つ。

```text
~/.cache/skillpkg/
├── artifacts/
├── registry/
└── metadata/

```

---

# 55. Offline

一度取得したSkillは、

```bash
skillpkg install --offline

```

でcacheから復元できる設計とする。

---

# 56. CI利用

Project Repository：

```text
project/
├── pyproject.toml
├── uv.lock
├── skills.toml
└── skills.lock

```

CI：

```bash
uv sync --frozen
uvx skillpkg install --frozen

```

概念：

```text
uv.lock
    ↓
Python environment再現

skills.lock
    ↓
Agent Skills environment再現

```

---

# 57. Frozen Mode

```bash
skillpkg install --frozen

```

では、

```text
skills.toml
skills.lock

```

の不整合があれば失敗させる。

CIで再現性を保証する。

---

# 58. Repository構成

推奨Monorepo：

```text
skill-platform/
├── packages/
│   ├── cli/
│   │   └── skillpkg/
│   │
│   ├── sdk/
│   │
│   └── registry-client/
│
├── services/
│   ├── registry-api/
│   ├── auth/
│   └── entitlement/
│
├── agents/
│   ├── claude/
│   ├── codex/
│   └── opencode/
│
└── tests/

```

---

# 59. uv Workspace

Python側Monorepoにはuv workspaceを利用できる。

uvは `tool.uv.workspace` により複数Packageを1 workspaceとして管理できる。([Astral Docs](https://docs.astral.sh/uv/concepts/projects/workspaces/?utm_source=chatgpt.com "Using workspaces | uv - Astral Docs"))

例：

```toml
[tool.uv.workspace]
members = [
    "packages/cli",
    "packages/sdk",
    "packages/registry-client"
]

```

---

# 60. 開発環境

```bash
git clone ...
cd skill-platform

uv sync

```

実行：

```bash
uv run skillpkg --help

```

テスト：

```bash
uv run pytest

```

---

# 61. Registry DB

主要テーブル：

```text
users
publishers
skills
skill_versions
skill_files
skill_dependencies
skill_permissions
downloads
purchases
subscriptions
entitlements
publisher_keys

```

---

# 62. skills

```text
id
slug
name
description
publisher_id
visibility
latest_version_id
created_at
updated_at

```

---

# 63. skill_versions

```text
id
skill_id
version
manifest
artifact_url
artifact_sha256
signature
published_at
yanked_at

```

---

# 64. Visibility

```text
public
unlisted
private
paid

```

---

# 65. Version Yank

悪意あるVersion等を取り下げる。

```text
yanked_at

```

既にlockされているProjectについてどう扱うかはpolicyを別途持つ。

重大なSecurity incidentの場合のみ強制block可能な設計とする。

---

# 66. Marketplaceとの統合

Marketplace Web：

```text
Skill detail
    │
    ├── description
    ├── versions
    ├── publisher
    ├── reviews
    ├── permissions
    ├── compatibility
    └── install command

```

表示：

```bash
uvx skillpkg add eccube-development

```

---

# 67. EC-CUBEとの統合

EC-CUBEをMarketplaceとして利用する場合、

```text
EC-CUBE
   │
   ├── 商品
   ├── Customer
   ├── Order
   ├── Payment
   └── Publisher

```

とSkill Registryを接続する。

---

# 68. 商品とSkillの対応

```text
EC-CUBE Product
       │
       │ skill_id
       ▼
Skill Registry
       │
       ├── Versions
       ├── Artifact
       └── Metadata

```

---

# 69. 購入

```text
Customer
    │
    ▼
EC-CUBE Checkout
    │
    ▼
Payment
    │
    ▼
Order completed
    │
    ▼
Entitlement created
    │
    ▼
skillpkg add

```

---

# 70. CLI認証

```bash
uvx skillpkg login

```

Marketplaceアカウントと接続。

購入後：

```bash
uvx skillpkg add premium-eccube-agent

```

---

# 71. 推奨MVP

最初から全機能を作らない。

## Phase 1

```text
uvx CLI
Public Registry
GitHub / Storage download
SKILL.md
Claude adapter
Codex adapter
OpenCode adapter
Project / Global
add
list
remove

```

---

# 72. Phase 2

```text
skills.toml
skills.lock
Version resolution
update
install
sync
SHA256
Private repository

```

---

# 73. Phase 3

```text
Authentication
Paid Skills
Entitlement
Marketplace
EC-CUBE integration
Signed download URLs

```

---

# 74. Phase 4

```text
Publisher signatures
Permission manifest
Security scanner
Dependency graph
Reviews
Download ranking
Analytics

```

---

# 75. MVP CLI UX

最初のVersionでは、

```bash
uvx skillpkg search eccube

```

↓

```bash
uvx skillpkg add eccube-development

```

↓

```text
Detected:
Claude Code
Codex

Install eccube-development 1.0.0?

[y/N]

```

↓

```text
✓ Downloaded
✓ Verified
✓ Installed for Claude Code
✓ Installed for Codex

eccube-development@1.0.0 installed

```

とする。

---

# 76. uvベースにする最大の意味

このアーキテクチャにおいてuvが担当するのは、

```text
Agent Skillそのものの管理

```

ではない。

uvが担当するのは、

```text
Python runtime
CLI delivery
Tool isolation
Python dependency resolution
Python package indexes
Cache
Build
Publish

```

である。uvはPython toolを隔離環境にインストール・実行でき、Package build/publishや複数Indexも扱えるため、このCLIインフラ部分を自前実装せずに済む。([Astral Docs](https://docs.astral.sh/uv/guides/tools/?utm_source=chatgpt.com "Using tools | uv - Astral Docs"))

その上に、

```text
Skill Registry
Skill Manifest
Skill Resolver
Skill Lock
Agent Adapter
Marketplace

```

を構築する。

---

# 77. npx方式との比較

```text
npx方式

npm
 ↓
npx
 ↓
skills CLI
 ↓
Skill

```

本設計：

```text
uv方式

PyPI / Python Index
 ↓
uvx
 ↓
skillpkg CLI
 ↓
Skill

```

構造的には非常に近い。

最大の違いはCLI runtimeが、

```text
Node.js ecosystem

```

か、

```text
Python ecosystem

```

かである。

---

# 78. 本設計の最終アーキテクチャ

```text
                      Marketplace
                          │
                          ▼
                 ┌─────────────────┐
                 │ Skill Registry  │
                 └────────┬────────┘
                          │
                  Metadata / Auth
                          │
                          ▼
┌──────────┐       ┌─────────────────┐
│   PyPI   │──────▶│      uvx        │
└──────────┘       └────────┬────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │ skillpkg CLI  │
                    └───────┬───────┘
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
          ▼                 ▼                 ▼
     Resolver          Lock Manager      Auth Client
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │ Skill Store   │
                    └───────┬───────┘
                            │
                      Agent Adapter
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
    Claude Code           Codex            OpenCode

```

---

# 79. 最終責務分離


| Component                | 責務                         |
| ------------------------ | -------------------------- |
| **uv**                   | Python環境・CLI実行・Python依存管理  |
| **uvx**                  | `skillpkg` のオンデマンド実行       |
| **PyPI / Private Index** | `skillpkg` CLIの配布          |
| **skillpkg CLI**         | Skill package management   |
| **Skill Registry**       | Skill metadata / versions  |
| **Object Storage**       | Skill artifact             |
| **skills.toml**          | Project Skill宣言            |
| **skills.lock**          | 解決済みSkill状態                |
| **Agent Adapter**        | Agent固有配置処理                |
| **Marketplace**          | Discovery / Commerce       |
| **Entitlement**          | Private / Paid Skillアクセス制御 |


---

# 80. 結論

本設計で構築するものは、

> **「uvそのものをSkill Package Managerに改造する」システムではない。**

正確には、

```text
uv / uvx
   │
   │ Python Tool Infrastructure
   ▼
skillpkg
   │
   │ Agent Skill Package Manager
   ▼
Skill Registry
   │
   ▼
Agent Skills

```

という二層構造である。

ユーザーUXは、

```bash
uvx skillpkg add eccube-development

```

まで単純化できる。

一方、内部では、

```text
Registry
Version resolution
Dependency resolution
Integrity
Authentication
Entitlement
Lockfile
Agent adapters

```

を独自に管理する。

この分離により、**uvが既に解決しているPython runtime・CLI distribution・dependency isolation・Package Index・cache等を再実装せず、Agent Skills固有のPackage Managementに開発リソースを集中できる**設計となる。([Astral Docs](https://docs.astral.sh/uv/guides/tools/?utm_source=chatgpt.com "Using tools | uv - Astral Docs"))