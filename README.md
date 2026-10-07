# ai-adapter
<img src="docs/readme-thumbnail.png" alt="ai-adapter" width="800">

**One configuration for all your AI coding agents.**

[![CI](https://github.com/smapira/ai-adapter-01/actions/workflows/ci.yml/badge.svg)](https://github.com/smapira/ai-adapter-01/actions/workflows/ci.yml)[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)

Manage and sync your AI agent configuration across Claude Code, Codex, Cursor, VS Code, OpenCode and more.

```bash
# Get started in 3 commands
pip install ai-adapter
ai-adapter init
ai-adapter start <your-config-repo-url>
```

```text
            ┌─────────────┐
            │  ai-adapter  │
            └──────┬──────┘
       ┌───────────┼───────────┐
       ▼           ▼           ▼
 ┌─────────┐ ┌─────────┐ ┌─────────┐
 │ Claude  │ │  Codex  │ │  Cursor │
 │  Code   │ │   CLI   │ │  rules  │
 └─────────┘ └─────────┘ └─────────┘
     ▼           ▼           ▼
 ┌─────────┐ ┌─────────┐ ┌─────────┐
 │ VS Code │ │ OpenCode│ │ OpenClaw│
 └─────────┘ └─────────┘ └─────────┘
```

> ## Agent Plugins 1.0.0 Compliant
>
> `ai-adapter` natively supports the **Agent Plugins 1.0.0** open standard
> ([agent-plugins.org](https://agent-plugins.org/)) — the vendor-neutral packaging
> format for skills + MCP servers backed by AWS, Microsoft, OpenAI, Anysphere, and Vercel.
> Build, validate, and distribute portable plugin packages with:
>
> ```bash
> ai-adapter plugin build my-plugin
> ai-adapter plugin validate ./my-plugin
> ```
>
> Your skills and MCP servers become portable across Copilot, Cursor, Codex,
> VS Code, AWS Kiro and more — with a single `plugin.json` manifest.

A CLI tool for managing AI agent instruction files (`.github/instructions` etc.) and scripts in groups. Easily share and migrate settings across environments.

---

## Features

- **Agent Plugins 1.0.0 Compliant**: Native support for the industry-standard plugin format — `plugin build` scaffolds a portable package, `plugin validate` checks `plugin.json` / `mcp.json` / `skills/` against the spec (name rules, server types, `${PLUGIN_ROOT}` placeholders, reserved env keys, SKILL.md frontmatter)
- **Centralized Management**: All data is consolidated under `~/.ai-adapter/`. Centrally manage settings across projects
- **Environment Switching**: Switch agent settings and scripts per environment (e.g., work, home)
- **GitHub Sync**: Use `ai-adapter sync` to sync `~/.ai-adapter/` with a GitHub remote. Easy team sharing and PC migration
- **Agent Binding**: Bind agent names to environments for automatic resolution based on context
- **Skill Management**: Manage and deploy skills in SKILL.md format (`.github/skills/`)
- **Command Management**: Manage and deploy VS Code custom command definitions (`.github/commands/`)
- **Prompt Management**: Manage and deploy prompt templates for AI agents (`.github/prompts/`)
- **MCP Server Management**: Centrally manage MCP server settings and output in each tool format
- **OpenCode Integration**: Generate `opencode.json`/`opencode.jsonc` (JSONC with comments) with MCP, skills (`.claude/skills`, `.agents/skills` compat paths supported), prompts, and agents; symlink `.opencode` → `.github`
- **OpenClaw Integration**: Export MCP servers and skills to OpenClaw format (`--format openclaw`)
- **Cursor Integration**: Export MCP servers and skills to Cursor format (`--format cursor` → `.cursor/mcp.json` + `.cursor/rules/*.mdc`); legacy `.cursorrules` (`--format cursorrules`) and plugin packages (`--format cursor-plugin` → `~/.cursor/plugins/local/`) for migration (design 07)
- **Codex CLI Integration**: Generate `AGENTS.md` for OpenAI Codex CLI (`ai-adapter codex install`)
- **Root-Level Agent Management**: Manage `AGENTS.md`, `CLAUDE.md`, etc. as first-class artifacts, deployable to project root
- **Runtime Monitor (Runtime Plane)**: `ai-adapter monitor` discovers AI agent sessions running in Orca / VS Code / Zed and reports what they are doing — read-only observability (never sends input, never changes IDE settings, never stops processes)

---

## Supported Tools

| Tool | Status | Integration |
|------|--------|-------------|
| **GitHub Copilot** | ✅ Partial | `.github/` (agents, skills, commands, prompts, bins) + `.mcp.json` |
| **Claude Code** | ✅ Partial | `.github/` fallback + `--format claude` → `.claude/` native paths (agents, skills, user MCP) |
| **OpenCode** | ✅ Full | `ai-adapter opencode install` → `opencode.json`/`opencode.jsonc` (+ `.opencode` symlink); `sub-agent get --format opencode --scope user` → `~/.config/opencode/agents/` |
| **Codex CLI** | ✅ Full | `ai-adapter codex install` → `AGENTS.md` |
| **Cursor** | ✅ Skills + MCP | `--format cursor` → `.cursor/rules/*.mdc` + `.cursor/mcp.json`; `--format cursorrules` (legacy) → `.cursorrules`; `--format cursor-plugin` → `~/.cursor/plugins/local/<project>/` |
| **OpenClaw** | ✅ Partial | `--format openclaw` → `~/.openclaw/` (MCP + skills) |
| **Orca** | ✅ Partial | Shared `~/.claude/skills/` + `.mcp.json` via OpenClaw-style export |
| **Gemini CLI** | ✅ Full | `ai-adapter gemini install` → `.gemini/` (settings.json, commands/*.toml, GEMINI.md); `--with-extension` → `~/.gemini/extensions/<name>/`; `command/prompt get --format gemini` → TOML |
| **Zed** | ✅ Full | `ai-adapter zed install` → `AGENTS.md` + `.agents/skills/` (Zed discovery path); `zed validate` checks settings.json/SKILL.md; `skill get-all --format zed` |
| **Agent Plugins 1.0.0** | ✅ Full | `ai-adapter plugin build/validate` (portable packages) |

Not supported yet:

| Tool | Status | Notes |
|------|--------|-------|
| **Continue** | ❌ Planned | `.continuerc.json` rules export is a future task |

Per-file-type details: [LLM Tool Specification Comparison](documents/wiki/LLM-Tool-Comparison.md).

---

## Installation

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (package management)

```bash
# Also installable via pip
pip install ai-adapter

# Or use uv
uv pip install ai-adapter
```

### Upgrade

```bash
# Upgrade via pip
pip install --upgrade ai-adapter

# Upgrade via uv
uv pip install --upgrade ai-adapter

# Upgrade to the latest development version
cd ai-adapter && git pull && uv sync && uv pip install -e .
```

### Development Version

```bash
git clone <repository-url>
cd ai-adapter
uv sync
uv pip install -e .
```

### Verification

```bash
ai-adapter --help
ai-adapter --version
```

---

## Quick Start

```bash
# 1. Initialize
ai-adapter start https://github.com/YOUR-REPO/YOUR-CONFIG.git

# 2. Add an agent file (for .github/agents/, e.g. individual .agent.md files)
ai-adapter sub-agent add ~/my-agents/reviewer.md

# 2b. Add a root-level agent file (for project-root AGENTS.md/CLAUDE.md)
ai-adapter agent add ~/my-agents/AGENTS.md

# 3. Add an environment
ai-adapter env add myhome

# 4. Add a script
ai-adapter bin add --env myhome ~/scripts/deploy.sh

# 5. Add a skill (optionally with --env)
ai-adapter skill add ~/my-skills/database-schema
ai-adapter skill add --env myhome ~/my-skills/database-schema

# 6. Add an MCP server
ai-adapter mcp add github --command npx --args @modelcontextprotocol/server-github

# 7. Deploy to a project
cd your-project
ai-adapter sub-agent get reviewer      # → .github/agents/reviewer.md
ai-adapter agent get AGENTS            # → ./AGENTS.md (project root)
ai-adapter bin get --env myhome deploy   # → .github/bin/deploy.sh
ai-adapter skill get database-schema  # → .github/skills/database-schema/
ai-adapter skill get-all --env myhome # → deploy only myhome skills
ai-adapter mcp get                     # → .mcp.json

# 8. Deploy to OpenClaw (optional, requires OpenClaw installed)
ai-adapter mcp get --format openclaw          # → ~/.openclaw/openclaw.json
ai-adapter skill get-all --format openclaw    # → ~/.openclaw/skills/

# 8b. Deploy to Claude Code native paths (optional)
ai-adapter skill get-all --format claude      # → .claude/skills/
ai-adapter sub-agent get reviewer --format claude  # → .claude/agents/reviewer.md
ai-adapter mcp get --format claude --scope user    # → ~/.claude.json (merged)

# 9. Sync with GitHub (share settings)
ai-adapter sync
```

---

## Command Reference

### `ai-adapter start <URL>`

One-click setup of `~/.ai-adapter/` by linking with a GitHub remote repository.
Attempts to clone, and if that fails, initializes as a new repository.

```bash
# Setup from a new or existing repository
ai-adapter start git@github.com:user/my-agent-config.git
```

### `ai-adapter init`

Initializes the `~/.ai-adapter/` directory and configuration file (creates `agents/`, `bin/`, `skills/`, `commands/`, `prompts/`, `instructions/`, `mcp/` directories).
You can set a remote repository via the `--remote` option or an interactive prompt.

```bash
# Minimal initialization (remote can be set later)
ai-adapter init

# Initialize with a remote specified
ai-adapter init --remote git@github.com:user/my-agent-config.git
```

### `ai-adapter status`

Displays the current status (registration counts, default environment, etc.).

```bash
ai-adapter status
```

### `ai-adapter add-all-rec`

Batch-registers all files under `.github/` and `.mcp.json` into `~/.ai-adapter/`.
Also discovers root-level files (AGENTS.md, AGENT.md, CLAUDE.md, copilot-instructions.md)
and registers them into `~/.ai-adapter/instructions/`.
Run this after cloning a synced repository to automatically restore configuration from files.

```bash
# Run from the project root
ai-adapter add-all-rec
```

### `ai-adapter get-all-rec`

Deploys **all** registered items across all categories to `.github/` at once.
The reverse of `add-all-rec` — runs `sub-agent get-all` + `bin get-all` + `skill get-all` +
`command get-all` + `prompt get-all` + `agent get-all` (root instructions) + `mcp get` in a single command.

| Option | Description |
|--------|-------------|
| `--force` | Overwrite existing files without prompting |
| `--env` | Filter by environment name (only deploy items for this env) |
| `--project-dir`, `-d` | Target project directory (default: current directory) |
| `--no-summary` | Skip the diagnostic summary shown before deployment |

```bash
# Deploy everything from ~/.ai-adapter/ to the current project
ai-adapter get-all-rec

# Deploy only items for a specific environment
ai-adapter get-all-rec --env remote

# Force overwrite to a specific project
ai-adapter get-all-rec --force --project-dir /path/to/project

# Skip the pre-deploy diagnostic summary
ai-adapter get-all-rec --no-summary
```

### `ai-adapter agent`

Manages root-level agent instruction files (`AGENTS.md`, `CLAUDE.md`, `copilot-instructions.md`).
Deploys to **project root** (`./`) by default, or to each platform's user directory with `--scope user`.

| Command | Description |
|---------|------|
| `agent add <path>` | Add a root-level file to `~/.ai-adapter/instructions/` |
| `agent add-rec <dir>` | Recursively register all files in a directory |
| `agent get <name>` | Copy to project root (`./AGENTS.md` etc.) (use `--force` to skip overwrite confirmation) |
| `agent get-all` | Copy all registered root-level files to project root |
| `agent list` | List registered root-level files |
| `agent remove <name>` | Remove a root-level file |
| `agent remove-all` | Remove all root-level files (supports `--force`) |

`agent get` / `agent get-all` accept the following options:

| Option | Description |
|--------|-------------|
| `--format <platform>` | `standard` (default, project root), `cursorrules` (legacy `.cursorrules` at project root), `codex`, `claude`, `opencode`, `gemini`, `zed`, or `cursor` (unsupported → exit 2) |
| `--scope project\|user` | `project` (default) deploys to the project root; `user` deploys to the platform's user directory |
| `--target root\|github-instructions\|github-copilot` | Deploy target: `root` (default) = project root, `github-instructions` = `.github/instructions/`, `github-copilot` = `.github/copilot-instructions.md`. Incompatible with `--format` (error when combined). |
| `--project-dir <dir>` | Target project directory (project scope only; ignored with a warning under `--scope user`) |
| `--force` | Skip overwrite confirmation |

User-scope destinations and filenames:

| `--format` | `--scope user` destination | Filename (mapped by `get-all`) |
|------------|----------------------------|--------------------------------|
| `codex` | `~/.codex/` | `AGENTS.md` |
| `claude` | `~/.claude/` | `CLAUDE.md` |
| `opencode` | `~/.config/opencode/` | `AGENTS.md` |
| `gemini` | `~/.gemini/` | `GEMINI.md` |
| `zed` | `~/.config/zed/` (macOS/Linux), `%APPDATA%\Zed\` (Windows) | `AGENTS.md` |

With `--scope user`, `get-all` maps every registered file to the name its platform
actually reads (e.g. `AGENTS.md` → `CLAUDE.md` for Claude Code). When the mapped name
is already taken, the file keeps its original name and a warning is shown. User-scope
deploys never modify any `.gitignore`.

```bash
ai-adapter agent add ~/my-agents/AGENTS.md
ai-adapter agent list
ai-adapter agent get AGENTS          # → ./AGENTS.md
ai-adapter agent get CLAUDE          # → ./CLAUDE.md
ai-adapter agent get AGENTS --format codex --scope user    # → ~/.codex/AGENTS.md
ai-adapter agent get-all --format claude --scope user      # → ~/.claude/CLAUDE.md (+ mapped names)
ai-adapter agent get AGENTS --target github-instructions   # → ./.github/instructions/AGENTS.md
ai-adapter agent get AGENTS --target github-copilot        # → ./.github/copilot-instructions.md
ai-adapter agent get AGENTS --format cursorrules           # → ./.cursorrules (legacy, single instruction)
ai-adapter agent get-all --format cursorrules              # → ./.cursorrules (all instructions concatenated)
ai-adapter agent remove AGENTS
ai-adapter agent remove-all --force
```

> **Note on `.cursorrules`**: `--format cursorrules` writes the legacy project-root
> `.cursorrules` file for migration purposes only. Cursor officially recommends
> `.cursor/rules/*.mdc` (deploy with `skill get-all --format cursor`); prefer that
> for new setups. `.cursorrules` is a single file, so concatenation only makes
> sense with `get-all`.

### `ai-adapter sub-agent`

Manages `.agent.md` files (for VS Code / GitHub Copilot agent definitions).
Deploys to `.github/agents/` (or `.claude/agents/` with `--format claude`).

| Command | Description |
|---------|------|
| `sub-agent add <path>` | Add an agent file to `~/.ai-adapter/agents/` |
| `sub-agent add-rec <dir>` | Recursively register all agents in a directory |
| `sub-agent get <name>` | Copy an agent to `.github/agents/` (use `--force` to skip overwrite confirmation) |
| `sub-agent get-all` | Copy all registered agents to `.github/agents/` |
| `sub-agent get <name> --format claude` | Copy to `.claude/agents/` as `<name>.md` (`.agent.md` renamed, tools converted) |
| `sub-agent get-all --format claude` | Copy all registered agents to `.claude/agents/` (add `--scope user` for `~/.claude/agents/`) |
| `sub-agent get <name> --format opencode` | Copy to `.github/agents/` (add `--scope user` for `~/.config/opencode/agents/`; original filename kept — OpenCode is extension-agnostic) |
| `sub-agent get-all --format opencode` | Copy all registered agents to `.github/agents/` (add `--scope user` for `~/.config/opencode/agents/`) |
| `sub-agent list` | List registered agents |
| `sub-agent remove <name>` | Remove an agent (use `--keep-file` to keep the file) |
| `sub-agent remove-all` | Remove all agents (supports `--keep-file`, `--force`) |

All commands above accept `--env <env>` to filter or scope by environment (e.g. `sub-agent add --env production reviewer.md`, `sub-agent list --env production`). When adding with `--env`, an agent-env binding is created. When removing with `--env`, only the binding is removed (not the agent itself).

```bash
ai-adapter sub-agent add ~/dotfiles/agents/reviewer.md
ai-adapter sub-agent add --env production ~/dotfiles/agents/reviewer.md
ai-adapter sub-agent list --env production
ai-adapter sub-agent get reviewer
ai-adapter sub-agent remove reviewer --env production
```

### `ai-adapter env`

Manages environment settings.

| Command | Description |
|---------|------|
| `env add <name>` | Add a new environment |
| `env remove <name>` | Remove an environment (cannot remove the default environment) |
| `env list` | List environments (`*` indicates the default environment) |
| `env default` | Show the current default environment name |
| `env set-default <name>` | Change the default environment |
| `env link-agent <agent> <env>` | Bind an agent to an environment |
| `env unlink-agent <agent>` | Unbind an agent |
| `env remove-all` | Remove all environments except the default (supports `--force`) |

```bash
ai-adapter env add office
ai-adapter env list
ai-adapter env set-default office
ai-adapter env link-agent reviewer office
ai-adapter env remove-all --force
```

### `ai-adapter bin`

Manages script files. `[env]` is optional; if omitted, environment resolution logic applies.

| Command | Description |
|---------|------|
| `bin add --env <env> <path>` | Add a script to `~/.ai-adapter/bin/` (environment resolution applies when --env is omitted) |
| `bin add-rec <dir>` | Recursively register all scripts in a directory |
| `bin get --env <env> <name>` | Copy a script to `.github/bin/` (environment resolution applies when --env is omitted) |
| `bin get-all` | Copy all registered scripts to `.github/bin/` |
| `bin list --env <env>` | List scripts (when --env is omitted, shows all environments) |
| `bin remove --env <env> <name>` | Unregister a script (environment resolution applies when --env is omitted) |
| `bin remove-all` | Unregister all scripts (supports `--force`) |
| `bin add-path` | Output and apply shell configuration to add `.github/bin/` to PATH |

```bash
ai-adapter bin add --env myhome ~/scripts/deploy.sh
ai-adapter bin list
ai-adapter bin get deploy
ai-adapter bin remove deploy
ai-adapter bin remove-all --force
```

The `--env` flag is optional; when omitted, environment resolution logic applies.

### `ai-adapter skill`

Manages skills (directories containing SKILL.md).

| Command | Description |
|---------|------|
| `skill add <path>` | Add a skill directory to `~/.ai-adapter/skills/` |
| `skill add-rec <dir>` | Recursively register all skills in a directory |
 | `skill get <name>` | Copy a skill to `.github/skills/` (add `--format` for other targets) |
 | `skill get <name> --format cursor-plugin` | Install a skill as a Cursor plugin package at `~/.cursor/plugins/local/<project>/` (manifest + skills/) |
 | `skill get-all` | Copy all registered skills to `.github/skills/` |
 | `skill get-all --format openclaw` | Copy all registered skills to `~/.openclaw/skills/` |
 | `skill get-all --format cursor` | Deploy skills to `.cursor/rules/` as `*.mdc` (Cursor rules) |
 | `skill get-all --format cursor-plugin` | Install all skills as a Cursor plugin package at `~/.cursor/plugins/local/<project>/` |
 | `skill get-all --format claude` | Deploy skills to `.claude/skills/` (add `--scope user` for `~/.claude/skills/`) |
 | `skill get-all --format zed` | Deploy skills to Zed's discovery path `.agents/skills/` (add `--scope user` for `~/.agents/skills/`) |
 | `skill list` | List registered skills (filter with `--tag`) |
 | `skill remove <name>` | Remove a skill (use `--purge` to also delete files) |
 | `skill remove-all` | Remove all skills (supports `--purge`, `--force`) |
 | `skill search <keyword>` | Search skills by keyword (filter with `--tag`) |
| `skill link-agent <skill> <agent>` | Bind a skill to an agent |

All commands above accept `--env <env>` to filter or scope by environment, and `--agent <agent>` on add commands for env resolution (e.g. `skill add --env production ~/skills/db/`, `skill get-all --env staging`).

```bash
ai-adapter skill add ~/skills/database-schema/
ai-adapter skill add --env production ~/skills/database-schema/
ai-adapter skill list --env production
ai-adapter skill get database-schema
ai-adapter skill get-all --env staging --force
ai-adapter skill search prisma
```

### `ai-adapter mcp`

Manages MCP server settings.

| Command | Description |
|---------|------|
| `mcp add <name>` | Add an MCP server setting (with `--command`, `--args`, etc.) |
| `mcp add --file <path>` | Batch-import MCP server settings from `.mcp.json` |
| `mcp remove <name>` | Remove an MCP server setting |
| `mcp list` | List MCP servers (filter with `--tool`, `--env`) |
| `mcp get --path <dir>` | Export MCP settings to `.mcp.json` (default: current directory) |
| `mcp get --env <env>` | Export MCP settings filtered by environment |
 | `mcp get --format openclaw` | Export MCP settings to `~/.openclaw/openclaw.json` (server-name-based merge) |
 | `mcp get --format cursor` | Export MCP settings to `.cursor/mcp.json` (Cursor format) |
 | `mcp get --format claude --scope user` | Merge MCP settings into `~/.claude.json` (`.bak` backup, other keys preserved) |
 | `mcp get --format vscode` | Export MCP settings to `.vscode/mcp.json` (VS Code `servers` + `type: stdio` format) |
 | `mcp get --format gemini` | Merge MCP settings into `.gemini/settings.json` or `~/.gemini/settings.json` (`.bak` backup, other keys preserved) |
| `mcp remove-all` | Remove all MCP server settings (supports `--force`) |

```bash
# Interactive addition
ai-adapter mcp add github --command npx --args @modelcontextprotocol/server-github

# Batch-import from .mcp.json
echo '{"mcpServers":{"github":{"command":"npx","args":["@modelcontextprotocol/server-github"]}}}' > .mcp.json
ai-adapter mcp add --file .mcp.json

# List
ai-adapter mcp list

# Export to current directory (standard format)
ai-adapter mcp get
# Export only servers for a specific environment
ai-adapter mcp get --env remote
# Export to a specified directory
ai-adapter mcp get --path /path/to/project
# Export to OpenClaw format (~/.openclaw/openclaw.json)
ai-adapter mcp get --format openclaw
# Export to OpenClaw format with custom path (no merge, new file)
ai-adapter mcp get --format openclaw --path /path/to/output
```

### `ai-adapter plugin`

Builds and validates **Agent Plugins 1.0.0** packages (https://agent-plugins.org/).

| Command | Description |
|---------|------|
| `plugin build <name>` | Scaffold a new 1.0.0 package layout (`plugin.json`, `mcp.json`, `skills/`) |
| `plugin validate <path>` | Validate a plugin package against the 1.0.0 spec |
| `plugin validate --json` | Output the validation result as JSON |
| `plugin validate --strict` | Treat warnings (e.g. missing mcp.json) as failures too |

Exit codes reflect the result: `0` on success, non-zero on failure — safe to use in CI.

```bash
# Scaffold a new portable plugin
ai-adapter plugin build my-plugin --description "AI agent skills and MCP servers"

# Validate a plugin package
ai-adapter plugin validate ./my-plugin
# → ✓ Plugin package is valid.

# JSON output for CI
ai-adapter plugin validate ./my-plugin --json
```

The `plugin build` name must follow the 1.0.0 rules: 1-64 chars, lowercase
alphanumeric / hyphens / periods, no leading/trailing separator. `plugin validate`
checks `plugin.json` manifest (`$schema`, `name`, `author`, field types),
`mcp.json` (`type: stdio|streamable-http|sse`, single-token `command`,
`${PLUGIN_ROOT}` paths, reserved env keys, HTTPS for non-loopback URLs),
and `skills/` (`SKILL.md` with `name`/`description` frontmatter).

### `ai-adapter command`

Manages VS Code custom command definitions (`.sh`, `.py`, `.js`, etc.).

| Command | Description |
|---------|------|
| `command add <path>` | Add a command file to `~/.ai-adapter/commands/` |
| `command add-rec <dir>` | Recursively register all files in a directory |
| `command get <name>` | Copy a command to `.github/commands/` |
| `command get <name> --format opencode --scope user` | Copy to `~/.config/opencode/commands/` (OpenCode auto-discovers user commands) |
| `command get <name> --format gemini` | Convert to Gemini TOML at `.gemini/commands/<name>.toml` (nested `dir/name` supported) |
| `command get-all` | Copy all registered commands to `.github/commands/` |
| `command list` | List registered commands |
| `command remove <name>` | Remove a command |
| `command remove-all` | Remove all commands (supports `--force`) |

All commands above accept `--env <env>` to filter or scope by environment, and `--agent <agent>` on add commands for env resolution.

```bash
ai-adapter command add ~/scripts/deploy.sh
ai-adapter command add --env production ~/scripts/deploy.sh
ai-adapter command list --env production
ai-adapter command get deploy
ai-adapter command remove deploy
```

### `ai-adapter prompt`

Manages prompt templates for AI agents.

| Command | Description |
|---------|------|
| `prompt add <path>` | Add a prompt file to `~/.ai-adapter/prompts/` |
| `prompt add-rec <dir>` | Recursively register all files in a directory |
| `prompt get <name>` | Copy a prompt to `.github/prompts/` |
| `prompt get <name> --format gemini` | Convert to Gemini TOML at `.gemini/commands/<name>.toml` |
| `prompt get-all` | Copy all registered prompts to `.github/prompts/` |
| `prompt list` | List registered prompts |
| `prompt remove <name>` | Remove a prompt |
| `prompt remove-all` | Remove all prompts (supports `--force`) |

All commands above accept `--env <env>` to filter or scope by environment, and `--agent <agent>` on add commands for env resolution.

```bash
ai-adapter prompt add ~/prompts/code-review.md
ai-adapter prompt add --env production ~/prompts/code-review.md
ai-adapter prompt list --env production
ai-adapter prompt get code-review
ai-adapter prompt remove code-review
```

### `ai-adapter opencode`

Manages OpenCode integration settings.

| Command | Description |
|---------|------|
| `opencode alias` | Create a symbolic link `.opencode` → `.github` |
| `opencode install` | Generate `opencode.json` in the current directory (includes MCP, skills, prompts, and agents) |
| `opencode install --format jsonc` | Generate `opencode.jsonc` with explanatory comments (prompts if `opencode.json` already exists; both files may coexist) |
| `opencode install --with-compat-skills` | Add `.claude/skills` and `.agents/skills` to `skills.paths` (default keeps `.github/skills` only) |
| `opencode uninstall` | Remove `opencode.json` / `opencode.jsonc` |
| `opencode validate` | Validate `opencode.json` (or `opencode.jsonc`) schema and agent file formats; `opencode.jsonc` alone is valid, `opencode.json` takes precedence |
| `opencode validate --fix` | Automatically fix array-format tools to object format |
| `opencode validate --config-only` | Validate only the config file (skip agent file validation) |

```bash
# Create an alias from .opencode to .github
ai-adapter opencode alias

# Generate an opencode.json with MCP servers, skills, and agents
ai-adapter opencode install

# Generate opencode.jsonc with comments instead
ai-adapter opencode install --format jsonc

# Include .claude/skills and .agents/skills in skills.paths
ai-adapter opencode install --with-compat-skills

# Remove
ai-adapter opencode uninstall

# Validate and fix agent files
ai-adapter opencode validate
ai-adapter opencode validate --fix
```

### `ai-adapter codex`

Manages Codex CLI integration. Generates `AGENTS.md` in plain Markdown for OpenAI Codex CLI, and deploys MCP servers / skills to Codex native paths.

| Command | Description |
|---------|------|
| `codex install` | Generate `AGENTS.md` in the current directory from registered agents, instructions, and skills |
| `codex install --force` | Overwrite existing `AGENTS.md` without prompting |
| `codex uninstall` | Remove `AGENTS.md` from the current directory |
| `mcp get --format codex` | Merge MCP servers into `.codex/config.toml` (project scope; comment-preserving text-splice) |
| `mcp get --format codex --scope user` | Merge into `~/.codex/config.toml` |
| `skill get-all --format codex` | Deploy skills to `.agents/skills/` (project) |
| `skill get-all --format codex --scope user` | Deploy to `~/.agents/skills/` (user, spec-compliant path) |
| `skill get-all --format codex --scope user --also-codex-dir` | Also mirror into `~/.codex/skills/` (compat opt-in) |

```bash
# Generate AGENTS.md for Codex CLI
ai-adapter codex install

# Force overwrite
ai-adapter codex install --force

# Remove
ai-adapter codex uninstall

# MCP → .codex/config.toml (comments in other sections preserved)
ai-adapter mcp get --format codex
ai-adapter mcp get --format codex --scope user

# Skills → .agents/skills/ (spec-compliant path)
ai-adapter skill get-all --format codex --scope user
```

**Codex native paths**:
- Project: `.codex/config.toml`, `.agents/skills/`
- User: `~/.codex/config.toml`, `~/.agents/skills/`
- `auth.json` is never read or written (security)

### `ai-adapter vscode`

Manages VS Code editor configuration under `.vscode/`. Covers MCP server export (`mcp.json`) and extension recommendations (`extensions.json`). User settings (`settings.json`), debug configs (`launch.json`), and task definitions (`tasks.json`) are detected by `scan` but not managed.

| Command | Description |
|---------|------|
| `vscode install` | Generate `.vscode/mcp.json` from registered MCP servers (merge with `.bak` backup) |
| `vscode install --project-dir <path>` | Generate `.vscode/mcp.json` in a specific project |
| `vscode extension add <id>` | Add an extension to `.vscode/extensions.json` recommendations |
| `vscode extension list` | List recommended extensions |
| `vscode validate` | Validate `.vscode/mcp.json` and `.vscode/extensions.json` (JSON parse + schema) |
| `vscode validate --json` | Structured JSON output for CI |
| `mcp get --format vscode` | Export MCP settings to `.vscode/mcp.json` (same as install) |

```bash
# Generate .vscode/mcp.json from registered MCP servers
ai-adapter vscode install

# Add a recommended extension
ai-adapter vscode extension add ms-vscode.copilot-chat

# List recommended extensions
ai-adapter vscode extension list

# Validate VS Code configuration
ai-adapter vscode validate
ai-adapter vscode validate --json
```

**VS Code MCP format** (differs from Claude Code's `.mcp.json`):

```json
{
  "servers": {
    "github": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_TOKEN": "${env:GITHUB_TOKEN}" }
    }
  }
}
```

- Uses `servers` key (not `mcpServers`) with `type: "stdio"` entries
- Env values use VS Code's `${env:KEY}` setting-variable syntax
- Only stdio servers are exported; http/sse servers are skipped with a warning
- Merge preserves unmanaged servers and takes a `.bak` backup

**VS Code paths**:
- `.vscode/mcp.json` — MCP server definitions (managed)
- `.vscode/extensions.json` — recommended extensions (managed)
- `.vscode/settings.json`, `.vscode/launch.json`, `.vscode/tasks.json` — detected by `scan` only

### `ai-adapter gemini`

Manages Gemini CLI configuration under `.gemini/` (project) or `~/.gemini/` (user). Covers MCP export (`settings.json` `mcpServers`), custom commands (Markdown → TOML), context deployment (`GEMINI.md`), extension manifests, and validation.

| Command | Description |
|---------|------|
| `gemini install` | Generate `.gemini/settings.json`, `.gemini/commands/*.toml`, and `GEMINI.md` from the store |
| `gemini install --scope user` | Same, deployed under `~/.gemini/` |
| `gemini install --project-dir <path>` | Install into a specific project (default: current directory) |
| `gemini install --with-extension` | Also generate `~/.gemini/extensions/<name>/gemini-extension.json` |
| `gemini validate` | Validate settings.json, command TOMLs, and extension manifests |
| `gemini validate --json` | Structured JSON output for CI |
| `command get <name> --format gemini` | Convert one command to `.gemini/commands/<name>.toml` |
| `prompt get <name> --format gemini` | Convert one prompt to `.gemini/commands/<name>.toml` |
| `mcp get --format gemini` | Merge MCP servers into `.gemini/settings.json` (`.bak` backup) |

```bash
# Install everything from the store into .gemini/
ai-adapter gemini install

# Install into ~/.gemini/ (user scope)
ai-adapter gemini install --scope user

# Install + generate an extension manifest (registered via gemini extensions install)
ai-adapter gemini install --with-extension

# Validate the configuration
ai-adapter gemini validate
ai-adapter gemini validate --json
```

**Gemini settings.json format** (standard `mcpServers` key, `${ENV_KEY}` env references):

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_TOKEN": "${GITHUB_TOKEN}" }
    }
  }
}
```

- Merge preserves unmanaged servers and non-MCP keys (model, theme, …); a `.bak` backup is taken
- Commands/prompts export as TOML (`description` + triple-quoted `prompt`); nested commands (`dir/name`) become `.gemini/commands/dir/name.toml`
- `--with-extension` writes the manifest **only** to `~/.gemini/extensions/<name>/` (Gemini does not read project-root manifests) and prints the `gemini extensions install` registration command

**Gemini CLI paths**:
- `.gemini/settings.json` / `~/.gemini/settings.json` — MCP servers (managed)
- `.gemini/commands/**/*.toml` / `~/.gemini/commands/**/*.toml` — custom commands (managed)
- `GEMINI.md` / `~/.gemini/GEMINI.md` — context instructions (managed)
- `~/.gemini/extensions/<name>/gemini-extension.json` — extension manifests (generated by `--with-extension`)

### `ai-adapter zed`

Manages Zed editor configuration. Instructions deploy as `AGENTS.md` (project root or the OS-specific Zed user directory); skills deploy to Zed's actual discovery path `.agents/skills/` (project) / `~/.agents/skills/` (global) — **not** `.zed/skills/`, which Zed never searches. `settings.json` is **validate-only** in Phase A: Zed's settings carry user-owned editor preferences (theme, font, LSP), so ai-adapter never generates or merges them.

| Command | Description |
|---------|------|
| `zed install` | Deploy `AGENTS.md` (instructions concatenated) + `.agents/skills/` from the store |
| `zed install --scope user` | Same, under the OS-specific Zed user dir + `~/.agents/skills/` |
| `zed install --project-dir <path>` | Install into a specific project (default: current directory) |
| `zed install --force` | Overwrite existing `AGENTS.md` / skill directories without prompting |
| `zed validate` | Check AGENTS.md existence, settings.json JSON parse, SKILL.md frontmatter |
| `zed validate --json` | Structured JSON output for CI |
| `skill get-all --format zed` | Deploy all skills to `.agents/skills/` (`--scope user` → `~/.agents/skills/`) |
| `agent get <name> --format zed --scope user` | Deploy an instruction to the Zed user dir as `AGENTS.md` |

```bash
# Install everything from the store (AGENTS.md + .agents/skills/)
ai-adapter zed install

# Install into the OS-specific Zed user directory
ai-adapter zed install --scope user

# Validate the configuration
ai-adapter zed validate
ai-adapter zed validate --json
```

**Zed paths** (OS-dependent user dir via `config.get_zed_user_dir()`):

| Path | Scope | Managed |
|------|-------|---------|
| `AGENTS.md` / `<Zed user dir>/AGENTS.md` | Project / User | `zed install` |
| `.agents/skills/<name>/SKILL.md` / `~/.agents/skills/` | Project / User | `zed install`, `skill get-all --format zed` |
| `.zed/settings.json` / `<Zed user dir>/settings.json` | Project / User | `zed validate` (detect-only) |
| `<Zed user dir>/keymap.json`, `.zed/tasks.json` | User / Project | `scan` (detect-only) |

- User dir: `~/.config/zed/` (macOS/Linux, XDG config dir), Windows `%APPDATA%\Zed\`
- Zed does not support nested skills — each skill must be a direct child of the skills root
- Zed's MCP servers use the `context_servers` key in `settings.json`; merge support is a Phase B feature

### Claude Code Integration

`ai-adapter` deploys to Claude Code's **native paths** (`.claude/`) with the `--format claude` option. Existing `.github/` deployment remains the default (`--format standard`).

| Command | Description |
|---------|------|
| `skill get-all --format claude` | Deploy skills to `.claude/skills/` (`--scope user` → `~/.claude/skills/`) |
| `sub-agent get <name> --format claude` | Deploy an agent to `.claude/agents/<name>.md` (`.agent.md` renamed, array tools converted) |
| `sub-agent get-all --format claude` | Deploy all agents to `.claude/agents/` (`--scope user` → `~/.claude/agents/`) |
| `mcp get --format claude --scope user` | Merge MCP servers into `~/.claude.json` (`.bak` backup; `projects` etc. preserved) |
| `mcp get --format claude` | Project scope → `.mcp.json` (same as `--format standard`; Claude Code reads it natively) |

```bash
# Skills → .claude/skills/ (project) or ~/.claude/skills/ (user)
ai-adapter skill get-all --format claude
ai-adapter skill get-all --format claude --scope user --force

# Agents → .claude/agents/ (.agent.md is renamed to .md; tools become object format)
ai-adapter sub-agent get reviewer --format claude
ai-adapter sub-agent get-all --format claude --scope user

# User-scope MCP → ~/.claude.json (merges mcpServers, keeps Claude Code's own keys)
ai-adapter mcp get --format claude --scope user
```

Key design principles:
- **Native paths** — project deploys go to `.claude/agents/` and `.claude/skills/`; user deploys to `~/.claude/` via `--scope user`
- **`.agent.md` → `.md`** — Claude Code reads plain `.md` agent files; array-format `tools` is converted to object format on deploy (the store copy is never modified)
- **Project MCP = `.mcp.json`** — Claude Code reads project MCP servers from `.mcp.json` (already produced by `mcp get --format standard`); `--format claude --scope project` writes the same file
- **User MCP = `~/.claude.json`** — only the `mcpServers` key is merged; other keys (project history, permissions) are preserved verbatim, and a `.bak` backup is taken first
- **`doctor` validates `~/.claude.json`** — the `mcpServers` subtree shape is checked read-only during `ai-adapter doctor`
- **`scan` detects project `.claude/`** — `ai-adapter scan` reports `.claude/agents/` and `.claude/skills/` with tool `claude` (alongside the existing user-scope detection)

### OpenClaw Integration

`ai-adapter` can export configurations to OpenClaw (a personal AI assistant with multi-channel gateway) using the `--format openclaw` option on existing commands.

| Command | Description |
|---------|------|
| `mcp get --format openclaw` | Export MCP servers to `~/.openclaw/openclaw.json` (server-name-based merge preserves existing servers) |
| `skill get-all --format openclaw` | Deploy skills to `~/.openclaw/skills/` (preserves non-ai-adapter skills) |

```bash
# Export MCP servers to OpenClaw format
ai-adapter mcp get --format openclaw

# Export MCP servers to a custom location (new file, no merge)
ai-adapter mcp get --format openclaw --path /path/to/output

# Deploy all skills to OpenClaw
ai-adapter skill get-all --format openclaw --force
```

Key design principles:
- **`${VAR}` format** for env values — resolved by OpenClaw at load time from `~/.openclaw/.env`
- **Server-name-based merge** — existing non-ai-adapter MCP servers in `openclaw.json` are preserved
- **`.bak` backup** — existing `openclaw.json` is backed up before modification
- **No format conversion needed for skills** — both tools use `SKILL.md` with YAML frontmatter

### `ai-adapter bin add-path`

Outputs and applies shell configuration to add the current project's `.github/bin/` to PATH.
This allows you to run `.github/bin/add_task.sh` directly as `add_task.sh`.

```bash
# Interactively select a shell configuration file
ai-adapter bin add-path

# Write directly to zshrc
ai-adapter bin add-path --shell zshrc
ai-adapter bin add-path --shell bash_profile
```

### `ai-adapter uninstall`

Removes `~/.ai-adapter/` and restores the initial state.

| Option | Description |
|-----------|------|
| `--force` | Remove without showing a confirmation prompt |
| `--keep-git` | Keep the Git repository (`.git`) and remove only data |

```bash
ai-adapter uninstall
ai-adapter uninstall --force
ai-adapter uninstall --keep-git
```

### `ai-adapter sync`

Syncs `~/.ai-adapter/` with a GitHub remote.

```bash
ai-adapter sync
```

Internally, the following steps are executed:
1. Check Git repository (run `git init` if uninitialized)
2. `git add -A && git commit`
3. `git pull --rebase origin main`
4. `git push origin main`

### `ai-adapter scan`

Discovers installed AI agent configurations across tools (Claude, Codex, Cursor, OpenCode, VS Code, Gemini CLI, Zed) and shows a summary.
For Claude Code this covers both the user scope (`~/.claude/`) and the project's `.claude/agents/` + `.claude/skills/` (reported with tool `claude`). Gemini CLI detection covers `~/.gemini/`, `.gemini/`, project-root `GEMINI.md`, and installed extension manifests. Zed detection covers the OS-specific user directory (`settings.json`, `AGENTS.md`, `keymap.json`) and project `.zed/settings.json` / `.zed/tasks.json`.

| Option | Description |
|--------|-------------|
| `--json` | Machine-readable JSON output (for CI integration) |
| `--project-dir` | Target project directory (default: current directory) |

```bash
ai-adapter scan                     # Human-readable summary
ai-adapter scan --json              # JSON output
ai-adapter scan --project-dir /path # Scan a specific project
```

Security: authentication files (`auth.json`, `.credentials.json`, `.env`, `*.key`) are automatically excluded from results.

### `ai-adapter doctor`

Health diagnostics and auto-fix for your AI environment.

| Option | Description |
|--------|-------------|
| `--json` | Machine-readable JSON output |
| `--fix` | Apply detected fixes (with backup) |
| `--dry-run` | Preview fixes without applying |
| `--force` | Skip confirmation for destructive actions |

```bash
ai-adapter doctor              # Health summary
ai-adapter doctor --fix        # Auto-fix with backup
ai-adapter doctor --fix --dry-run  # Preview fixes
```

Checks: installed tools, available updates, compatibility issues, configuration validation.

### `ai-adapter monitor`

Runtime Plane command: discovers AI agent sessions running in Orca, VS Code, and Zed, and reports what they are doing. Read-only — it never sends input to agents, never changes IDE settings, and never stops processes.

| Option | Description |
|--------|-------------|
| `--json` | Machine-readable JSON envelope (`{"sessions": [...]}`) |

```bash
ai-adapter monitor          # Plain table: HOST / PROJECT / AGENT / STATE / AGE
ai-adapter monitor --json   # JSON output (lowercase enum values, ISO 8601 datetimes)
```

STATE is derived from the canonical status: `ACTIVE` (working / waiting / blocked), `INACTIVE` (idle / done), `UNKNOWN` (cannot be determined — never guessed).

Observation sources per host (design: Coverage > Precision):

| Host | Discovery path | Source / Confidence |
|------|----------------|---------------------|
| Orca | Official CLI (`orca terminal list --json`, `orca worktree ps --json`) | `cli` / `high` |
| VS Code | Process observation fallback (`ps` + host attribution) | `process` / `low` |
| Zed | Process observation fallback (`ps` + host attribution) | `process` / `low` |

VS Code sessions resolve PROJECT by correlating open-window folders (`windowsState` in VS Code `globalStorage/storage.json`) with per-window directory handles (`lsof`); a session is attributed only when exactly one open folder maps to its window root — ambiguity is never guessed, so shared runtimes (e.g. `copilot-runtime`) may show `-`. AGE comes from `ps etime` for all process-observation sessions.

VS Code / Zed sessions report `status: unknown` until an official session API (e.g. Zed ACP) becomes available — process existence alone is never promoted to working/waiting/done. Missing hosts are skipped gracefully; an empty result is not an error.

### `ai-adapter setup`

Apply named profiles to register skills / MCP / agents / commands in bulk.

| Command | Description |
|---------|------|
| `setup apply <profile>` | Apply a named profile |
| `setup list` | List available profiles |

| Option | Description |
|--------|-------------|
| `--dry-run` | Preview without making changes |
| `--yes` | Skip confirmation prompt |
| `--install-missing` | Auto-install skills not found locally |

```bash
ai-adapter setup list                # List profiles
ai-adapter setup apply web-development  # Apply profile
ai-adapter setup apply web-development --dry-run  # Preview
```

### `ai-adapter pack`

Apply collections of profiles in sequence.

| Command | Description |
|---------|------|
| `pack install <name>` | Apply a pack (multiple profiles) |
| `pack list` | List available packs |

```bash
ai-adapter pack list           # List packs
ai-adapter pack install starter  # Apply pack
```

### `ai-adapter skill install`

Install skills from local cache or GitHub.

| Option | Description |
|--------|-------------|
| `--source` | Source: `github:user/repo` |
| `--force` | Overwrite existing skill |

```bash
ai-adapter skill install database-schema
ai-adapter skill install my-skill --source github:example/ai-skills
```

### `ai-adapter optimize`

Analyze and optimize your AI environment configuration.

| Option | Description |
|--------|-------------|
| `--json` | Machine-readable JSON output |
| `--apply` | Apply recommended optimizations |
| `--dry-run` | Preview changes (default for --apply) |
| `--force` | Skip confirmation prompts |

```bash
ai-adapter optimize              # Read-only analysis
ai-adapter optimize --apply      # Apply optimizations
ai-adapter optimize --apply --dry-run  # Preview
```

### `ai-adapter version`

Show installed skill versions and available updates.

```bash
ai-adapter version
```

---

## Data Storage

All data is stored under `~/.ai-adapter/`.  
Project-level files are deployed to `.github/` (may change in future versions).

```
~/.ai-adapter/
├── config.json                 # Main configuration file
├── agents/                     # AI agent .agent.md files (managed by sub-agent)
│   ├── reviewer.md
│   ├── implementer.md
│   └── researcher.md
├── bin/                        # Script files
│   ├── deploy-prod.sh
│   └── deploy-staging.sh
├── skills/                     # Skill directories
│   ├── database-schema/
│   │   ├── SKILL.md
│   │   └── examples/
│   └── security-review/
│       └── SKILL.md
├── instructions/               # Root-level agent files (managed by agent)
│   ├── AGENTS.md
│   └── CLAUDE.md
└── mcp/                        # MCP server settings
    └── servers.json
```

This directory can be turned into a Git repository and synced across multiple PCs via GitHub.

### Environment Resolution Priority

When `--env` is omitted in `add` / `add-rec` commands (for `bin`, `skill`, `command`, `prompt`):

1. If the `--agent` option is explicitly specified, the bound environment of that agent is used
2. If the relevant agent exists in `agent_bindings`, its bound environment is used
3. If neither applies, `default_env` (default: `"default"`) is used

For `list`, `get`, `get-all`, `remove`, `remove-all` commands, `--env` acts as a filter.
Items with no env set (universal) are always included regardless of the filter.

---

## Configuration File

All settings are stored in `~/.ai-adapter/config.json`.

```json
{
  "version": 1,
  "default_env": "default",
  "agent_bindings": [
    { "agent": "reviewer", "env": "myhome" },
    { "agent": "implementer", "env": "office" }
  ],
  "agents": [
    { "name": "reviewer", "description": "Agent for code review" },
    { "name": "implementer", "description": "Agent for implementation" }
  ],
  "envs": [
    { "name": "default", "description": "Default environment" },
    { "name": "myhome", "description": "Home development environment" },
    { "name": "office", "description": "Office development environment" }
  ],
  "bins": [
    { "name": "deploy-prod.sh", "env": "myhome", "description": "Production deployment" },
    { "name": "format-all.sh", "env": "default", "description": "Code formatting" }
  ],
  "skills": [
    {
      "name": "database-schema",
      "description": "Database schema design and review knowledge",
      "path": "skills/database-schema",
      "tags": ["database", "prisma", "schema"],
      "agent": "reviewer",
      "env": "production"
    }
  ],
  "commands": [
    { "name": "deploy", "content": "#!/bin/bash\necho deploy", "env": "production" }
  ],
  "prompts": [
    { "name": "code-review", "content": "Review checklist...", "env": "staging" }
  ],
  "mcp_servers": [
    {
      "name": "github",
      "command": "npx",
      "args": ["@modelcontextprotocol/server-github"],
      "env_keys": ["GITHUB_TOKEN"],
      "enabled": true,
      "tools": ["vscode", "claude", "cursor"]
    }
  ]
}
```

---

## Use Cases

### Sharing LLM configuration files between office and home

```bash
# Office PC
ai-adapter init
ai-adapter agent add ~/company-agent.md
ai-adapter env add office
ai-adapter sync

# Home PC
git clone <your-ai-adapter-repo> ~/.ai-adapter
ai-adapter agent get company-agent   # → .github/agents/company-agent.md
```

### Migrating to a new PC

```bash
# New PC
git clone <your-ai-adapter-repo> ~/.ai-adapter
ai-adapter bin list                  # Check registered scripts
ai-adapter bin get deploy-prod       # Deploy the required scripts
```

### Different agent settings per project

```bash
ai-adapter env add project-a
ai-adapter env add project-b
ai-adapter agent add reviewer-a.md
ai-adapter env link-agent reviewer-a project-a

# Running in project-a automatically uses the project-a environment
cd /path/to/project-a
ai-adapter bin add deploy.sh
```

---

## Development

### Development Environment

```bash
uv sync
uv pip install -e .
```

### Running Tests

Tests must run inside the sandbox directory (`.testbox/`): the suite operates
on `Path.cwd() / ".github"` (backup → delete → restore), and running it from the
repo root can permanently destroy `.github/workflows` if interrupted.

```bash
# All tests (sandboxed — safe)
bash scripts/run_tests.sh

# Verbose output
bash scripts/run_tests.sh -v

# Single test file / module
bash scripts/run_tests.sh tests/test_env.py
bash scripts/run_tests.sh tests/test_env.py -k add   # keyword filter

# Pytest (optional; cwd is isolated per-test by tests/conftest.py)
uv run pytest
```

`run_tests.sh` uses pytest (not `unittest discover`) intentionally:
`tests/conftest.py`, which chdirs every test into a fresh temp directory, is a
pytest plugin. Under a bare unittest run, `add_to_gitignore()` walks up from
`.testbox/` to the real repo's `.git` and appends test artefacts to the real
`.gitignore`, polluting the repository.

### Linter and Type Checking

```bash
uv run ruff check .
uv run ruff format .
uv run mypy src/
```

---

## Project Structure

```
ai-adapter/
├── pyproject.toml              # Project settings, dependencies, entry points
├── README.md                   # This file
├── LICENSE                     # MIT License
├── .gitignore                  # Git ignore settings
├── src/
│   └── ai_adapter/
│       ├── __init__.py         # Version information
│       ├── __main__.py         # python -m ai_adapter support
│       ├── cli.py              # CLI entry point (registers all subcommands)
│       ├── config.py           # Read/write ~/.ai-adapter/config.json
│       ├── models.py           # Data models (dataclass)
│       ├── diff.py             # Sync diff comparison
│       ├── git.py              # Git operation wrapper
│       ├── sync.py             # sync command (GitHub sync)
│       ├── agent_format.py     # Agent file YAML format utilities
│       ├── agent_plugins.py    # Agent Plugins 1.0.0 validation (plugin.json / mcp.json / skills)
│       ├── commands/           # Subcommand implementations
│       │   ├── agent.py        # agent subcommand
│       │   ├── bin.py          # bin subcommand
│       │   ├── command.py      # command subcommand
│       │   ├── env.py          # env subcommand
│       │   ├── get_all_rec.py  # get-all-rec subcommand (deploy everything + summary)
│       │   ├── instruction.py  # instruction subcommand (root AGENTS.md etc.)
│       │   ├── mcp.py          # mcp subcommand
│       │   ├── plugin.py       # plugin subcommand (Agent Plugins build/validate)
│       │   ├── prompt.py       # prompt subcommand
│       │   └── skill.py        # skill subcommand
│       └── providers/          # External tool integrations
│           ├── opencode.py     # OpenCode integration (install/alias/uninstall)
│           ├── openclaw.py     # OpenClaw integration (MCP + skills export)
│           ├── cursor.py       # Cursor integration (MCP + skills export to .cursor/)
│           └── codex.py        # Codex CLI integration (AGENTS.md generation)
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_agent.py
│   ├── test_env.py
│   ├── test_bin.py
│   ├── test_skill.py
│   ├── test_mcp.py
│   ├── test_sync.py
│   ├── test_git.py
│   ├── test_cli.py
│   ├── test_cursor.py          # Cursor integration tests
│   └── test_instruction.py
└── examples/
    └── sample-config.json      # Sample configuration file
```

---

## Tech Stack

| Category | Technology |
|------|---------|
| Language | Python 3.10+ |
| CLI Framework | Click |
| Configuration File | JSON (standard library) |
| Testing | pytest — sandboxed via `scripts/run_tests.sh` into `.testbox/`, with per-test cwd isolation (`tests/conftest.py`) |
| Package Management | uv |

---

## License

MIT License
