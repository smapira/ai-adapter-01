"""instruction subcommand implementation.

Manages root-level agent instruction files (AGENTS.md, AGENT.md, etc.)
under ~/.ai-adapter/instructions/. Deploys to the project root (default)
or, with ``--format <platform> --scope user``, to each platform's user
directory (e.g. ~/.codex/AGENTS.md).

``--target github-instructions`` deploys to ``.github/instructions/`` and
``--target github-copilot`` deploys to ``.github/copilot-instructions.md``
(design 08). ``--target`` is incompatible with ``--format``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import click

from ai_adapter.config import (
    USER_INSTRUCTION_FILENAMES,
    add_to_gitignore,
    get_github_instructions_dir,
    get_instructions_dir,
    get_user_instruction_path,
    load_config,
    resolve_scope_path,
    save_config,
)
from ai_adapter.models import Instruction
from ai_adapter.providers.cursor import CURSORRULES_FILENAME, export_cursorrules

# --format choices (design 01 §2.1). "standard" keeps original filenames;
# "cursorrules" (design 07) writes the legacy project-root .cursorrules;
# "cursor" stays unsupported because Cursor has no native agent concept.
PLATFORM_FORMATS: tuple[str, ...] = ("codex", "claude", "opencode", "gemini", "zed")
FORMAT_CHOICES: tuple[str, ...] = ("standard", "cursor", "cursorrules", *PLATFORM_FORMATS)


@click.group(name="instruction")
def instruction_group() -> None:
    """Manage root-level agent instruction files (AGENTS.md)."""


@instruction_group.command(name="list")
def instruction_list() -> None:
    """List registered instructions."""
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    if not config.instructions:
        click.echo("No instructions registered.")
        return

    click.echo("Instructions:")
    click.echo("-" * 40)
    for inst in config.instructions:
        desc = f" - {inst.description}" if inst.description else ""
        click.echo(f"  {inst.name}{desc}")


@instruction_group.command(name="add")
@click.argument("path", type=click.Path(exists=True, readable=True))
def instruction_add(path: str) -> None:
    """Add an instruction file to ~/.ai-adapter/instructions/.

    PATH: Path to the instruction file (e.g. AGENTS.md, CLAUDE.md).
    """
    src = Path(path).resolve()
    instructions_dir = get_instructions_dir()
    instructions_dir.mkdir(parents=True, exist_ok=True)

    name = src.stem
    dest = instructions_dir / src.name

    if dest.exists():
        click.confirm(f"'{dest.name}' already exists. Overwrite?", abort=True)

    shutil.copy2(src, dest)
    content = src.read_text(encoding="utf-8")[:200]
    click.echo(f"Instruction '{name}' added: {dest}")

    config = load_config()
    if config is None:
        return

    for existing in config.instructions:
        if existing.name == name:
            save_config(config)
            return

    config.instructions.append(Instruction(name=name, content=content))
    save_config(config)


def _find_instruction_by_name(instructions_dir: Path, name: str) -> Path | None:
    """Find an instruction file by name."""
    # 1. Exact match
    exact = instructions_dir / name
    if exact.exists() and exact.is_file():
        return exact

    # 2. Search with extension
    for f in sorted(instructions_dir.iterdir()):
        if f.is_file() and f.stem == name:
            return f

    return None


def _reject_cursor_format(format_name: str, command: str) -> None:
    """Fail fast: Cursor has no native agent concept.

    Agent instructions (AGENTS.md) cannot be converted to a Cursor format,
    so ``--format cursor`` always exits with code 2 and a clear reason.
    ``--format cursorrules`` is a separate legacy escape hatch (design 07).
    """
    if format_name != "cursor":
        return
    click.echo(
        f"Error: 'agent {command} --format cursor' is not supported. "
        "Cursor has no native 'agent' concept, so agent instructions "
        "(AGENTS.md) cannot be converted to a Cursor format. "
        "Supported formats: standard, cursorrules.",
        err=True,
    )
    raise click.exceptions.Exit(2)


def _validate_format_scope(format_name: str, scope: str, project_dir: str | None) -> None:
    """Reject invalid --format/--scope combinations.

    ``--scope user`` needs a platform format to know *which* user directory
    to use, and ``--project-dir`` only makes sense for project scope.
    ``cursorrules`` is a project-root file with no user-scope location.
    """
    if scope == "user" and format_name in ("standard", "cursorrules"):
        raise click.ClickException(f"--format {format_name} does not support --scope user")
    if scope == "user" and project_dir is not None:
        click.echo("Warning: --project-dir is ignored with --scope user.", err=True)


def _resolve_get_dest(src: Path, format_name: str, scope: str, project_dir: str | None, target: str = "root") -> Path:
    """Return the deploy destination for a single instruction.

    User scope writes to the platform directory under $HOME keeping the
    source filename (arbitrary names are allowed); project scope keeps the
    existing project-root behaviour untouched.

    When *target* is a GitHub destination (design 08), the path is resolved
    from the project directory regardless of *format_name* — ``--target``
    implies standard format and project scope.
    """
    if target == "github-instructions":
        base = Path(project_dir).resolve() if project_dir else Path.cwd()
        return base / ".github" / "instructions" / src.name
    if target == "github-copilot":
        base = Path(project_dir).resolve() if project_dir else Path.cwd()
        return base / ".github" / "copilot-instructions.md"
    if scope == "user":
        return get_user_instruction_path(format_name, filename=src.name)
    project_path = Path(project_dir).resolve() if project_dir else None
    return get_github_instructions_dir(project_path) / src.name


def _deploy_cursorrules(
    named_contents: list[tuple[str, str]],
    project_dir: str | None,
    force: bool,
) -> Path:
    """Write instruction content to ./.cursorrules (legacy Cursor format).

    The destination resolves through :func:`resolve_scope_path` so the
    project-root deploy stays consistent with every other tool (design 01),
    and the ScopeTarget gitignore flag is honoured the same way.

    Args:
        named_contents: ``(name, raw content)`` pairs; frontmatter is
            stripped and multiple entries are joined with separators by
            :func:`export_cursorrules`.
        project_dir: Target project directory (default: cwd).
        force: Overwrite an existing .cursorrules without prompting.

    Returns:
        The written ``.cursorrules`` path.
    """
    project_path = Path(project_dir).resolve() if project_dir else None
    target = resolve_scope_path("cursor", "instruction", "project", project_path)
    dest = target.path / CURSORRULES_FILENAME

    if dest.exists() and not force:
        click.confirm(f"'{dest.name}' already exists. Overwrite?", abort=True)

    content = export_cursorrules(named_contents)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(f"{content}\n" if content else "", encoding="utf-8")
    if target.use_gitignore:
        add_to_gitignore(dest)
    return dest


@instruction_group.command(name="get")
@click.argument("name")
@click.option(
    "--project-dir",
    "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="Target project directory (default: current directory; ignored with --scope user)",
)
@click.option("--force", is_flag=True, help="Overwrite existing file without prompting")
@click.option(
    "--format",
    "-f",
    "format_name",
    type=click.Choice(FORMAT_CHOICES),
    default=None,
    help=(
        "Output format (standard=project root, "
        "cursorrules=.cursorrules legacy rules file, "
        "codex/claude/opencode/gemini/zed=platform user paths, cursor=unsupported)"
    ),
)
@click.option(
    "--scope",
    type=click.Choice(["project", "user"]),
    default="project",
    help="project=project root (default), user=platform user directory",
)
@click.option(
    "--target",
    type=click.Choice(["root", "github-instructions", "github-copilot"]),
    default="root",
    help=(
        "Deploy target: root=project root (default), "
        "github-instructions=.github/instructions/, "
        "github-copilot=.github/copilot-instructions.md"
    ),
)
def instruction_get(
    name: str,
    project_dir: str | None,
    force: bool,
    format_name: str | None,
    scope: str,
    target: str,
) -> None:
    """Copy instruction to project root (./AGENTS.md etc.) or a user path.

    NAME: Instruction name to retrieve (no extension needed).
    """
    # --target is incompatible with --format (design 08 task 08-1).
    # When --target is specified (non-root), --format must not be explicitly
    # given — it is locked to standard. Using both is an error.
    if target != "root":
        if format_name is not None:
            raise click.ClickException("--target is incompatible with --format")
        format_name = "standard"
        if scope != "project":
            raise click.ClickException("--target is only supported with --scope project")
    if format_name is None:
        format_name = "standard"

    _reject_cursor_format(format_name, "get")
    _validate_format_scope(format_name, scope, project_dir)

    instructions_dir = get_instructions_dir()
    src = _find_instruction_by_name(instructions_dir, name)

    if src is None:
        click.echo(f"Instruction '{name}' not found.", err=True)
        raise click.ClickException(f"Instruction '{name}' is not registered.")

    # Legacy .cursorrules (design 07): single file, frontmatter stripped.
    # --target is already rejected for any explicit --format above.
    if format_name == "cursorrules":
        content = src.read_text(encoding="utf-8")
        dest = _deploy_cursorrules([(src.stem, content)], project_dir, force)
        click.echo(f"Instruction content written to {dest}.")
        return

    dest = _resolve_get_dest(src, format_name, scope, project_dir, target)

    if dest.exists() and not force:
        click.confirm(f"'{dest.name}' already exists. Overwrite?", abort=True)

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    # GitHub-targeted instructions are team-shared workspace config (Copilot
    # reads them from the repo); do not gitignore them (review M2).
    if scope == "project" and target == "root":
        add_to_gitignore(dest)
    click.echo(f"Instruction '{name}' copied to {dest}.")


@instruction_group.command(name="remove")
@click.argument("name")
def instruction_remove(name: str) -> None:
    """Remove an instruction."""
    config = load_config()
    if config is None:
        return

    found = None
    for inst in config.instructions:
        if inst.name == name:
            found = inst
            break

    if found is None:
        click.echo(f"Instruction '{name}' is not registered.", err=True)
        raise click.ClickException(f"Instruction '{name}' not found.")

    config.instructions.remove(found)
    save_config(config)

    instructions_dir = get_instructions_dir()
    for f in instructions_dir.iterdir():
        if f.stem == name or f.name == name:
            f.unlink()
            click.echo(f"File {f.name} removed.")
            break

    # Also delete from project root (standard target)
    root_dir = get_github_instructions_dir()
    if root_dir.exists():
        for f in root_dir.iterdir():
            if f.stem == name or f.name == name:
                f.unlink()
                break

    # Also delete from --target github-* deploy destinations (review M3:
    # get/remove lifecycle must match, otherwise files linger forever).
    github_instructions = Path.cwd() / ".github" / "instructions"
    if github_instructions.is_dir():
        for f in github_instructions.iterdir():
            if f.is_file() and (f.stem == name or f.name == name):
                f.unlink()
                click.echo(f"Removed {f.name} from .github/instructions/.")
    # copilot-instructions.md is a fixed-name deploy target (--target
    # github-copilot). Any instruction may have been deployed there, so
    # do not require the stem to match the instruction name (QA M3).
    copilot_instructions = Path.cwd() / ".github" / "copilot-instructions.md"
    if copilot_instructions.is_file():
        copilot_instructions.unlink()
        click.echo("Removed copilot-instructions.md from .github/.")

    click.echo(f"Instruction '{name}' removed.")


@instruction_group.command(name="add-rec")
@click.argument("dir_path", type=click.Path(exists=True, file_okay=False, readable=True))
def instruction_add_rec(dir_path: str) -> None:
    """Recursively add all files in a directory to ~/.ai-adapter/instructions/."""
    src_dir = Path(dir_path).resolve()
    instructions_dir = get_instructions_dir()
    instructions_dir.mkdir(parents=True, exist_ok=True)

    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    added = 0
    for f in sorted(src_dir.rglob("*")):
        if not f.is_file():
            continue
        dest = instructions_dir / f.name
        config.instructions = [i for i in config.instructions if i.name != f.stem]
        shutil.copy2(f, dest)
        content = f.read_text(encoding="utf-8")[:200]
        config.instructions.append(Instruction(name=f.stem, content=content))
        added += 1

    save_config(config)
    click.echo(f"Instructions added: {added}")


def _resolve_get_all_dest_name(
    src_name: str,
    format_name: str,
    scope: str,
    root_dir: Path,
    placed: set[str],
) -> tuple[str, str | None]:
    """Return (destination filename, attempted mapped name) for one get-all copy.

    User scope maps every file to the name its platform actually reads
    (see :data:`USER_INSTRUCTION_FILENAMES`). When that name is already
    taken — by an earlier file in this run or an existing file on disk —
    the source filename is kept instead so nothing is overwritten silently.
    If the source filename is also taken, a numbered suffix is appended.
    """
    if scope != "user":
        return src_name, None
    mapped_name = USER_INSTRUCTION_FILENAMES[format_name]

    def _is_taken(name: str) -> bool:
        return name in placed or (root_dir / name).exists()

    # Collision check FIRST — before the identity shortcut — so that a file
    # whose native name equals the platform mapping cannot silently overwrite
    # an earlier mapping target (review C1).
    if not _is_taken(mapped_name):
        return mapped_name, mapped_name
    if not _is_taken(src_name):
        return src_name, mapped_name
    # Both taken: append a numbered suffix so nothing is lost silently.
    stem, suffix = Path(src_name).stem, Path(src_name).suffix
    n = 1
    while _is_taken(f"{stem} ({n}){suffix}"):
        n += 1
    return f"{stem} ({n}){suffix}", mapped_name


def _format_get_all_mapping(src_name: str, dest_name: str, mapped_name: str | None, scope: str) -> str | None:
    """Build the per-file mapping line for user-scope get-all output."""
    if scope != "user" or mapped_name is None:
        return None
    if dest_name != mapped_name:
        return f"  {src_name} → {mapped_name} (conflict, kept as {dest_name})"
    if dest_name != src_name:
        return f"  {src_name} → {dest_name} (mapped)"
    # Identity mapping (src name equals platform name): still show the line
    # so the output matches the design document's examples.
    return f"  {src_name} → {dest_name}"


@instruction_group.command(name="get-all")
@click.option(
    "--project-dir",
    "-d",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help="Target project directory (default: current directory; ignored with --scope user)",
)
@click.option("--force", is_flag=True, help="Overwrite existing files without prompting")
@click.option(
    "--format",
    "-f",
    "format_name",
    type=click.Choice(FORMAT_CHOICES),
    default="standard",
    help=(
        "Output format (standard=keep filenames, "
        "cursorrules=.cursorrules legacy rules file, "
        "codex/claude/opencode/gemini/zed=platform user paths, cursor=unsupported)"
    ),
)
@click.option(
    "--scope",
    type=click.Choice(["project", "user"]),
    default="project",
    help="project=project root (default), user=platform user directory",
)
def instruction_get_all(
    project_dir: str | None,
    force: bool,
    format_name: str,
    scope: str,
) -> None:
    """Copy all registered instructions to project root or a user path."""
    _reject_cursor_format(format_name, "get-all")
    _validate_format_scope(format_name, scope, project_dir)

    config = load_config()
    if config is None or not config.instructions:
        click.echo("No instructions registered.")
        return

    instructions_dir = get_instructions_dir()
    project_path = Path(project_dir).resolve() if project_dir else None

    # Legacy .cursorrules (design 07): concatenate every instruction into a
    # single file with separator comments.
    if format_name == "cursorrules":
        named_contents: list[tuple[str, str]] = []
        for inst_entry in config.instructions:
            src = _find_instruction_by_name(instructions_dir, inst_entry.name)
            if src is None:
                click.echo(f"   Skip: '{inst_entry.name}' file not found.")
                continue
            named_contents.append((src.stem, src.read_text(encoding="utf-8")))
        if not named_contents:
            click.echo("No instructions found.")
            return
        dest = _deploy_cursorrules(named_contents, project_dir, force)
        click.echo(f"All instructions written to {dest}.")
        return

    if scope == "user":
        root_dir = get_user_instruction_path(format_name).parent
    else:
        root_dir = get_github_instructions_dir(project_path)

    copied = 0
    placed: set[str] = set()
    mapping_lines: list[str] = []
    for inst_entry in config.instructions:
        src = _find_instruction_by_name(instructions_dir, inst_entry.name)
        if src is None:
            click.echo(f"   Skip: '{inst_entry.name}' file not found.")
            continue
        dest_name, mapped_name = _resolve_get_all_dest_name(src.name, format_name, scope, root_dir, placed)
        dest = root_dir / dest_name
        if dest.exists() and not force:
            click.confirm(f"Overwrite '{dest.name}'?", abort=True)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        if scope == "project":
            add_to_gitignore(dest)
        placed.add(dest.name)
        copied += 1
        line = _format_get_all_mapping(src.name, dest_name, mapped_name, scope)
        if line:
            mapping_lines.append(line)

    if scope == "user":
        click.echo(f"Copied {copied} instructions to {root_dir}.")
        for line in mapping_lines:
            click.echo(line)
    else:
        click.echo(f"All instructions ({copied}) copied to {root_dir}.")


@instruction_group.command(name="remove-all")
@click.option("--force", is_flag=True, help="Delete without confirmation")
def instruction_remove_all(force: bool) -> None:
    """Remove all registered instructions."""
    config = load_config()
    if config is None or not config.instructions:
        click.echo("No instructions registered.")
        return

    count = len(config.instructions)
    if not force:
        click.confirm(f"All instructions ({count})?", abort=True)

    config.instructions.clear()
    save_config(config)
    click.echo(f"All instructions ({count}) removed.")
