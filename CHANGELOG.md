# Changelog

## [0.16.0] - 2026-07-27

### Added

- **OpenClaw MCP export** (`mcp get --format openclaw`): Export MCP server configurations
  to OpenClaw format (`mcp.servers` in `openclaw.json`)
  - Server-name-based merge preserves existing non-ai-adapter servers
  - `enabled` flag per server, `${VAR}` env format, `.bak` backup
  - `--force` to skip confirmation prompt
- **OpenClaw skills export** (`skill get-all --format openclaw`): Deploy skills to
  `~/.openclaw/skills/` using native SKILL.md format (identical format, no conversion needed)
  - Existing non-ai-adapter skills in target directory are preserved
  - Clear warning when OpenClaw is not installed

### Changed

- **`mcp get`**: Added `--format`/`-f` option (`standard` | `openclaw`, default: `standard`).
  Existing logic refactored into `_mcp_get_standard()` for clarity.
- **`skill get-all`**: Added `--format`/`-f` option (`standard` | `openclaw`, default: `standard`).
  Deployment logic refactored into `_deploy_skills_standard()` and `_deploy_skills_openclaw()`.

## [0.15.0] - 2026-07-26

### Added

- **`get-all-rec` top-level command**: Deploy all registered items across all categories
  to `.github/` in a single command (reverse of `add-all-rec`)
  - `agents/`, `bin/`, `skills/`, `commands/`, `prompts/`, and `.mcp.json`
  - Supports `--force` to skip confirmation prompts
  - Supports `--project-dir`/`-d` to target a specific project directory

## [0.13.0] - 2026-07-25

### Changed

- **`add-all-rec`**: Improved user experience when `.github/` directory is missing
  - Auto-creates `.github/` instead of continuing silently with "Total: 0"
  - Each section (agents/bin/skills/.mcp.json) now always reports its status:
    - `N registered` when files exist
    - `skip (directory not found)` when the directory is absent
  - Eliminates confusing "All imports completed: Total: 0" with no explanation

## [0.12.0] - 2026-07-25

### Added

- **`opencode validate` subcommand**: Validate agent file formats in `.github/agents/`
  - `--fix`: Automatically convert array-format `tools` to object format
  - `--quiet`: Minimal output for CI integration (exit code 0 = valid, 1 = invalid)
  - `--project-dir`: Target project directory
- **`agent_format.py` module**: Centralised YAML format utilities for agent files
  - `parse_frontmatter()`: Parse YAML frontmatter (moved from `agent.py`)
  - `convert_tools_to_object()`: Convert array-format `tools` to object format
  - `convert_agent_file()`: Destructive in-place format conversion
  - `validate_agent_file()`: Validate `tools` field format
  - `batch_validate_and_fix()`: Directory-level validation and fix

### Changed

- **`agent get` / `agent get-all`**: Added `--fix` option for destructive format conversion.
  Default behaviour changed to **validate + warn only** (no auto-conversion).
- **`agent add` / `agent add-rec`**: Replaced `--no-convert` with `--fix` option.
  Default behaviour changed to **validate + warn only** (no auto-conversion).
- **`opencode alias`**: Now validates agent files before symlink creation and
  prompts to fix any format issues.

## [0.11.0] - 2026-07-25

### Changed

- **Renamed `mcp export` → `mcp get`**: Consistent with agent/bin/skill/command/prompt naming
- **Merged `mcp load` into `mcp add --file`**: Bulk import from `.mcp.json` is now
  `ai-adapter mcp add --file .mcp.json` instead of the removed `mcp load` command

## [0.10.0] - 2026-07-23

### Changed

- **Complete i18n: All remaining Japanese text translated to English**:
  All source files (git.py, sync.py, models.py, skill.py, mcp.py, prompt.py)
  and all test files are fully English across docstrings, error messages,
  CLI output, and test content.

## [0.9.0] - 2026-07-23

### Changed

- **i18n: All user-facing text translated to English**: README, CHANGELOG, CLI help,
  docstrings, and error messages

## [0.8.0] - 2026-07-23

### Added

- **`command` subcommand**: Manage VS Code custom command definitions
  - `command add <path>` / `command list` / `command get <name>` / `command remove <name>`
  - `command add-rec <dir>` / `command get-all` / `command remove-all [--force]`
- **`prompt` subcommand**: Manage prompt templates
  - `prompt add <path>` / `prompt list` / `prompt get <name>` / `prompt remove <name>`
  - `prompt add-rec <dir>` / `prompt get-all` / `prompt remove-all [--force]`
