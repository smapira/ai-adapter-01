# ai-adapter

**Common management infrastructure CLI tool for AI agent scripts**

A CLI tool for managing AI agent instruction files (`.github/instructions` etc.) and scripts in groups. Easily share and migrate settings across environments.

---

## Features

- **Centralized Management**: All data is consolidated under `~/.ai-adapter/`. Centrally manage settings across projects
- **Environment Switching**: Switch agent settings and scripts per environment (e.g., work, home)
- **GitHub Sync**: Use `ai-adapter sync` to sync `~/.ai-adapter/` with a GitHub remote. Easy team sharing and PC migration
- **Agent Binding**: Bind agent names to environments for automatic resolution based on context
- **Skill Management**: Manage and deploy skills in SKILL.md format (`.github/skills/`)
- **Command Management**: Manage and deploy VS Code custom command definitions (`.github/commands/`)
- **Prompt Management**: Manage and deploy prompt templates for AI agents (`.github/prompts/`)
- **MCP Server Management**: Centrally manage MCP server settings and output in each tool format

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
ai-adapter init

# 2. Add an agent file
ai-adapter agent add ~/my-agents/reviewer.md

# 3. Add an environment
ai-adapter env add myhome

# 4. Add a script
ai-adapter bin add --env myhome ~/scripts/deploy.sh

# 5. Add a skill
ai-adapter skill add ~/my-skills/database-schema

# 6. Add an MCP server
ai-adapter mcp add github --command npx --args @modelcontextprotocol/server-github

# 7. Deploy to a project
cd your-project
ai-adapter agent get reviewer      # → .github/agents/reviewer.md
ai-adapter bin get --env myhome deploy   # → .github/bin/deploy.sh
ai-adapter skill get database-schema  # → .github/skills/database-schema/
ai-adapter mcp get   # → .mcp.json

# 8. Sync with GitHub (share settings)
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

Initializes the `~/.ai-adapter/` directory and configuration file (creates `agents/`, `bin/`, `skills/`, `commands/`, `prompts/`, `mcp/` directories).
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
Run this after cloning a synced repository to automatically restore configuration from files.

```bash
# Run from the project root
ai-adapter add-all-rec
```

```bash
ai-adapter status
```

### `ai-adapter agent`

Manages AI agent instruction files (`.md` etc.).

| Command | Description |
|---------|------|
| `agent add <path>` | Add an agent file to `~/.ai-adapter/agents/` |
| `agent add-rec <dir>` | Recursively register all agents in a directory |
| `agent get <name>` | Copy an agent to `.github/agents/` (use `--force` to skip overwrite confirmation) |
| `agent get-all` | Copy all registered agents to `.github/agents/` |
| `agent list` | List registered agents |
| `agent remove <name>` | Remove an agent (use `--keep-file` to keep the file) |
| `agent remove-all` | Remove all agents (supports `--keep-file`, `--force`) |

```bash
ai-adapter agent add ~/dotfiles/agents/reviewer.md
ai-adapter agent list
ai-adapter agent get reviewer
ai-adapter agent remove reviewer
ai-adapter agent remove-all --force
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
| `skill get <name>` | Copy a skill to `.github/skills/` |
| `skill get-all` | Copy all registered skills to `.github/skills/` |
| `skill list` | List registered skills (filter with `--tag`) |
| `skill remove <name>` | Remove a skill (use `--purge` to also delete files) |
| `skill remove-all` | Remove all skills (supports `--purge`, `--force`) |
| `skill search <keyword>` | Search skills by keyword |
| `skill link-agent <skill> <agent>` | Bind a skill to an agent |

```bash
ai-adapter skill add ~/skills/database-schema/
ai-adapter skill list
ai-adapter skill get database-schema
ai-adapter skill search prisma
ai-adapter skill link-agent database-schema reviewer
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
| `mcp remove-all` | Remove all MCP server settings (supports `--force`) |

