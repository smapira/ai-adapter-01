"""Codex CLI provider integration.

Generates AGENTS.md files for OpenAI Codex CLI from ai-adapter's
registered agents, skills, and instructions.

Codex CLI reads AGENTS.md as plain Markdown (no YAML frontmatter).
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import click

from ai_adapter import config as _config
from ai_adapter.agent_format import parse_frontmatter
from ai_adapter.config import add_to_gitignore, resolve_scope_path
from ai_adapter.models import MCPServer, Skill

# tomllib is stdlib from Python 3.11; 3.10 falls back to the API-compatible
# tomli package (a regular dependency with a python_full_version < '3.11'
# marker — no extra install step needed).
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]


def _extract_agents_section(agents_dir: Path) -> list[str]:
    """Extract agent content from .agent.md files (without frontmatter)."""
    sections: list[str] = []
    if not agents_dir.exists():
        return sections

    for f in sorted(agents_dir.iterdir()):
        if not f.is_file():
            continue
        if not (str(f).endswith(".agent.md") or str(f).endswith(".md")):
            continue
        content = f.read_text(encoding="utf-8")
        fm = parse_frontmatter(f)
        name = fm.get("name", "").strip() or f.stem

        # Strip YAML frontmatter block
        stripped = re.sub(r"^---\s*\n.*?\n---\s*\n?", "", content, flags=re.DOTALL).strip()
        if stripped:
            sections.append(stripped)
        else:
            sections.append(f"## {name}")

    return sections


def _extract_instructions_section(instructions_dir: Path) -> list[str]:
    """Extract content from root-level instruction files."""
    sections: list[str] = []
    if not instructions_dir.exists():
        return sections

    for f in sorted(instructions_dir.iterdir()):
        if not f.is_file():
            continue
        if not f.suffix == ".md":
            continue
        content = f.read_text(encoding="utf-8").strip()
        if content:
            sections.append(content)

    return sections


def _extract_skills_section(skills_dir: Path) -> list[str]:
    """Extract skill content from SKILL.md files."""
    sections: list[str] = []
    if not skills_dir.exists():
        return sections

    for d in sorted(skills_dir.iterdir()):
        if not d.is_dir():
            continue
        skill_file = d / "SKILL.md"
        if not skill_file.exists():
            continue
        content = skill_file.read_text(encoding="utf-8").strip()
        if content:
            sections.append(content)

    return sections


def generate_agents_md() -> str:
    """Generate AGENTS.md content from ai-adapter store.

    Combines agents, instructions, and skills into a single
    plain Markdown file suitable for Codex CLI.
    """
    agents_dir = _config.get_agents_dir()
    instructions_dir = _config.get_instructions_dir()
    skills_dir = _config.get_skills_dir()

    sections: list[str] = []

    agents = _extract_agents_section(agents_dir)
    if agents:
        sections.extend(agents)

    instructions = _extract_instructions_section(instructions_dir)
    if instructions:
        sections.extend(instructions)

    skills = _extract_skills_section(skills_dir)
    if skills:
        sections.extend(skills)

    return "\n\n---\n\n".join(sections) + "\n" if sections else ""


# ── Scope path resolution (design 03) ───────────────────────────────────
# All destinations come from resolve_scope_path() (design 01) — this module
# never re-implements path mapping.


def resolve_config_toml_path(scope: str, project_dir: Path | None = None) -> Path:
    """Return the Codex ``config.toml`` path for *scope*.

    Args:
        scope: "project" → ``<project>/.codex/config.toml``,
            "user" → ``~/.codex/config.toml``.
        project_dir: Project directory for project scope (defaults to cwd).
    """
    return resolve_scope_path("codex", "mcp", scope, project_dir).path / "config.toml"


def resolve_skills_path(scope: str, project_dir: Path | None = None) -> Path:
    """Return the Codex skills directory for *scope*.

    The spec path is ``.agents/skills/`` (design 03): project scope uses
    the project's copy, user scope ``~/.agents/skills/``.
    """
    return resolve_scope_path("codex", "skills", scope, project_dir).path


def resolve_compat_skills_path(scope: str, project_dir: Path | None = None) -> Path:
    """Return the opt-in compat mirror ``.codex/skills/`` for *scope*."""
    return resolve_scope_path("codex", "skills_compat", scope, project_dir).path


# ── TOML helpers (design 03 Phase A) ────────────────────────────────────
# config.toml is text-spliced, never round-tripped through a TOML writer:
# tomli-w would destroy hand-written comments and key order that Codex
# users maintain (model, approval_policy, …).


# Matches any TOML table header: [name], [a.b], [[array-of-tables]], …
_TOML_TABLE_HEADER_RE = re.compile(r"^\s*\[(\[.*?\]|[^\]]+)\]\s*(?:#.*)?$")


def _toml_string(value: str) -> str:
    """Render a TOML basic string.

    JSON string escaping is a compatible subset of TOML's basic-string
    escapes, so :func:`json.dumps` is safe without a TOML writer.
    """
    return json.dumps(value, ensure_ascii=False)


def _toml_key(name: str) -> str:
    """Render a TOML key, quoting only when the bare form is invalid."""
    if re.fullmatch(r"[A-Za-z0-9_-]+", name):
        return name
    return _toml_string(name)


def _parse_table_header_key(raw: str) -> str:
    """Normalize a table header key, stripping quotes from each segment."""
    segments: list[str] = []
    for segment in raw.split("."):
        segment = segment.strip()
        if len(segment) >= 2 and segment[0] == segment[-1] and segment[0] in "\"'":
            segment = segment[1:-1]
        segments.append(segment)
    return ".".join(segments)


def _table_ranges(lines: list[str]) -> dict[str, tuple[int, int]]:
    """Map each table key to its ``(start, end)`` line range (end exclusive)."""
    ranges: dict[str, tuple[int, int]] = {}
    current: str | None = None
    start = 0
    for i, line in enumerate(lines):
        match = _TOML_TABLE_HEADER_RE.match(line)
        if match is None:
            continue
        if current is not None:
            ranges[current] = (start, i)
        raw_key = match.group(1)
        if raw_key.startswith("["):  # [[array-of-tables]] — strip outer brackets
            raw_key = raw_key.strip("[")
        current = _parse_table_header_key(raw_key)
        start = i
    if current is not None:
        ranges[current] = (start, len(lines))
    return ranges


def _mcp_section_ranges(lines: list[str]) -> dict[str, tuple[int, int]]:
    """Return ranges of tables owned by the ``mcp_servers`` namespace."""
    return {
        key: span
        for key, span in _table_ranges(lines).items()
        if key == "mcp_servers" or key.startswith("mcp_servers.")
    }


def _render_server_table(name: str, entry: dict) -> str:
    """Render one ``[mcp_servers.<name>]`` block as TOML text."""
    lines = [f"[mcp_servers.{_toml_key(name)}]", f"command = {_toml_string(str(entry.get('command', '')))}"]
    args = entry.get("args") or []
    if args:
        lines.append(f"args = [{', '.join(_toml_string(str(a)) for a in args)}]")
    env = entry.get("env") or {}
    if env:
        pairs = ", ".join(f"{_toml_string(str(k))} = {_toml_string(str(v))}" for k, v in env.items())
        lines.append(f"env = {{ {pairs} }}")
    return "\n".join(lines) + "\n"


def _has_non_table_mcp_servers(lines: list[str]) -> bool:
    """Detect TOML forms the text-splice cannot safely handle.

    Returns ``True`` when ``mcp_servers`` is defined as an inline table
    (``mcp_servers = { … }``), a dotted key (``mcp_servers.foo = …``), or
    a ``[mcp_servers]`` table with direct key/value pairs.  Splicing
    ``[mcp_servers.<name>]`` tables onto those forms would produce
    duplicate-key TOML that fails to parse, so callers must refuse to
    merge (review C2).
    """
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Inline table: mcp_servers = { … }
        if re.match(r"^mcp_servers\s*=", stripped):
            return True
        # Dotted key: mcp_servers.foo = …
        if re.match(r"^mcp_servers\.", stripped):
            return True
        # [mcp_servers] header followed by direct keys is handled by
        # _splice_mcp_servers (keys are preserved), so only inline/dotted
        # forms are unsafe.
    return False


def _splice_mcp_servers(text: str, servers: dict) -> str:
    """Return *text* with managed ``[mcp_servers.*]`` tables upserted.

    Text-splice on purpose: a parse → serialize round trip would destroy
    comments and key order.  Managed server names are replaced in place
    (or appended after the last mcp_servers table / at end of file when
    absent); unmanaged tables and every other section pass through
    verbatim.

    Comments *inside* a managed ``[mcp_servers.<name>]`` table are
    replaced along with the table content — ai-adapter owns those
    entries.  Comments in unmanaged tables and all other sections are
    preserved (design 03 §2.2 / review C3 clarification).

    Raises:
        ValueError: When the existing text uses inline-table or dotted-key
            forms for ``mcp_servers`` that text-splice cannot handle
            safely (review C2).
    """
    lines = text.splitlines(keepends=True)
    if _has_non_table_mcp_servers(lines):
        raise ValueError(
            "config.toml defines mcp_servers as an inline table or dotted key; "
            "text-splice merge cannot handle that form safely. "
            "Convert to [mcp_servers.<name>] table form, or remove the entry, "
            "then retry."
        )
    ordered = sorted(_mcp_section_ranges(lines).items(), key=lambda kv: kv[1][0])

    out: list[str] = []
    cursor = 0
    insert_at: int | None = None
    replaced: set[str] = set()
    prefix = "mcp_servers."
    for key, (start, end) in ordered:
        out.extend(lines[cursor:start])
        name = key[len(prefix) :] if key.startswith(prefix) else None
        if name and name in servers:
            out.append(_render_server_table(name, servers[name]))
            replaced.add(name)
        else:
            out.extend(lines[start:end])
        insert_at = len(out)
        cursor = end
    out.extend(lines[cursor:])

    pending = [n for n in sorted(servers) if n not in replaced]
    if not pending:
        return "".join(out)

    if insert_at is None:
        insert_at = len(out)
    block = "".join(_render_server_table(n, servers[n]) for n in pending)
    if insert_at > 0 and out[insert_at - 1].strip():
        block = "\n" + block
    out.insert(insert_at, block)
    return "".join(out)


def export_mcp_toml(servers: list[MCPServer]) -> dict:
    """Export MCP servers as a Codex ``config.toml`` ``mcp_servers`` payload.

    Disabled servers are filtered out; ``env_keys`` become ``"${KEY}"``
    strings resolved by Codex at load time.

    Args:
        servers: MCP server configurations from ai-adapter.

    Returns:
        ``{"mcp_servers": {name: {command, args, env}}}`` — the payload
        merged by :func:`merge_into_config_toml`.
    """
    servers_dict: dict[str, dict] = {}
    for s in servers:
        if not s.enabled:
            continue
        entry: dict[str, object] = {"command": s.command}
        if s.args:
            entry["args"] = list(s.args)
        if s.env_keys:
            entry["env"] = {k: f"${{{k}}}" for k in s.env_keys}
        servers_dict[s.name] = entry
    return {"mcp_servers": servers_dict}


def merge_into_config_toml(path: Path, mcp_data: dict, force: bool = False) -> None:
    """Merge ``mcp_servers`` into a Codex ``config.toml`` (comment-preserving).

    Only the ``[mcp_servers.*]`` tables are rewritten — every other section
    (``model``, ``approval_policy``, …) and all comments are preserved via
    text splice.  Managed server names are upserted, unmanaged servers are
    kept.  A ``.bak`` backup is taken before modifying an existing file;
    a missing file starts from empty text.  ``~/.codex/auth.json`` (the
    credential store) is never read or written.

    Args:
        path: Path to the target ``config.toml``.
        mcp_data: Dict from :func:`export_mcp_toml`.
        force: Skip the confirmation prompt if True.
    """
    servers: dict = dict(mcp_data.get("mcp_servers") or {})
    existing_text = ""
    if path.exists():
        if not force:
            click.confirm(f"Overwrite MCP servers in '{path}'?", abort=True)
        bak_path = path.parent / (path.name + ".bak")
        shutil.copy2(path, bak_path)
        existing_text = path.read_text(encoding="utf-8")

    try:
        new_text = _splice_mcp_servers(existing_text, servers)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    # Validate the spliced result before writing (review M4): a bad splice
    # must never leave the user with an unparsable config.toml.
    try:
        tomllib.loads(new_text)
    except tomllib.TOMLDecodeError as exc:
        raise click.ClickException(
            f"Merge produced invalid TOML for '{path}': {exc}. "
            "The original file was not modified (a .bak backup exists if one was taken)."
        ) from exc

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new_text, encoding="utf-8")
    click.echo(f"Codex MCP configuration written: {path} ({len(servers)} servers)")


def validate_config_toml_mcp(path: Path) -> list[str]:
    """Return validation messages for the ``[mcp_servers]`` table (read-only).

    An empty list means *path* is valid TOML (or absent) and every
    ``mcp_servers`` entry is a table with a ``command`` key.  Messages are
    human-readable one-liners without a path prefix; the caller attaches
    path/label context.
    """
    if not path.is_file():
        return []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        return [f"is not valid TOML: {exc}"]
    except OSError as exc:
        return [f"could not be read: {exc}"]
    if not isinstance(data, dict):
        return []
    servers = data.get("mcp_servers")
    if servers is None:
        return []
    if not isinstance(servers, dict):
        return ["mcp_servers must be a table"]
    messages: list[str] = []
    for name, entry in servers.items():
        if not isinstance(entry, dict) or "command" not in entry:
            messages.append(f"mcp_servers.{name} must be a table with a 'command' key")
    return messages


# ── Skills (design 03 Phase B) ──────────────────────────────────────────


def _copy_skill_tree(src: Path, dest: Path, force: bool) -> None:
    """Copy one skill directory, confirming overwrites unless *force*."""
    if dest.exists():
        if force:
            shutil.rmtree(dest)
        else:
            click.confirm(f"'{dest}' already exists. Overwrite?", abort=True)
            shutil.rmtree(dest)
    shutil.copytree(src, dest)


def deploy_skills(
    skills: list[Skill],
    src_dir: Path,
    scope: str,
    project_dir: Path | None = None,
    force: bool = False,
    also_codex_dir: bool = False,
) -> None:
    """Copy skill directories to the Codex spec path ``.agents/skills/``.

    The canonical destination (design 03) is ``.agents/skills/`` in the
    project or ``~/.agents/skills/`` for user scope.  *also_codex_dir*
    additionally mirrors each skill into the Codex-native
    ``.codex/skills/`` directory — an explicit opt-in so the two copies
    never drift silently.  Project-scope destinations are added to
    ``.gitignore``; user scope never is.

    Args:
        skills: Registered skill entries from the config.
        src_dir: The ai-adapter skills store (``~/.ai-adapter/skills/``).
        scope: "project" or "user".
        project_dir: Project directory for project scope.
        force: Overwrite existing skill directories without prompting.
        also_codex_dir: Also copy to the ``.codex/skills/`` compat path.
    """
    target = resolve_scope_path("codex", "skills", scope, project_dir)
    dest_dir = target.path
    dest_dir.mkdir(parents=True, exist_ok=True)
    compat_dir: Path | None = None
    if also_codex_dir:
        compat_dir = resolve_compat_skills_path(scope, project_dir)
        compat_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for skill_entry in skills:
        src = src_dir / skill_entry.name
        if not src.exists():
            click.echo(f"   Skip: '{skill_entry.name}' directory not found.")
            continue
        dest = dest_dir / skill_entry.name
        _copy_skill_tree(src, dest, force)
        if target.use_gitignore:
            add_to_gitignore(dest)
        if compat_dir is not None:
            _copy_skill_tree(src, compat_dir / skill_entry.name, force)
        copied += 1

    if compat_dir is not None:
        click.echo(f"Copied {copied} skills to {dest_dir} and {compat_dir} (compat).")
    else:
        click.echo(f"Copied {copied} skills to {dest_dir}.")


@click.group(name="codex")
def codex_group() -> None:
    """Manage Codex CLI integration settings."""


@codex_group.command(name="install")
@click.option("--force", is_flag=True, help="Overwrite existing AGENTS.md without prompting")
def codex_install(force: bool) -> None:
    """Generate AGENTS.md in the current directory for Codex CLI.

    Reads registered agents, instructions, and skills from
    ``~/.ai-adapter/`` and generates a plain Markdown AGENTS.md file.
    """
    content = generate_agents_md()
    if not content:
        click.echo("No agents, instructions, or skills registered.")
        click.echo("Nothing to generate.")
        return

    output_path = Path.cwd() / "AGENTS.md"

    if output_path.exists() and not force:
        click.confirm(f"'{output_path.name}' already exists. Overwrite?", abort=True)

    output_path.write_text(content, encoding="utf-8")
    _config.add_to_gitignore(output_path)
    click.echo(f"AGENTS.md generated: {output_path}")


@codex_group.command(name="uninstall")
def codex_uninstall() -> None:
    """Remove AGENTS.md from the current directory."""
    output_path = Path.cwd() / "AGENTS.md"

    if not output_path.exists():
        click.echo("AGENTS.md not found.")
        return

    output_path.unlink()
    click.echo(f"AGENTS.md removed: {output_path}")