- **`agent get --force`**: `--force` option to skip overwrite confirmation when deploying agents
- **`Config.from_dict()` validation**: Added type checking for all fields in config files
  - Display user-friendly error messages when loading a broken `config.json`

### Changed

- **`command get` / `prompt get`**: Changed extension list from hardcoded to dynamic scanning
  - Auto-detect any extension (`.rb`, `.js`, `.json`, `.yaml`, etc.)
- **`skill get-all`**: Fixed docstring pointing to `.claude/skills/` to `.github/skills/`

## [0.7.0] - 2026-07-22

### Added

- **`add-all-rec` command**: Bulk register all items from `.github/` and `.mcp.json`
  - `.github/agents/` → `~/.ai-adapter/agents/`
  - `.github/bin/` → `~/.ai-adapter/bin/`
  - `.github/skills/` → `~/.ai-adapter/skills/`
  - `.mcp.json` → `mcp_servers` in `config.json`

## [0.6.1] - 2026-07-21

### Changed

- **`agent add-rec` / `bin add-rec` / `skill add-rec`**: Changed to overwrite behavior (overwrite existing files instead of skipping)

## [0.6.0] - 2026-07-21

### Added

- **`agent add-rec` / `bin add-rec` / `skill add-rec`**: Recursively bulk register all items in a directory
- **`mcp remove-all`**: Remove all MCP server configurations and physically delete `.mcp.json`
- **`mcp load --file`**: Bulk load MCP server configurations from `.mcp.json`

### Changed

- **`agent remove` / `bin remove` / `skill remove`**: Also physically delete deployed files under `.github/` on removal

### Removed

- **`mcp enable` / `mcp disable`**: Removed unnecessary commands (unified with `remove` / `remove-all`)

## [0.5.1] - 2026-07-21

### Changed

- **Moved `export` to `bin add-path`**: Integrated from top-level command to `bin` subcommand
  - `ai-adapter bin add-path` adds `.github/bin/` to PATH

## [0.5.0] - 2026-07-21

### Added

- **`opencode` subcommand**: OpenCode integration settings (`alias`, `install`, `uninstall`)
  - `alias`: Create symbolic link `.opencode` → `.github`
  - `install`: Generate `opencode.json` from template
  - `uninstall`: Remove `opencode.json`
- **`mcp load --file` command**: Bulk load MCP server configurations from `.mcp.json`
- **`bin add-path` command**: Output and apply shell configuration to add current project's `.github/bin/` to PATH
  - Interactive or with `--shell` option, automatically appends to zshrc/bash_profile/bashrc
- **`agent get-all` / `bin get-all` / `skill get-all`**: Bulk deploy all registered items
- **`agent remove-all` / `env remove-all` / `bin remove-all` / `skill remove-all`**: Bulk remove all registered items
- **`skill get-all` / `skill remove-all`**: Bulk deploy/remove skills
- **File-based sync**: Auto-restore via `rebuild_config()`
  - Auto-rebuild configuration from files after successful `sync` pull
  - Auto-rebuild configuration after `start` clone/init
  - Show actual file count in `status`
  - `list` / `get-all` works from filesystem even when config is empty

### Changed

- **`mcp export`**: Changed output destination to current directory, always use `.mcp.json` as output file
  - Can specify output directory with `--path` option
- **Renamed `mcp export` `--tool` option to `--path`**
- **`mcp add`**: Removed `--file` option, simplified to require `--command`
- **`bin` command**: Changed `env` from positional argument (`click.argument`) to `--env` option (`click.option`)
  - Improved to accept only filename as single argument like `bin get script.py`
- **Unified skill deployment directory**: Changed `get_claude_skills_dir()` → `get_github_skills_dir()`
  - Changed `skill get` / `skill get-all` output destination from `.claude/skills/` to `.github/skills/`
  - Unified under `.github/` same as `agent` / `bin`
- **`agent add`**: Read `name` from frontmatter of `.agent.md` file and use as registration name

### Fixed

- **`sync`**: Fixed crash on exit code 1 from `git diff --cached --quiet` (changes exist)
- **`sync`**: Show guide message instead of crash on pull/push failure (no connection/branch mismatch/conflict)
- **`sync`**: Show setup instructions instead of crash when Git user config (user.name/user.email) is not set
- **`skill get-all`**: Fixed crash when hitting existing directory without `--force`

## [0.4.1] - 2026-07-20

### Changed

- **Unified skill deployment directory**: Changed `get_claude_skills_dir()` → `get_github_skills_dir()`
  - Changed `skill get` / `skill get-all` output destination from `.claude/skills/` to `.github/skills/`
  - Unified under `.github/` same as `agent` / `bin`

