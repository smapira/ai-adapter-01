"""Gemini CLI provider integration.

Handles:
- Custom command export (``.gemini/commands/**/*.toml``)
- MCP export (``settings.json`` ``mcpServers`` section)
- Context file deployment (``GEMINI.md``)
- Extension manifest generation (``gemini-extension.json``)
- Configuration validation

Gemini CLI reads custom commands as TOML files (``description`` +
``prompt``), MCP servers from ``.gemini/settings.json`` (project) or
``~/.gemini/settings.json`` (user), and project/user context from
``GEMINI.md``.  Extensions are installed under
``~/.gemini/extensions/<name>/`` — the CLI does not read manifests from
the project root, so :func:`generate_extension_manifest` output must be
registered via ``gemini extensions install`` (design 05 task 05-3).
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import click

from ai_adapter import config as _config
from ai_adapter.agent_format import parse_frontmatter_text
from ai_adapter.config import add_to_gitignore, resolve_scope_path
from ai_adapter.models import Config, MCPServer

# tomllib is stdlib from Python 3.11; 3.10 falls back to the API-compatible
# tomli package (a regular dependency with a python_full_version < '3.11'
# marker — same pattern as the Codex provider).
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]


# ── Path resolution ─────────────────────────────────────────────────────


def resolve_commands_path(scope: str, project_dir: Path | None = None) -> Path:
    """Return the Gemini CLI commands directory for *scope*.

    Args:
        scope: "project" → ``.gemini/commands/``, "user" → ``~/.gemini/commands/``.
        project_dir: Project directory for project scope (defaults to cwd).

    Delegates to :func:`resolve_scope_path` so every tool shares one
    scope-resolution policy (design 05 constraint: no bespoke resolution).
    """
    return resolve_scope_path("gemini", "commands", scope, project_dir).path


def resolve_settings_path(scope: str, project_dir: Path | None = None) -> Path:
    """Return the settings.json path for *scope* (``.gemini/settings.json``)."""
    base = resolve_scope_path("gemini", "mcp", scope, project_dir).path
    return base / "settings.json"


def resolve_context_path(scope: str, project_dir: Path | None = None, filename: str = "GEMINI.md") -> Path:
    """Return the GEMINI.md path for *scope* (project root or ``~/.gemini/``)."""
    base = resolve_scope_path("gemini", "instruction", scope, project_dir).path
    return base / filename


# ── Markdown → TOML conversion ──────────────────────────────────────────


def _strip_frontmatter(content: str) -> str:
    """Return *content* without its leading YAML frontmatter block."""
    match = re.match(r"^---\s*\n.*?\n---\s*\n?", content, re.DOTALL)
    return content[match.end() :] if match else content


def parse_command_markdown(content: str) -> tuple[str, str]:
    """Split command Markdown into ``(description, body)``.

    The YAML frontmatter ``description`` becomes the Gemini TOML
    ``description``; the remaining body becomes the ``prompt``.  Content
    without usable frontmatter keeps the whole text as the body with an
    empty description (design 05 task 05-4).
    """
    frontmatter = parse_frontmatter_text(content)
    description = str(frontmatter.get("description") or "")
    return description, _strip_frontmatter(content)


def _escape_toml_basic(value: str) -> str:
    """Escape *value* for a TOML basic (single-line) string body."""
    escaped = value.replace("\\", "\\\\")
    escaped = escaped.replace('"', '\\"')
    return escaped.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")


def _escape_toml_multiline(value: str) -> str:
    """Escape *value* for a TOML multi-line basic string (``\"\"\"``).

    Backslashes are doubled first so later escapes stay literal; ``\"\"\"``
    becomes ``\"\"\\\"`` (design 05 Plan Architect M5-3) so the content can
    never terminate the multi-line literal early.  A trailing backslash is
    covered by the same doubling — it would otherwise escape the closing
    delimiter.
    """
    escaped = value.replace("\\", "\\\\")
    return escaped.replace('"""', '""\\"')


def export_command_toml(command_name: str, content: str, description: str = "") -> str:
    """Convert a command/prompt Markdown body to Gemini CLI TOML.

    Args:
        command_name: Command name — carried by the output filename; kept
            in the signature per the design 05 provider API.
        content: Markdown source (frontmatter + body, or body only).
        description: Pre-resolved description; when empty it is parsed
            from *content*'s frontmatter.

    Returns:
        TOML text with ``description`` and a triple-quoted ``prompt``.
    """
    if description:
        body = _strip_frontmatter(content)
    else:
        description, body = parse_command_markdown(content)
    prompt = _escape_toml_multiline(body)
    if not prompt.endswith("\n"):
        prompt += "\n"
    description_line = f'description = "{_escape_toml_basic(description)}"'
    return f'{description_line}\n\nprompt = """\n{prompt}"""\n'


# ── MCP export / merge ──────────────────────────────────────────────────


def export_mcp(servers: list[MCPServer]) -> dict:
    """Export MCP servers for Gemini settings.json ``mcpServers``.

    Env values use Gemini's ``${ENV_KEY}`` expansion syntax (design 05
    task 05-1 AC2).  Disabled servers are filtered out; entries without a
    command (http/sse-style) are skipped with a warning, mirroring the
    VS Code provider behaviour.
    """
    exported: dict[str, dict] = {}
    for server in servers:
        if not server.enabled:
            continue
        if not server.command:
            click.echo(
                f"Warning: skipping non-stdio MCP server '{server.name}' (only command-based servers are exported).",
                err=True,
            )
            continue
        entry: dict[str, object] = {"command": server.command}
        if server.args:
            entry["args"] = list(server.args)
        if server.env_keys:
            entry["env"] = {key: f"${{{key}}}" for key in server.env_keys}
        exported[server.name] = entry
    return {"mcpServers": exported}


def merge_into_settings(path: Path, data: dict, force: bool = False) -> None:
    """Merge *data* (``mcpServers``) into the Gemini settings.json at *path*.

    Only the ``mcpServers`` section is managed — every other top-level key
    (model, theme, tools, …) is preserved.  Unmanaged server names are
    preserved too (new names overwrite, unknown names survive).  A ``.bak``
    backup is taken before modifying an existing file.
    """
    existing: dict = {}
    if path.exists():
        if not force:
            click.confirm(f"Overwrite MCP servers in '{path}'?", abort=True)
        bak_path = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, bak_path)
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            loaded = {}
        # Guard against non-object top level: a structurally odd file must
        # not crash the merge with AttributeError (same review note M1 as
        # the VS Code provider).
        existing = loaded if isinstance(loaded, dict) else {}

    new_servers = dict(data.get("mcpServers", {}))
    existing_servers = existing.get("mcpServers", {})
    if not isinstance(existing_servers, dict):
        existing_servers = {}

    managed_names = set(new_servers)
    for name, entry in existing_servers.items():
        if name not in managed_names:
            new_servers[name] = entry

    existing["mcpServers"] = new_servers
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ── Context deployment ──────────────────────────────────────────────────


