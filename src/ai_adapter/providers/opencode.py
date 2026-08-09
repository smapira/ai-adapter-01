"""opencode subcommand implementation.

Manages .opencode symlinks and opencode.json installation/uninstallation.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import click

from ai_adapter import config as _config
from ai_adapter.agent_format import batch_validate_and_fix, convert_agent_file
from ai_adapter.models import MCPServer


@click.group(name="opencode")
def opencode_group() -> None:
    """Manage OpenCode integration settings."""


def _mcp_server_to_opencode(server: MCPServer) -> dict:
    """Convert ai-adapter MCPServer to opencode.json MCP format.

    ``MCPServer.command`` must be a single token (no spaces).
    ``MCPServer.tools`` field is ignored (opencode has its own tool system).
    """
    entry: dict = {
        "type": "local",
        "command": [server.command] + server.args,
        "enabled": server.enabled,
    }
    if server.env_keys:
        entry["environment"] = {k: f"${{{k}}}" for k in server.env_keys}
    return entry


@opencode_group.command(name="alias")
def opencode_alias() -> None:
    """Create a .opencode → .github symlink in the current directory.

    Creates a .opencode symlink pointing to the absolute path of .github/.
    Before creating the symlink, validates ``.github/agents/*.agent.md``
    files and offers to fix any format issues.
    """
    github_path = Path.cwd().resolve() / ".github"
    opencode_path = Path.cwd().resolve() / ".opencode"

    if not github_path.exists():
        click.echo(f"'.github' directory not found: {github_path}", err=True)
        raise click.ClickException(".github directory does not exist.")

    # Validate agent files before symlink creation
    agents_dir = github_path / "agents"
    if agents_dir.exists():
        errors = batch_validate_and_fix(agents_dir, fix=False)
        if errors:
            click.echo(
                "Warning: the following agent files have array-format tools (expected object format):",
                err=True,
            )
            for err in errors:
                click.echo(f"  {err}", err=True)
            click.echo("")
            if click.confirm("Fix them automatically?"):
                fixed = 0
                for f in sorted(agents_dir.iterdir()):
                    if f.is_file() and str(f).endswith(".agent.md"):
                        if convert_agent_file(f):
                            fixed += 1
                click.echo(f"Fixed {fixed} file(s).")
            else:
                raise click.ClickException("Agent file format validation failed. Run 'opencode validate --fix' to fix.")

    if opencode_path.exists() or opencode_path.is_symlink():
        click.echo("'.opencode' already exists.")
        click.confirm("Replace it?", abort=True)
        if opencode_path.is_symlink() or opencode_path.is_dir():
            import shutil

            if opencode_path.is_symlink() or opencode_path.is_file():
                opencode_path.unlink()
            else:
                shutil.rmtree(opencode_path)

    os.symlink(str(github_path), str(opencode_path))
    _config.add_to_gitignore(opencode_path)
    click.echo(f"Symlink created: {opencode_path} → {github_path}")


@opencode_group.command(name="install")
def opencode_install() -> None:
    """Generate opencode.json in the current directory.

    Dynamically builds the configuration based on what is registered
    in ``~/.ai-adapter/config.json``:

    - Root-level agent files (``AGENTS.md``, ``CLAUDE.md``, etc.) → project root
    - ``.agent.md`` files → ``.github/agents/*.agent.md`` glob
    - ``.github/copilot-instructions.md`` → always included as fallback
    - MCP servers → ``mcp`` section with opencode format
    - Skills → ``skills.paths`` section
    - Prompts → ``command`` section with template + description
    """
    cfg = _config.load_config()
    instructions = _build_instructions(cfg)
    config: dict = {
        "$schema": "https://opencode.ai/config.json",
        "instructions": instructions,
        "permission": _DEFAULT_PERMISSION,
    }

    if cfg:
        _add_mcp_section(config, cfg)
        _add_skills_section(config, cfg)
        _add_prompts_section(config, cfg)

    output_path = Path.cwd() / "opencode.json"

    with open(output_path, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    _config.add_to_gitignore(output_path)
    click.echo(f"opencode.json generated: {output_path}")


_DEFAULT_PERMISSION: dict[str, str] = {
    "read": "ask",
    "edit": "ask",
    "glob": "ask",
    "grep": "ask",
    "list": "ask",
    "bash": "ask",
    "task": "ask",
    "webfetch": "ask",
    "websearch": "ask",
    "todowrite": "ask",
}


def _build_instructions(cfg: _config.Config | None) -> list[str]:
    """Build the instructions array from config."""
    instructions: list[str] = [".github/copilot-instructions.md"]

    if not cfg:
        return instructions

    if cfg.instructions:
        instructions_dir = _config.get_instructions_dir()
        for inst in cfg.instructions:
            found = False
            for f in sorted(instructions_dir.iterdir()):
                if f.is_file() and f.stem == inst.name:
                    instructions.append(f.name)
                    found = True
                    break
            if not found:
                instructions.append(f"{inst.name}.md")

    if cfg.agents:
        instructions.append(".github/agents/*.agent.md")

    if cfg.skills:
        instructions.append(".github/skills/*/SKILL.md")

    return instructions