```bash
# Interactive addition
ai-adapter mcp add github --command npx --args @modelcontextprotocol/server-github

# Batch-import from .mcp.json
echo '{"mcpServers":{"github":{"command":"npx","args":["@modelcontextprotocol/server-github"]}}}' > .mcp.json
ai-adapter mcp add --file .mcp.json

# List
ai-adapter mcp list

# Export to current directory
ai-adapter mcp get
# Export to a specified directory
ai-adapter mcp get --path /path/to/project
```

### `ai-adapter command`

Manages VS Code custom command definitions (`.sh`, `.py`, `.js`, etc.).

| Command | Description |
|---------|------|
| `command add <path>` | Add a command file to `~/.ai-adapter/commands/` |
| `command add-rec <dir>` | Recursively register all files in a directory |
| `command get <name>` | Copy a command to `.github/commands/` |
| `command get-all` | Copy all registered commands to `.github/commands/` |
| `command list` | List registered commands |
| `command remove <name>` | Remove a command |
| `command remove-all` | Remove all commands (supports `--force`) |

```bash
ai-adapter command add ~/scripts/deploy.sh
ai-adapter command list
ai-adapter command get deploy
ai-adapter command remove deploy
ai-adapter command remove-all --force
```

### `ai-adapter prompt`

Manages prompt templates for AI agents.

| Command | Description |
|---------|------|
| `prompt add <path>` | Add a prompt file to `~/.ai-adapter/prompts/` |
| `prompt add-rec <dir>` | Recursively register all files in a directory |
| `prompt get <name>` | Copy a prompt to `.github/prompts/` |
| `prompt get-all` | Copy all registered prompts to `.github/prompts/` |
| `prompt list` | List registered prompts |
| `prompt remove <name>` | Remove a prompt |
| `prompt remove-all` | Remove all prompts (supports `--force`) |

```bash
ai-adapter prompt add ~/prompts/code-review.md
ai-adapter prompt list
ai-adapter prompt get code-review
ai-adapter prompt remove code-review
ai-adapter prompt remove-all --force
```

### `ai-adapter opencode`

Manages OpenCode integration settings.

| Command | Description |
|---------|------|
| `opencode alias` | Create a symbolic link `.opencode` → `.github` |
| `opencode install` | Generate `opencode.json` in the current directory |
| `opencode uninstall` | Remove `opencode.json` |

```bash
# Create an alias from .opencode to .github
ai-adapter opencode alias

# Generate an opencode.json template
ai-adapter opencode install

# Remove
ai-adapter opencode uninstall
```

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

---

## Data Storage

All data is stored under `~/.ai-adapter/`.  
Project-level files are deployed to `.github/` (may change in future versions).

```
~/.ai-adapter/
├── config.json                 # Main configuration file
├── agents/                     # AI agent instruction files
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
└── mcp/                        # MCP server settings
    └── servers.json
```

This directory can be turned into a Git repository and synced across multiple PCs via GitHub.

### Environment Resolution Priority

When `[env]` is omitted in `bin` commands:

1. If the `--agent` option is explicitly specified, the bound environment of that agent is used
2. If the relevant agent exists in `agent_bindings`, its bound environment is used
3. If neither applies, `default_env` (default: `"default"`) is used

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
      "agent": "reviewer"
    }
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

```bash
# All tests
uv run python -m unittest discover tests

# Specific file
uv run python -m unittest tests/test_env.py

# Verbose output
uv run python -m unittest discover tests -v
```

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
│       ├── cli.py              # CLI entry point
│       ├── config.py           # Read/write ~/.ai-adapter/config.json
│       ├── models.py           # Data models (dataclass)
│       ├── agent.py            # agent subcommand
│       ├── env.py              # env subcommand
│       ├── bin.py              # bin subcommand
│       ├── skill.py            # skill subcommand
│       ├── mcp.py              # mcp subcommand
│       ├── sync.py             # sync command (GitHub sync)
│       └── git.py              # Git operation wrapper
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
│   └── test_cli.py
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
| Testing | unittest (standard library) |
| Package Management | uv |

---

## License

MIT License