def deploy_context(
    content: str,
    scope: str,
    project_dir: Path | None = None,
    filename: str = "GEMINI.md",
    force: bool = False,
) -> Path:
    """Deploy *content* as the GEMINI.md context file for *scope*.

    Uses :func:`resolve_scope_path` for the destination directory and
    honours its gitignore flag (project scope only).
    """
    target = resolve_scope_path("gemini", "instruction", scope, project_dir)
    dest = target.path / filename
    if dest.exists() and not force:
        click.confirm(f"'{dest}' already exists. Overwrite?", abort=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    if target.use_gitignore:
        add_to_gitignore(dest)
    return dest


# ── Extension manifest ──────────────────────────────────────────────────


def generate_extension_manifest(
    name: str,
    description: str = "",
    mcp_servers: list[MCPServer] | None = None,
    context_file: str | None = None,
) -> dict:
    """Generate a ``gemini-extension.json`` manifest dict.

    The manifest is installed under ``~/.gemini/extensions/<name>/`` —
    Gemini CLI does not read manifests from the project root (design 05
    task 05-3, Plan Architect C5-1).  MCP server entries are exported
    as-is: ``${extensionPath}`` placeholders are allowed by the official
    spec and ai-adapter never forces path resolution on them.
    """
    manifest: dict[str, object] = {
        "name": name,
        "version": "1.0.0",
        "description": description or "Gemini CLI extension managed by ai-adapter",
    }
    if mcp_servers:
        manifest["mcpServers"] = export_mcp(mcp_servers).get("mcpServers", {})
    if context_file:
        manifest["contextFileName"] = context_file
    return manifest


# ── Validation helpers ──────────────────────────────────────────────────


def validate_settings(path: Path) -> list[str]:
    """Validate a Gemini ``settings.json`` structure.

    Checks: valid JSON, top-level object, and ``mcpServers`` (when
    present) is an object whose entries are objects.  Returns error
    messages (empty when valid).
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [f"{path.name}: not valid JSON: {exc}"]
    if not isinstance(data, dict):
        return [f"{path.name}: must be a JSON object"]
    errors: list[str] = []
    servers = data.get("mcpServers")
    if servers is None:
        return errors
    if not isinstance(servers, dict):
        errors.append(f"{path.name}: 'mcpServers' must be an object")
        return errors
    for name, entry in servers.items():
        if not isinstance(entry, dict):
            errors.append(f"{path.name}: mcpServers.{name} must be an object")
    return errors


def validate_extension_manifest(path: Path) -> list[str]:
    """Validate a ``gemini-extension.json`` manifest structure.

    Checks: valid JSON object, required string ``name``, and ``mcpServers``
    (when present) is an object of objects.  Returns error messages.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [f"{path.name}: not valid JSON: {exc}"]
    if not isinstance(data, dict):
        return [f"{path.name}: must be a JSON object"]
    errors: list[str] = []
    if not isinstance(data.get("name"), str) or not data.get("name"):
        errors.append(f"{path.name}: missing required 'name' field")
    servers = data.get("mcpServers")
    if servers is not None:
        if not isinstance(servers, dict):
            errors.append(f"{path.name}: 'mcpServers' must be an object")
        else:
            for name, entry in servers.items():
                if not isinstance(entry, dict):
                    errors.append(f"{path.name}: mcpServers.{name} must be an object")
    return errors


def validate_command_toml(path: Path) -> list[str]:
    """Validate a ``.gemini/commands/**/*.toml`` file.

    Checks: TOML parses, and ``prompt`` / ``description`` (when present)
    are strings.  Returns error messages (empty when valid).
    """
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        return [f"{path.name}: not valid TOML: {exc}"]
    except OSError as exc:
        return [f"{path.name}: {exc}"]
    errors: list[str] = []
    for key in ("prompt", "description"):
        if key in data and not isinstance(data[key], str):
            errors.append(f"{path.name}: '{key}' must be a string")
    return errors


# ── Store lookup helpers ────────────────────────────────────────────────


def find_store_file(directory: Path, name: str) -> Path | None:
    """Find a registered store file by name, supporting nested names.

    Handles flat names (``deploy`` → ``deploy.md`` / ``deploy.sh``) and
    nested names (``dir/name`` → ``dir/name.md``) — Gemini supports nested
    custom commands via ``.gemini/commands/<dir>/<name>.toml``.
    """
    if not directory.is_dir():
        return None
    exact = directory / name
    if exact.is_file():
        return exact
    relative = Path(name)
    parent = directory / relative.parent
    if not parent.is_dir():
        return None
    for candidate in sorted(parent.iterdir()):
        if candidate.is_file() and candidate.stem == relative.name:
            return candidate
    return None


def _build_context_content(config: Config) -> str:
    """Concatenate registered instruction files into one GEMINI.md body.

    Each instruction gets a ``# <name>`` heading so merged sections stay
    attributable.  Full file content is read from the store — the config
    entry only keeps a 200-character preview.
    """
    instructions_dir = _config.get_instructions_dir()
    sections: list[str] = []
    for inst in config.instructions:
        src = find_store_file(instructions_dir, inst.name)
        body = (src.read_text(encoding="utf-8") if src else inst.content).strip()
        if body:
            sections.append(f"# {inst.name}\n\n{body}")
    if not sections:
        return ""
    return "\n\n".join(sections) + "\n"


# ── CLI group ───────────────────────────────────────────────────────────


@click.group(name="gemini")
def gemini_group() -> None:
    """Manage Gemini CLI configuration (.gemini/)."""


@gemini_group.command(name="install")
@click.option(
    "--scope",
    type=click.Choice(["project", "user"]),
    default="project",
    help="Deploy scope: project=.gemini/ + GEMINI.md, user=~/.gemini/",
)
@click.option(
    "--project-dir",
    "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="Target project directory (default: current directory)",
)
@click.option(
    "--with-extension",
    is_flag=True,
    help=(
        "Also generate ~/.gemini/extensions/<name>/gemini-extension.json "
        "(registered later via `gemini extensions install`)"
    ),
)
@click.option("--force", is_flag=True, help="Overwrite existing settings.json without prompting")
def gemini_install(scope: str, project_dir: str | None, with_extension: bool, force: bool) -> None:
    """Install Gemini CLI configuration from the ai-adapter store.

    Generates ``settings.json`` (MCP), ``commands/*.toml`` (commands and
    prompts as Gemini TOML), and ``GEMINI.md`` (instructions as context).
    With ``--scope user`` everything lands under ``~/.gemini/``.
    """
    config = _config.load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    project_path = Path(project_dir).resolve() if project_dir else None
    installed = _install_all(config, scope, project_path, force)
    if not installed:
        click.echo("Nothing to install.")
        return

    click.echo("Gemini CLI configuration installed:")
    for path in installed:
        click.echo(f"  {path}")

    if with_extension:
        _install_extension(config, project_path, force)


def _install_all(config: Config, scope: str, project_path: Path | None, force: bool) -> list[str]:
    """Install every store artifact for *scope*; returns the written paths."""
    installed: list[str] = []
    installed.extend(_install_command_tomls(config, scope, project_path))
    installed.extend(_install_settings(config, scope, project_path, force))
    installed.extend(_install_context(config, scope, project_path, force))
    return installed


def _install_command_tomls(config: Config, scope: str, project_path: Path | None) -> list[str]:
    """Convert registered commands and prompts into ``commands/*.toml``.

    TOML files are ai-adapter-generated artifacts, so they are overwritten
    silently — prompting per file would make batch installs unusable.
    """
    target = resolve_scope_path("gemini", "commands", scope, project_path)
    store_entries = [(c.name, _config.get_commands_dir(), c.content) for c in config.commands]
    store_entries += [(p.name, _config.get_prompts_dir(), p.content) for p in config.prompts]

    installed: list[str] = []
    for name, store_dir, fallback_content in store_entries:
        src = find_store_file(store_dir, name)
        content = src.read_text(encoding="utf-8") if src else fallback_content
        if not content.strip():
            continue
        dest = target.path / f"{name}.toml"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(export_command_toml(name, content), encoding="utf-8")
        if target.use_gitignore:
            add_to_gitignore(dest)
        installed.append(str(dest))
    return installed


def _install_settings(config: Config, scope: str, project_path: Path | None, force: bool) -> list[str]:
    """Merge registered MCP servers into settings.json for *scope*."""
    enabled = [s for s in config.mcp_servers if s.enabled]
    if not enabled:
        return []
    settings_path = resolve_settings_path(scope, project_path)
    merge_into_settings(settings_path, export_mcp(enabled), force=force)
    if resolve_scope_path("gemini", "mcp", scope, project_path).use_gitignore:
        add_to_gitignore(settings_path)
    return [str(settings_path)]


def _install_context(config: Config, scope: str, project_path: Path | None, force: bool) -> list[str]:
    """Deploy concatenated instruction content as GEMINI.md for *scope*."""
    content = _build_context_content(config)
    if not content:
        return []
    dest = deploy_context(content, scope, project_path, force=force)
    return [str(dest)]


def _install_extension(config: Config, project_path: Path | None, force: bool) -> None:
    """Generate ``~/.gemini/extensions/<name>/gemini-extension.json`` (task 05-3).

    The manifest is deliberately NOT written to the project root — Gemini
    CLI only reads extension manifests from ``~/.gemini/extensions/`` and
    registering one requires ``gemini extensions install`` (Plan C5-1).
    """
    project_name = (project_path or Path.cwd()).resolve().name
    extensions_dir = Path.home() / ".gemini" / "extensions" / project_name
    if extensions_dir.exists() and not force:
        click.confirm(f"'{extensions_dir}' already exists. Overwrite manifest?", abort=True)

    enabled = [s for s in config.mcp_servers if s.enabled]
    manifest = generate_extension_manifest(
        name=project_name,
        mcp_servers=enabled or None,
        context_file="GEMINI.md",
    )
    extensions_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = extensions_dir / "gemini-extension.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Bundle the context file inside the extension so contextFileName resolves.
    context_content = _build_context_content(config)
    if context_content:
        (extensions_dir / "GEMINI.md").write_text(context_content, encoding="utf-8")

    click.echo("Gemini extension manifest generated:")
    click.echo(f"  {manifest_path}")
    click.echo(f"Install with: gemini extensions install {extensions_dir}")


@gemini_group.command(name="validate")
@click.option("--json", "as_json", is_flag=True, help="Output the report as JSON")
@click.option(
    "--project-dir",
    "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="Target project directory (default: current directory)",
)
def gemini_validate(as_json: bool, project_dir: str | None) -> None:
    """Validate Gemini CLI configuration files.

    Checks project/user ``settings.json`` (JSON + mcpServers shape),
    ``.gemini/commands/**/*.toml`` (TOML parse), and installed
    ``gemini-extension.json`` manifests.  Exit code: 0 valid, 1 errors.
    """
    base_dir = Path(project_dir).resolve() if project_dir else Path.cwd()
    errors, checked = _run_validations(base_dir)

    if as_json:
        click.echo(json.dumps({"valid": not errors, "errors": errors, "checked": checked}, indent=2))
    elif errors:
        for err in errors:
            click.echo(err, err=True)
    else:
        click.echo("Gemini CLI configuration is valid.")

    if errors:
        raise SystemExit(1)


def _run_validations(base_dir: Path) -> tuple[list[str], list[str]]:
    """Validate every Gemini config surface; returns ``(errors, checked)``."""
    errors: list[str] = []
    checked: list[str] = []

    def _check_file(path: Path, validator) -> None:
        if not path.is_file():
            return
        checked.append(str(path))
        errors.extend(validator(path))

    def _check_tree(root: Path, pattern: str, validator) -> None:
        if not root.is_dir():
            return
        for path in sorted(root.rglob(pattern)):
            checked.append(str(path))
            errors.extend(validator(path))

    _check_file(base_dir / ".gemini" / "settings.json", validate_settings)
    _check_tree(base_dir / ".gemini" / "commands", "*.toml", validate_command_toml)
    _check_file(Path.home() / ".gemini" / "settings.json", validate_settings)
    _check_tree(Path.home() / ".gemini" / "commands", "*.toml", validate_command_toml)
    _check_tree(Path.home() / ".gemini" / "extensions", "gemini-extension.json", validate_extension_manifest)
    return errors, checked
