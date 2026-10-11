"""agent subcommand implementation.

Manages agent files under ~/.ai-adapter/agents/.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import click

from ai_adapter.agent_format import (
    _convert_tools_in_frontmatter,
    convert_agent_content_to,
    convert_agent_file_to_array,
    slugify_agent_name,
    strip_frontmatter_text,
    validate_agent_file,
)
from ai_adapter.agent_format import (
    find_agent_file as _find_agent_file,
)
from ai_adapter.agent_format import parse_frontmatter as _parse_frontmatter
from ai_adapter.config import (
    add_to_gitignore,
    get_agents_dir,
    get_github_agents_dir,
    load_config,
    resolve_scope_path,
    save_config,
)
from ai_adapter.models import Agent, AgentBinding
from ai_adapter.providers.claude import deploy_agent_file as _claude_deploy_agent_file
from ai_adapter.providers.claude import deploy_agents as _claude_deploy_agents
from ai_adapter.providers.claude import validate_claude_scope
from ai_adapter.providers.codex import deploy_agent_file as _codex_deploy_agent_file
from ai_adapter.providers.codex import deploy_agents as _codex_deploy_agents
from ai_adapter.providers.codex import export_agent_toml
from ai_adapter.providers.gemini import deploy_agent_file as _gemini_deploy_agent_file
from ai_adapter.providers.gemini import deploy_agents as _gemini_deploy_agents
from ai_adapter.providers.gemini import export_agent_markdown


def _get_agent_name_from_path(path: Path) -> str:
    """Get agent name from a file path.

    For .agent.md files, prefers the YAML frontmatter name.
    Otherwise strips all extensions from the filename.
    """
    if path.suffixes == [".agent", ".md"] or str(path).endswith(".agent.md"):
        # .agent.md: prefer the name from YAML frontmatter
        frontmatter = _parse_frontmatter(path)
        name_from_fm = frontmatter.get("name", "").strip()
        if name_from_fm:
            return name_from_fm
        # If no frontmatter, strip all extensions
        p = path
        while p.suffix:
            p = p.with_suffix("")
        return p.name

    # Otherwise: strip all extensions
    p = path
    while p.suffix:
        p = p.with_suffix("")
    return p.name


def _is_agent_bound_to_env(agent_name: str, env_name: str, bindings: list[AgentBinding]) -> bool:
    """Check if an agent has a binding to the specified env."""
    for b in bindings:
        if b.agent == agent_name and b.env == env_name:
            return True
    return False


def _get_agents_for_env(config, env: str | None) -> list:
    """Get agents filtered by env binding.

    If env is None, returns all agents.
    If env is specified, returns agents that have a binding to that env.
    """
    if env is None:
        return config.agents
    return [a for a in config.agents if _is_agent_bound_to_env(a.name, env, config.agent_bindings)]


def _copy_with_tools_conversion(src: Path, dest: Path, fix: bool = False, target_format: str = "object") -> None:
    """Copy *src* to *dest*, normalising ``tools`` for *target_format*.

    For ``.agent.md`` files the frontmatter ``tools`` field is checked
    against *target_format*:

    - ``"object"`` (OpenCode): array-format tools are an error;
      *fix* converts array → object.
    - ``"array"`` (VS Code): object-format tools are an error;
      *fix* converts object → array (falsy entries dropped).

    When *fix* is ``False`` (default) a warning is emitted but the file
    is copied as-is.

    For non-``.agent.md`` files the plain ``shutil.copy2`` is used
    regardless of *fix*.
    """
    if str(src).endswith(".agent.md"):
        content = src.read_text(encoding="utf-8")
        match = re.match(r"^(---\s*\n.*?\n---)", content, re.DOTALL)
        if match:
            frontmatter_block = match.group(1)
            inner = re.match(r"^---\s*\n(.*?)\n---", frontmatter_block, re.DOTALL)
            if inner:
                yaml_text = inner.group(1)
                if target_format == "array":
                    from ai_adapter.agent_format import _convert_tools_in_frontmatter_to_array

                    converted_yaml, was_modified = _convert_tools_in_frontmatter_to_array(yaml_text)
                    expected = "array"
                    wrong = "object"
                else:
                    converted_yaml, was_modified = _convert_tools_in_frontmatter(yaml_text)
                    expected = "object"
                    wrong = "array"
                if was_modified:
                    if fix:
                        # Destructive write: convert and save
                        new_frontmatter = f"---\n{converted_yaml}\n---"
                        modified = new_frontmatter + content[match.end() :]
                        dest.write_text(modified, encoding="utf-8")
                        shutil.copystat(src, dest)
                        click.echo(
                            f"  Warning: converted tools format in {dest.name}",
                            err=True,
                        )
                        return
                    else:
                        # Validate-only: warn but copy as-is
                        click.echo(
                            f"  Warning: {dest.name} has {wrong}-format tools "
                            f"(expected {expected}). Use --fix to convert.",
                            err=True,
                        )
    # Default: plain copy (also covers non-.agent.md files)
    shutil.copy2(src, dest)


def _opencode_deploy_agent(src: Path, dest_dir: Path, force: bool, fix: bool) -> Path:
    """Deploy one agent file for OpenCode.

    OpenCode's docs state that agent markdown file names become the agent
    name (``review.md`` → ``review`` agent).  A ``.agent.md`` source is
    therefore renamed to ``.md`` so the agent name matches what OpenCode
    derives (design 04 AC3, review M1 — verified against
    https://opencode.ai/docs/agents/).  Tools conversion still applies
    because OpenCode expects object-format frontmatter.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_name = src.name
    if src.name.endswith(".agent.md"):
        dest_name = src.name[: -len(".agent.md")] + ".md"
    dest = dest_dir / dest_name
    if dest.exists() and not force:
        click.confirm(f"'{dest.name}' already exists. Overwrite?", abort=True)
    _copy_with_tools_conversion(src, dest, fix=fix, target_format="object")
    return dest


def _opencode_deploy_agents(
    targets: list,
    agents_dir: Path,
    scope: str,
    project_dir: Path | None,
    fix: bool,
) -> None:
    """Deploy registered agents for OpenCode across the given scope.

    Project-scope destinations are added to ``.gitignore`` (user scope never
    is — walking up from ``$HOME`` could touch a dotfiles repo).
    """
    target = resolve_scope_path("opencode", "agents", scope, project_dir)
    copied = 0
    for agent_cfg in targets:
        src = _find_agent_file(agents_dir, agent_cfg.name)
        if src is None:
            click.echo(f"  Skip: '{agent_cfg.name}' file not found.")
            continue
        dest = _opencode_deploy_agent(src, target.path, force=False, fix=fix)
        if target.use_gitignore:
            add_to_gitignore(dest)
        copied += 1

    click.echo(f"All agents ({copied}) copied to {target.path}.")


@click.group(name="sub-agent")
def agent_group() -> None:
    """Manage AI agent instruction files (`.agent.md`)."""


@agent_group.command(name="list")
@click.option("--env", "-e", default=None, help="Filter by environment binding")
def agent_list(env: str | None) -> None:
    """List registered agents."""
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    if not config.agents:
        click.echo("No agents registered.")
        return

    agents = _get_agents_for_env(config, env)

    if not agents:
        click.echo(f"No agents registered for environment '{env}'.")
        return

    if env:
        click.echo(f"Agents (env: {env}):")
    else:
        click.echo("Agents:")
    click.echo("-" * 40)
    for agent in agents:
        bindings = [b.env for b in config.agent_bindings if b.agent == agent.name]
        binding_info = f" (env: {', '.join(bindings)})" if bindings else ""
        desc = f" - {agent.description}" if agent.description else ""
        click.echo(f"  {agent.name}{binding_info}{desc}")


@agent_group.command(name="add")
@click.argument("path", type=click.Path(exists=True, readable=True))
@click.option("--env", "-e", default=None, help="Environment name (creates binding when specified)")
@click.option(
    "--fix",
    is_flag=True,
    default=False,
    help="Convert object-format tools to array format (destructive; VS Code expects array).",
)
def agent_add(path: str, env: str | None, fix: bool) -> None:
    """Add an agent file to ~/.ai-adapter/agents/.

    PATH: Path to the agent file to add.

    When --env is specified, also creates an agent-env binding.
    """
    src = Path(path).resolve()
    agents_dir = get_agents_dir()
    agents_dir.mkdir(parents=True, exist_ok=True)

    # .agent.md format validation
    if str(src).endswith(".agent.md"):
        frontmatter = _parse_frontmatter(src)
        if not frontmatter:
            raise click.ClickException(".agent.md files require YAML frontmatter.")
        name_from_fm = frontmatter.get("name", "").strip()
        if not name_from_fm:
            raise click.ClickException(".agent.md files require a name property in frontmatter.")

    name = _get_agent_name_from_path(src)
    dest = agents_dir / src.name

    if dest.exists():
        click.confirm(f"'{dest.name}' already exists. Overwrite?", abort=True)

    shutil.copy2(src, dest)
    if str(dest).endswith(".agent.md"):
        errors = validate_agent_file(dest, target_format="array")
        if errors:
            if fix:
                convert_agent_file_to_array(dest)
                click.echo(
                    f"  Warning: converted tools format in {dest.name}",
                    err=True,
                )
            else:
                for err in errors:
                    click.echo(f"  Warning: {err}", err=True)
                click.echo(
                    "  Use --fix to convert automatically.",
                    err=True,
                )
    click.echo(f"Agent '{name}' added: {dest}")

    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    # Duplicate check
    for existing in config.agents:
        if existing.name == name:
            # On overwrite, do not update description (file-based anyway)
            # Add env binding if specified
            if env:
                if not _is_agent_bound_to_env(name, env, config.agent_bindings):
                    config.agent_bindings.append(AgentBinding(agent=name, env=env))
                    click.echo(f"Agent '{name}' bound to env '{env}'.")
            save_config(config)
            return

    config.agents.append(Agent(name=name))
    # Add env binding if specified
    if env:
        config.agent_bindings.append(AgentBinding(agent=name, env=env))
        click.echo(f"Agent '{name}' bound to env '{env}'.")
    save_config(config)


@agent_group.command(name="add-rec")
@click.argument("dir_path", type=click.Path(exists=True, file_okay=False, readable=True))
@click.option("--env", "-e", default=None, help="Environment name (creates bindings when specified)")
@click.option(
    "--fix",
    is_flag=True,
    default=False,
    help="Convert object-format tools to array format (destructive; VS Code expects array).",
)
def agent_add_rec(dir_path: str, env: str | None, fix: bool) -> None:
    """Recursively register all agent files in a directory.

    When --env is specified, also creates agent-env bindings.
    """
    src_dir = Path(dir_path).resolve()
    agents_dir = get_agents_dir()
    agents_dir.mkdir(parents=True, exist_ok=True)

    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    added = 0
    converted = 0
    warned = 0
    for f in sorted(src_dir.rglob("*")):
        if not f.is_file():
            continue
        if str(f).endswith(".agent.md"):
            frontmatter = _parse_frontmatter(f)
            if not frontmatter or not frontmatter.get("name", "").strip():
                continue

        name = _get_agent_name_from_path(f)
        dest = agents_dir / f.name
        config.agents = [a for a in config.agents if a.name != name]
        shutil.copy2(f, dest)
        if str(dest).endswith(".agent.md"):
            errors = validate_agent_file(dest, target_format="array")
            if errors:
                if fix:
                    convert_agent_file_to_array(dest)
                    converted += 1
                else:
                    warned += 1
        config.agents.append(Agent(name=name))
        # Add env binding if specified
        if env:
            if not _is_agent_bound_to_env(name, env, config.agent_bindings):
                config.agent_bindings.append(AgentBinding(agent=name, env=env))
        added += 1

    save_config(config)
    click.echo(f"Agents added: {added}")
    if converted:
        click.echo(
            f"  Warning: converted tools format in {converted} file(s).",
            err=True,
        )
    if warned:
        click.echo(
            f"  Warning: {warned} file(s) have array-format tools. Use --fix to convert.",
            err=True,
        )


@agent_group.command(name="get")
@click.argument("name")
@click.option("--env", "-e", default=None, help="Filter by environment binding")
@click.option("--force", is_flag=True, help="Overwrite existing files without prompting")
@click.option(
    "--fix",
    is_flag=True,
    default=False,
    help="Normalise tools format for the target platform (destructive).",
)
@click.option(
    "--project-dir",
    "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="Target project directory (default: current directory; ignored with --scope user)",
)
@click.option(
    "--format",
    "-f",
    "format_name",
    type=click.Choice(["standard", "claude", "opencode", "codex", "gemini"]),
    default="standard",
    help=(
        "Output format (standard=.github/agents/, claude=.claude/agents/, "
        "opencode=.github/agents/ or ~/.config/opencode/agents/, "
        "codex=.codex/agents/*.toml, gemini=.gemini/agents/*.md)"
    ),
)
@click.option(
    "--scope",
    type=click.Choice(["project", "user"]),
    default="project",
    help=(
        "Deploy scope for --format claude/opencode/codex/gemini: "
        "project=.claude/agents/, .github/agents/, .codex/agents/ or .gemini/agents/, "
        "user=~/.claude/agents/, ~/.config/opencode/agents/, ~/.codex/agents/ or ~/.gemini/agents/"
    ),
)
def agent_get(
    name: str,
    env: str | None,
    force: bool,
    fix: bool,
    project_dir: str | None,
    format_name: str,
    scope: str,
) -> None:
    """Copy agent file to .github/agents/ (or .claude/agents/ with --format claude).

    NAME: Agent name to retrieve (no extension needed).

    With --format claude, ``.agent.md`` files are renamed to ``.md``
    (Claude Code reads ``.md``) and tools are normalised to Claude's
    comma-separated string format (``tools: Read, Grep``).  With --format
    opencode, files keep their original
    names and deploy to ``~/.config/opencode/agents/`` with ``--scope
    user``.  With --format codex, agents are converted to Codex
    custom-agent TOML (``.codex/agents/*.toml``).  With --format gemini,
    agents are converted to Gemini CLI subagent Markdown
    (``.gemini/agents/*.md``).  Use --env to only get agents bound to a
    specific environment.
    """
    validate_claude_scope(format_name, scope, ignored_option="--project-dir" if project_dir else None)
    config = load_config()
    agents_dir = get_agents_dir()

    # If --env is specified, check that the agent is bound to that env
    if env and config:
        if not _is_agent_bound_to_env(name, env, config.agent_bindings):
            click.echo(f"Agent '{name}' is not bound to environment '{env}'.", err=True)
            raise click.ClickException(f"Agent '{name}' not found for env '{env}'.")

    src = _find_agent_file(agents_dir, name)

    if src is None:
        click.echo(f"Agent '{name}' not found.", err=True)
        raise click.ClickException(f"Agent '{name}' is not registered.")

    project_path = Path(project_dir).resolve() if project_dir else None

    if format_name == "claude":
        target = resolve_scope_path("claude", "agents", scope, project_path)
        dest = _claude_deploy_agent_file(src, target.path, force, fix=fix)
        if target.use_gitignore:
            add_to_gitignore(dest)
        click.echo(f"Agent '{name}' copied to {dest}.")
        return

    if format_name == "opencode":
        target = resolve_scope_path("opencode", "agents", scope, project_path)
        dest = _opencode_deploy_agent(src, target.path, force, fix=fix)
        if target.use_gitignore:
            add_to_gitignore(dest)
        click.echo(f"Agent '{name}' copied to {dest}.")
        return

    if format_name == "codex":
        target = resolve_scope_path("codex", "agents", scope, project_path)
        dest = _codex_deploy_agent_file(src, target.path, force)
        if target.use_gitignore:
            add_to_gitignore(dest)
        click.echo(f"Agent '{name}' converted to {dest}.")
        return

    if format_name == "gemini":
        target = resolve_scope_path("gemini", "agents", scope, project_path)
        dest = _gemini_deploy_agent_file(src, target.path, force)
        if target.use_gitignore:
            add_to_gitignore(dest)
        click.echo(f"Agent '{name}' converted to {dest}.")
        return

    github_dir = get_github_agents_dir(project_path)
    github_dir.mkdir(parents=True, exist_ok=True)

    dest = github_dir / src.name

    if dest.exists() and not force:
        click.confirm(f"'{dest.name}' already exists. Overwrite?", abort=True)

    _copy_with_tools_conversion(src, dest, fix=fix, target_format="array")
    add_to_gitignore(dest)
    click.echo(f"Agent '{name}' copied to {dest}.")


@agent_group.command(name="get-all")
@click.option("--env", "-e", default=None, help="Filter by environment binding")
@click.option(
    "--project-dir",
    "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="Target project directory (default: current directory; ignored with --scope user)",
)
@click.option(
    "--fix",
    is_flag=True,
    default=False,
    help="Normalise tools format for the target platform (destructive).",
)
@click.option(
    "--format",
    "-f",
    "format_name",
    type=click.Choice(["standard", "claude", "opencode", "codex", "gemini"]),
    default="standard",
    help=(
        "Output format (standard=.github/agents/, claude=.claude/agents/, "
        "opencode=.github/agents/ or ~/.config/opencode/agents/, "
        "codex=.codex/agents/*.toml, gemini=.gemini/agents/*.md)"
    ),
)
@click.option(
    "--scope",
    type=click.Choice(["project", "user"]),
    default="project",
    help=(
        "Deploy scope for --format claude/opencode/codex/gemini: "
        "project=.claude/agents/, .github/agents/, .codex/agents/ or .gemini/agents/, "
        "user=~/.claude/agents/, ~/.config/opencode/agents/, ~/.codex/agents/ or ~/.gemini/agents/"
    ),
)
def agent_get_all(
    env: str | None,
    project_dir: str | None,
    fix: bool,
    format_name: str,
    scope: str,
) -> None:
    """Copy all registered agents to .github/agents/ (or .claude/agents/ with --format claude).

    With --format claude, ``.agent.md`` files are renamed to ``.md`` and
    tools are normalised to Claude's comma-separated string format.  With --format
    opencode, files keep their original names and deploy to
    ``~/.config/opencode/agents/`` with ``--scope user``.  With --format
    codex, agents are converted to Codex custom-agent TOML.  With
    --format gemini, agents are converted to Gemini CLI subagent
    Markdown.  Use --env to only deploy agents bound to a specific
    environment.
    """
    validate_claude_scope(format_name, scope, ignored_option="--project-dir" if project_dir else None)
    config = load_config()
    if config is None or not config.agents:
        click.echo("No agents registered.")
        return

    agents_dir = get_agents_dir()
    project_path = Path(project_dir).resolve() if project_dir else None

    targets = _get_agents_for_env(config, env)

    if format_name == "claude":
        _claude_deploy_agents(targets, agents_dir, scope=scope, project_dir=project_path, fix=fix)
        return

    if format_name == "opencode":
        _opencode_deploy_agents(targets, agents_dir, scope=scope, project_dir=project_path, fix=fix)
        return

    if format_name == "codex":
        _codex_deploy_agents(targets, agents_dir, scope=scope, project_dir=project_path)
        return

    if format_name == "gemini":
        _gemini_deploy_agents(targets, agents_dir, scope=scope, project_dir=project_path)
        return

    github_dir = get_github_agents_dir(project_path)
    github_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for agent_cfg in targets:
        name = agent_cfg.name
        src = _find_agent_file(agents_dir, name)
        if src is None:
            click.echo(f"  Skip: '{name}' file not found.")
            continue

        dest = github_dir / src.name
        _copy_with_tools_conversion(src, dest, fix=fix, target_format="array")
        add_to_gitignore(dest)
        copied += 1

    click.echo(f"All agents ({copied}) copied to {github_dir}.")


# ── convert: one file → one platform ────────────────────────────────────
# Tools format differs per platform (see
# documents/dev/ai-coding-frontmatter-comparison.json).  A converted file
# is only loaded by the platform it targets, and each platform scans a
# different directory / extension.  To make the target unmistakable — and
# to keep a converted file from being picked up by the wrong scanner that
# happens to share the directory — every output file is prefixed with
# ``<format>--`` (e.g. ``codex--content-marketing.toml``).

_CONVERT_FORMATS = ("vscode", "claude", "opencode", "gemini", "codex")


def _convert_agent_content(src: Path, format_name: str) -> tuple[str, str]:
    """Convert one agent file for *format_name*.

    Returns ``(content, extension)`` where *extension* includes the dot
    (the filename stem is computed by the caller).  Frontmatter is parsed
    once; each branch re-emits only the fields that platform understands.
    """
    from ai_adapter.agent_format import convert_tools_to_array

    content = src.read_text(encoding="utf-8")
    fm = _parse_frontmatter(src)
    name = slugify_agent_name(str(fm.get("name") or "")) or slugify_agent_name(src.stem) or "agent"
    description = str(fm.get("description") or "").strip()
    model = fm.get("model")
    if isinstance(model, list):
        model = next((m for m in model if isinstance(m, str) and m), None)
    elif not isinstance(model, str) or not model:
        model = None
    body = strip_frontmatter_text(content).strip()

    if format_name == "codex":
        return export_agent_toml(name, description, body, model=model), ".toml"

    if format_name == "gemini":
        tools, _ = convert_tools_to_array(fm.get("tools"))
        return (
            export_agent_markdown(name, description, body, tools=tools or None, model=model),
            ".md",
        )

    shape = {"vscode": "array", "opencode": "object", "claude": "string"}[format_name]
    ext = ".agent.md" if format_name == "vscode" else ".md"
    return convert_agent_content_to(content, shape), ext


@agent_group.command(name="convert")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option(
    "--format",
    "-f",
    "format_name",
    type=click.Choice(list(_CONVERT_FORMATS)),
    required=True,
    help="Target platform.",
)
@click.option(
    "--output-dir",
    "-o",
    "output_dir",
    type=click.Path(file_okay=False),
    default=None,
    help="Output directory (default: alongside the source file).",
)
@click.option(
    "--prefix/--no-prefix",
    "use_prefix",
    default=True,
    help="Prefix the output filename with '<format>--' (default: on).",
)
@click.option("--stdout", "to_stdout", is_flag=True, help="Print to stdout instead of writing a file.")
def agent_convert(
    path: str,
    format_name: str,
    output_dir: str | None,
    use_prefix: bool,
    to_stdout: bool,
) -> None:
    """Convert an agent file's tools format for one platform.

    PATH is a `.agent.md` (or `.md`) file.  The `tools` field is normalised
    to the target platform's shape:

    \b
      vscode   array format, kept as .agent.md
      claude   comma-separated string, .md
      opencode object format, .md
      gemini   array format + slugified name, .md (body = system prompt)
      codex    TOML (name/description/developer_instructions), .toml

    The output filename is prefixed with `<format>--` by default so the
    intended platform is unmistakable and a converted file is not picked up
    by another tool that happens to scan the same directory.  Use
    --no-prefix to keep the original stem, or --stdout to preview.
    """
    src = Path(path)
    converted, ext = _convert_agent_content(src, format_name)

    stem = src.name
    for suffix in (".agent.md", ".md"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    stem = slugify_agent_name(stem) or "agent"
    out_name = f"{format_name}--{stem}{ext}" if use_prefix else f"{stem}{ext}"

    if to_stdout:
        click.echo(converted, nl=False)
        return

    out_dir = Path(output_dir) if output_dir else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / out_name
    if dest.exists():
        click.confirm(f"'{dest.name}' already exists. Overwrite?", abort=True)
    dest.write_text(converted, encoding="utf-8")
    click.echo(f"Agent '{src.name}' converted for {format_name}: {dest}")


@agent_group.command(name="remove")
@click.argument("name")
@click.option("--env", "-e", default=None, help="Remove only the env binding (not the agent)")
@click.option(
    "--keep-file/--no-keep-file",
    default=False,
    help="Keep physical files (default: also delete files)",
)
def agent_remove(name: str, env: str | None, keep_file: bool) -> None:
    """Remove an agent (or only its env binding when --env is specified).

    NAME: Name of the agent to remove.

    With --env, only removes the binding to that env (agent remains).
    Without --env, removes the agent entirely.
    """
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    # If --env is specified, only remove the binding
    if env:
        found_binding = None
        for b in config.agent_bindings:
            if b.agent == name and b.env == env:
                found_binding = b
                break
        if found_binding is None:
            click.echo(f"Agent '{name}' is not bound to environment '{env}'.", err=True)
            raise click.ClickException(f"Binding '{name}' -> '{env}' not found.")
        config.agent_bindings.remove(found_binding)
        save_config(config)
        click.echo(f"Agent '{name}' unbound from env '{env}'.")
        return

    # Remove from config (full removal)
    found = False
    for agent in list(config.agents):
        if agent.name == name:
            config.agents.remove(agent)
            found = True
            break

    if not found:
        click.echo(f"Agent '{name}' is not registered.", err=True)
        raise click.ClickException(f"Agent '{name}' not found.")

    # Also remove all bindings for this agent
    config.agent_bindings = [b for b in config.agent_bindings if b.agent != name]

    save_config(config)

    # Delete file
    if not keep_file:
        agents_dir = get_agents_dir()
        for f in agents_dir.iterdir():
            # Check for .agent.md / .md / exact name patterns
            candidates = [
                f.name == f"{name}.agent.md",
                f.name == f"{name}.md",
                f.name == name,
                _get_agent_name_from_path(f) == name,
            ]
            if any(candidates):
                f.unlink()
                click.echo(f"File {f.name} deleted.")
                break

    # Also delete from .github/agents/
    github_dir = get_github_agents_dir()
    if github_dir.exists():
        for f in github_dir.iterdir():
            candidates = [
                f.name == f"{name}.agent.md",
                f.name == f"{name}.md",
                f.name == name,
            ]
            if any(candidates):
                f.unlink()
                click.echo(f"Removed {f.name} from .github/agents/.")
                break

    click.echo(f"Agent '{name}' removed.")


@agent_group.command(name="remove-all")
@click.option("--env", "-e", default=None, help="Remove only env bindings for this environment")
@click.option(
    "--keep-file/--no-keep-file",
    default=False,
    help="Keep physical files (default: also delete files)",
)
@click.option("--force", is_flag=True, help="Delete without confirmation prompt")
def agent_remove_all(env: str | None, keep_file: bool, force: bool) -> None:
    """Remove all agents (or only env bindings when --env is specified).

    With --env, only removes bindings to that env (agents remain).
    Without --env, removes all agents entirely.
    """
    config = load_config()
    if config is None or not config.agents:
        click.echo("No agents registered.")
        return

    # If --env is specified, only remove bindings
    if env:
        bindings_to_remove = [b for b in config.agent_bindings if b.env == env]
        if not bindings_to_remove:
            click.echo(f"No agent bindings found for environment '{env}'.")
            return
        count = len(bindings_to_remove)
        if not force:
            click.confirm(f"Remove {count} agent binding(s) for env '{env}'?", abort=True)
        for b in bindings_to_remove:
            config.agent_bindings.remove(b)
        save_config(config)
        click.echo(f"Removed {count} agent binding(s) for env '{env}'.")
        return

    # Full removal
    count = len(config.agents)
    if not force:
        click.confirm(f"Remove all agents ({count})?", abort=True)

    agents_dir = get_agents_dir()

    # Delete files
    if not keep_file and agents_dir.exists():
        for f in agents_dir.iterdir():
            if f.is_file():
                f.unlink()

    config.agents.clear()
    config.agent_bindings.clear()
    save_config(config)
    click.echo(f"All agents ({count}) removed.")