def _add_mcp_section(config: dict, cfg: _config.Config) -> None:
    """Add MCP servers to the config dict."""
    if not cfg.mcp_servers:
        return
    config["mcp"] = {s.name: _mcp_server_to_opencode(s) for s in cfg.mcp_servers}


def _add_skills_section(config: dict, cfg: _config.Config) -> None:
    """Add skills paths to the config dict."""
    if cfg.skills:
        config["skills"] = {"paths": [".github/skills"]}


def _add_prompts_section(config: dict, cfg: _config.Config) -> None:
    """Add prompts as opencode commands to the config dict."""
    if not cfg.prompts:
        return

    prompts_dir = _config.get_prompts_dir()
    command_section: dict[str, dict] = {}
    for prompt in cfg.prompts:
        entry = _read_prompt_entry(prompts_dir, prompt)
        if entry is not None:
            command_section[prompt.name] = entry

    if command_section:
        config["command"] = command_section


def _read_prompt_entry(prompts_dir: Path, prompt: object) -> dict[str, str] | None:
    """Read a single prompt file and return an opencode command entry."""
    prompt_file = _find_prompt_file(prompts_dir, prompt.name)
    if prompt_file is None:
        click.echo(
            f"Warning: prompt file '{prompt.name}' not found in {prompts_dir}, skipping.",
            err=True,
        )
        return None

    try:
        content = prompt_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        click.echo(
            f"Warning: failed to read prompt file '{prompt_file.name}': {e}, skipping.",
            err=True,
        )
        return None

    entry: dict[str, str] = {"template": content}
    if prompt.description:
        entry["description"] = prompt.description
    return entry


def _find_prompt_file(prompts_dir: Path, name: str) -> Path | None:
    """Find a prompt file by name, trying multiple extensions."""
    for ext in (".md", ".txt", ".prompt", ""):
        candidate = prompts_dir / f"{name}{ext}"
        if candidate.exists():
            return candidate
    return None


@opencode_group.command(name="uninstall")
def opencode_uninstall() -> None:
    """Remove opencode.json from the current directory."""
    output_path = Path.cwd() / "opencode.json"

    if not output_path.exists():
        click.echo("opencode.json not found.")
        return

    output_path.unlink()
    click.echo(f"opencode.json removed: {output_path}")


# Valid permission keys per opencode.json schema
_VALID_PERMISSION_KEYS = frozenset(
    {
        "read",
        "edit",
        "glob",
        "grep",
        "list",
        "bash",
        "task",
        "external_directory",
        "todowrite",
        "question",
        "webfetch",
        "websearch",
        "lsp",
        "doom_loop",
        "skill",
    }
)


def _validate_opencode_config(config_path: Path) -> list[str]:
    """Validate opencode.json against expected schema.

    Returns a list of error messages (empty = valid).
    """
    data = _load_json_file(config_path)
    if isinstance(data, list) and len(data) == 1:
        return data  # error list from _load_json_file

    errors: list[str] = []
    errors.extend(_validate_instructions(data))
    errors.extend(_validate_permission(data))
    errors.extend(_validate_mcp_section(data))
    errors.extend(_validate_skills_section(data))
    errors.extend(_validate_command_section(data))
    return errors