## [0.4.0] - 2026-07-20

### Added

- **`agent remove-all` command**: Bulk remove all agents (supports `--keep-file`, `--force` options)
- **`env remove-all` command**: Bulk remove all environments except default (`--force` option)
- **`bin remove-all` command**: Bulk unregister all script registrations (`--force` option)

### Changed

- Changed `env` in `bin` command from positional argument (`click.argument`) to `--env` option (`click.option`)
  - Improved to accept only filename as single argument like `bin get script.py`
  - When `--env` is omitted, falls back to environment resolution logic as before

## [0.3.0] - 2026-07-20

### Added

- **`start <URL>` command**: One-shot setup linked with GitHub remote repository
  - Attempts `git clone`, falls back to `git init` + `remote add` on failure
  - Auto-generates `~/.ai-adapter/` directory structure and `config.json`
  - Remote URL saved in `Config.remote` field
- **`init --remote` option**: Initialize with remote URL specified from command line
- **`init` interactive prompt**: Interactively asks for remote URL when `--remote` is not specified (can skip)
- **`sync` interactive input when remote not configured**: Processes in order: saved `config.remote` → manual input → skip
- **`status` remote display**: Display `remote` if saved in config file
- **`git.py`**: Added `clone()`, `add_remote()`, `get_current_branch()` functions
- **`Config.remote` field**: Persist Git remote URL in config file

### Changed

- Improved `init` to perform Git repo initialization + remote setup
- Improved `sync` to not error-exit when remote is not set, but complete via interactive input

## [0.2.0] - 2026-07-20

### Added

- **`uninstall` command**: Remove `~/.ai-adapter/` to restore initial state (supports `--force`, `--keep-git` options)
- **`status` command**: Extended to display skills/mcp registration counts and directory status
- **`CHANGELOG.md`**: Newly created

## [0.1.0] - 2026-07-20

### Added

- **CLI foundation**: CLI entry point using Click framework (`ai-adapter` / `python -m ai_adapter`)
- **`init` command**: Initialize `~/.ai-adapter/` directory (create `agents/`, `bin/`, `skills/`, `mcp/` directories + `config.json`)
- **`status` command**: Display current configuration state (registration counts, default environment, directory status)
- **`agent` subcommand**: Manage AI agent instruction files (`add`, `get`, `list`, `remove`)
  - Save files to `~/.ai-adapter/agents/` and deploy to `.github/agents/`
- **`env` subcommand**: Manage environment settings (`add`, `remove`, `list`, `default`, `set-default`, `link-agent`, `unlink-agent`)
  - Default environment protection (cannot be deleted), agent-environment linking
- **`bin` subcommand**: Manage script files (`add`, `get`, `list`, `remove`)
  - Environment resolution logic when env is omitted (agent binding → default environment)
  - Explicit agent specification via `--agent` option
- **`skill` subcommand**: Manage skill directory (`add`, `get`, `list`, `remove`, `search`, `link-agent`)
  - Auto-parse YAML frontmatter from SKILL.md
  - Deploy to `.claude/skills/`, support tag filters and keyword search
- **`mcp` subcommand**: Manage MCP server settings (`add`, `remove`, `list`, `export`, `enable`, `disable`)
  - Support interactive addition and addition from JSON files
  - `export` outputs to VS Code / Claude / Cursor format (`.vscode/mcp.json`, `.mcp.json`, `.cursor/mcp.json`)
  - Support `--tool`, `--env` filters
- **`sync` command**: Sync `~/.ai-adapter/` with GitHub remote (`git add` → `commit` → `pull --rebase` → `push`)
- **Data models**: Dataclass definitions and JSON serialization for `Agent`, `Env`, `AgentBinding`, `Bin`, `Skill`, `MCPServer`, `Config`
- **Config file management**: Read/write `~/.ai-adapter/config.json` (path overridable via `AI_ADAPTER_CONFIG` environment variable)
- **Git operation wrapper**: Git command wrapper using `subprocess` (`is_repo`, `init_repo`, `add_all`, `commit`, `pull_rebase`, `push`, `has_remote`, `get_remotes`)
- **Tests**: 84 unit tests (Click CliRunner + unittest.mock based file operation/CLI/mock tests)

### Changed

- Changed config file format from YAML (`.ai-adapter.yaml`) to JSON (`config.json`)
- Unified all data storage from project root to `~/.ai-adapter/`

### Removed

- Removed `pyyaml` dependency (due to config file format change to JSON)

---

## Notes

- This version is in early development phase, so the API may change without notice
- Data stored in `~/.ai-adapter/` can be removed with `ai-adapter uninstall`