def _load_json_file(path: Path) -> dict | list[str]:
    """Load and parse a JSON file. Returns dict or single-element error list."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return [f"Invalid JSON: {e}"]
    except OSError as e:
        return [f"Cannot read file: {e}"]

    if not isinstance(data, dict):
        return ["opencode.json must be a JSON object"]
    return data


def _validate_instructions(data: dict) -> list[str]:
    """Validate the instructions section."""
    if "instructions" not in data:
        return []
    val = data["instructions"]
    if not isinstance(val, list):
        return ["'instructions' must be an array"]
    if not all(isinstance(s, str) for s in val):
        return ["'instructions' items must be strings"]
    return []


def _validate_permission(data: dict) -> list[str]:
    """Validate the permission section."""
    if "permission" not in data:
        return []
    perm = data["permission"]
    if not isinstance(perm, dict):
        return ["'permission' must be an object"]

    errors: list[str] = []
    for key in perm:
        if key not in _VALID_PERMISSION_KEYS:
            errors.append(f"Unknown permission key: '{key}'")
    for key, val in perm.items():
        if key in _VALID_PERMISSION_KEYS and val not in ("ask", "allow", "deny"):
            errors.append(f"permission.{key}: invalid value '{val}' (expected ask/allow/deny)")
    return errors


def _validate_mcp_section(data: dict) -> list[str]:
    """Validate the mcp section."""
    if "mcp" not in data:
        return []
    mcp = data["mcp"]
    if not isinstance(mcp, dict):
        return ["'mcp' must be an object"]

    errors: list[str] = []
    for name, server in mcp.items():
        errors.extend(_validate_mcp_server(name, server))
    return errors


def _validate_skills_section(data: dict) -> list[str]:
    """Validate the skills section."""
    if "skills" not in data:
        return []
    skills = data["skills"]
    if not isinstance(skills, dict):
        return ["'skills' must be an object"]
    if "paths" not in skills:
        return []
    if not isinstance(skills["paths"], list):
        return ["'skills.paths' must be an array"]
    if not all(isinstance(p, str) for p in skills["paths"]):
        return ["'skills.paths' items must be strings"]
    return []


def _validate_command_section(data: dict) -> list[str]:
    """Validate the command section."""
    if "command" not in data:
        return []
    cmd_section = data["command"]
    if not isinstance(cmd_section, dict):
        return ["'command' must be an object"]

    errors: list[str] = []
    for name, cmd in cmd_section.items():
        errors.extend(_validate_command_entry(name, cmd))
    return errors


def _validate_mcp_server(name: str, server: object) -> list[str]:
    """Validate a single MCP server entry."""
    prefix = f"mcp.{name}"
    if not isinstance(server, dict):
        return [f"{prefix} must be an object"]

    errors: list[str] = []

    if "type" not in server:
        errors.append(f"{prefix}: missing 'type'")
    elif server["type"] not in ("local", "remote"):
        errors.append(f"{prefix}: invalid type '{server['type']}' (expected local/remote)")

    if "command" not in server:
        errors.append(f"{prefix}: missing 'command'")
    elif not isinstance(server["command"], list):
        errors.append(f"{prefix}: 'command' must be an array")
    elif not all(isinstance(c, str) for c in server["command"]):
        errors.append(f"{prefix}: 'command' items must be strings")

    if "enabled" in server and not isinstance(server["enabled"], bool):
        errors.append(f"{prefix}: 'enabled' must be a boolean")

    if "environment" in server:
        if not isinstance(server["environment"], dict):
            errors.append(f"{prefix}: 'environment' must be an object")
        elif not all(isinstance(v, str) for v in server["environment"].values()):
            errors.append(f"{prefix}: 'environment' values must be strings")

    return errors


def _validate_command_entry(name: str, cmd: object) -> list[str]:
    """Validate a single command entry."""
    prefix = f"command.{name}"
    if not isinstance(cmd, dict):
        return [f"{prefix} must be an object"]

    if "template" not in cmd:
        return [f"{prefix}: missing required 'template'"]
    if not isinstance(cmd["template"], str):
        return [f"{prefix}: 'template' must be a string"]

    return []


@opencode_group.command(name="validate")
@click.option(
    "--fix",
    is_flag=True,
    help="Automatically fix agent file format issues.",
)
@click.option(
    "--quiet",
    is_flag=True,
    help="Minimal output; only exit code indicates result (0 = valid).",
)
@click.option(
    "--project-dir",
    "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="Target project directory (default: current directory)",
)
@click.option(
    "--config-only",
    is_flag=True,
    help="Validate only opencode.json (skip agent file validation).",
)
def opencode_validate(fix: bool, quiet: bool, project_dir: str | None, config_only: bool) -> None:
    """Validate opencode.json and agent file formats.

    By default, validates both:
    - ``opencode.json`` schema (instructions, permission, mcp, skills, command)
    - ``.github/agents/*.agent.md`` tools format (object vs array)

    Exit code: 0 if all valid, 1 if any issues found.
    """
    base_dir = Path(project_dir).resolve() if project_dir else Path.cwd()
    all_errors: list[str] = []

    # Validate opencode.json
    config_path = base_dir / "opencode.json"
    if config_path.exists():
        config_errors = _validate_opencode_config(config_path)
        all_errors.extend(config_errors)
    else:
        if not quiet:
            click.echo("opencode.json not found.")
        all_errors.append("opencode.json not found")

    # Validate agent files (unless --config-only)
    if not config_only:
        agents_dir = base_dir / ".github" / "agents"
        if agents_dir.exists():
            agent_errors = batch_validate_and_fix(agents_dir, fix=fix)
            all_errors.extend(agent_errors)

    if all_errors:
        if not quiet:
            for err in all_errors:
                click.echo(err, err=True)
            if fix:
                click.echo(f"Fixed {len(all_errors)} issue(s).")
            else:
                click.echo(
                    "Run with --fix to automatically correct format.",
                    err=True,
                )
        raise SystemExit(1)

    if not quiet:
        click.echo("All validations passed.")
