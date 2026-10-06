"""Environment scan module.

Discovers AI agent tool configurations — Claude Code (``~/.claude``),
Codex (``~/.codex``), Cursor (``~/.cursor``), OpenCode
(``~/.config/opencode``), VS Code (``.vscode/``), Gemini CLI
(``~/.gemini/``, ``.gemini/``), Zed (OS-specific user dir, ``.zed/``),
the current project (``.github/``, root instructions, ``.mcp.json``),
and user-scope instruction files
(``~/.codex/AGENTS.md``, ``~/.claude/CLAUDE.md``,
``~/.config/opencode/AGENTS.md``) — without reading sensitive content.

Security rules (must be kept in sync with tests/test_scan.py):
- Only filenames and YAML frontmatter (name/description/tags) are read.
- Full file contents are never printed.
- Credential files are excluded via :data:`SCAN_IGNORE_PATTERNS` and the
  component-wise :data:`_GENERIC_SECRET_COMPONENTS` check.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from ai_adapter.agent_format import parse_frontmatter
from ai_adapter.agent_plugins import ValidationIssue
from ai_adapter.models import Config

# ── Security blacklist ──────────────────────────────────────────────────
# Tool-specific glob patterns matched (case-insensitively) against
# scan-relative paths.  ``*`` matches across directory separators, so
# ``.cursor/*auth*`` covers both ``.cursor/auth.json`` and
# ``.cursor/sub/auth.json``.
SCAN_IGNORE_PATTERNS: tuple[str, ...] = (
    # Tool-specific credential stores
    ".codex/auth.json",
    ".claude/.credentials.json",
    # Cursor credentials / API keys
    ".cursor/*auth*",
    ".cursor/*key*",
    # Gemini CLI credentials / tokens (design 05)
    ".gemini/*cred*",
    ".gemini/*token*",
    # Generic secret-file extensions
    ".env",
    "*.env",
    "*.pem",
    "*.key",
)

# Filename components that identify a credential store.  These are matched
# *exactly* against the ``._-``-split basename (see :func:`_has_secret_component`)
# rather than as substrings of the full path: ``secrets.json`` / ``auth.json`` /
# ``tokens.txt`` are excluded, while normal files such as ``secretary.agent.md``
# or ``tokensmith.md`` are not (a substring match on ``*secret*`` would hide
# them).
_GENERIC_SECRET_COMPONENTS: frozenset[str] = frozenset(
    ("secret", "secrets", "token", "tokens", "auth", "credential", "credentials")
)

# Number of days after which a skill with an old ``update_date`` is
# reported as stale (severity "info").
STALE_SKILL_THRESHOLD_DAYS = 180

# Keys that hold MCP server maps, per config file type.
# "servers" is VS Code's key (design 08) — added alongside the standard
# "mcpServers" and OpenCode's "mcp".
_MCP_SERVER_KEYS = ("mcpServers", "mcp", "servers")

# Order in which tools appear in the Agents section of the report.
TOOL_ORDER = ("claude", "codex", "cursor", "opencode", "project")

# Insert "vscode" before "project" (design 08). Using tuple slicing to
# preserve the original entries without redefining the whole literal.
TOOL_ORDER = TOOL_ORDER[:-1] + ("vscode",) + TOOL_ORDER[-1:]

# Insert "gemini" before "project" (design 05). Append-only via tuple
# slicing — never redefine the whole literal.
TOOL_ORDER = TOOL_ORDER[:-1] + ("gemini",) + TOOL_ORDER[-1:]

# Insert "zed" before "project" (design 06). Append-only via tuple
# slicing — never redefine the whole literal.
TOOL_ORDER = TOOL_ORDER[:-1] + ("zed",) + TOOL_ORDER[-1:]

TOOL_LABELS: dict[str, str] = {
    "claude": "Claude Code",
    "codex": "Codex",
    "cursor": "Cursor",
    "opencode": "OpenCode",
    "vscode": "VS Code",
    "gemini": "Gemini CLI",
    "zed": "Zed",
    "project": "Project",
}


def _has_secret_component(scan_rel_path: str) -> bool:
    """Return True when the basename's ``._-``-split contains a secret word.

    Generic secret words (see :data:`_GENERIC_SECRET_COMPONENTS`) are
    compared per-component *exactly*, so ``secrets.json`` / ``token.txt`` /
    ``auth.json`` are excluded while similarly-named normal files such as
    ``secretary.agent.md`` are kept.
    """
    basename = scan_rel_path.rsplit("/", 1)[-1]
    components = set(re.split(r"[._-]+", basename))
    return bool(components & _GENERIC_SECRET_COMPONENTS)


def is_ignored(scan_rel_path: str) -> bool:
    """Return True when a scan-relative path must be excluded.

    *scan_rel_path* is the path relative to the scanned root (home or
    project directory) using forward slashes, e.g. ``".codex/auth.json"``.
    Matching is a case-insensitive glob against :data:`SCAN_IGNORE_PATTERNS`
    plus an exact per-component check against
    :data:`_GENERIC_SECRET_COMPONENTS`, so credential files never appear in
    scan results while normal files are left untouched.
    """
    normalized = scan_rel_path.replace("\\", "/").lower()
    if any(fnmatch.fnmatch(normalized, pattern.lower()) for pattern in SCAN_IGNORE_PATTERNS):
        return True
    return _has_secret_component(normalized)


# ── Data structures ─────────────────────────────────────────────────────


@dataclass
class ScanItem:
    """A single detected configuration item.

    Attributes:
        tool: Source tool — one of :data:`TOOL_ORDER`.
        category: "agent" | "skill" | "mcp" | "instruction" | "settings".
        name: Display name (frontmatter name when available, else filename).
        description: Frontmatter ``description`` when present.
        tags: Frontmatter ``tags`` list when present.
        path: Absolute path of the detected file (or SKILL.md).
        version: Frontmatter ``version`` (used for update detection).
        update_date: Frontmatter ``update_date`` (used for staleness checks).
    """

    tool: str
    category: str
    name: str
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    path: Path | None = None
    version: str | None = None
    update_date: str | None = None

    def to_dict(self) -> dict:
        d: dict = {"tool": self.tool, "category": self.category, "name": self.name}
        if self.description:
            d["description"] = self.description
        if self.tags:
            d["tags"] = self.tags
        if self.path:
            d["path"] = str(self.path)
        if self.version:
            d["version"] = self.version
        if self.update_date:
            d["update_date"] = self.update_date
        return d


@dataclass
class ScanResult:
    """Merged outcome of all detection passes."""

    items: list[ScanItem] = field(default_factory=list)
    problems: list[ValidationIssue] = field(default_factory=list)

    def count(self, tool: str | None = None, category: str | None = None) -> int:
        """Count items, optionally filtered by tool and/or category."""
        return sum(
            1
            for item in self.items
            if (tool is None or item.tool == tool) and (category is None or item.category == category)
        )

    def by_category(self, category: str) -> list[ScanItem]:
        """Return items in the given category (sorted by name)."""
        return sorted((i for i in self.items if i.category == category), key=lambda i: i.name)


# ── Detection helpers ───────────────────────────────────────────────────


def _frontmatter_text(path: Path) -> dict:
    """Parse frontmatter, tolerating unreadable/invalid files (→ {})."""
    try:
        data = parse_frontmatter(path)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _scan_agents(tool: str, agents_dir: Path, scan_rel: str) -> list[ScanItem]:
    """Detect ``*.md`` agent files directly under *agents_dir*."""
    items: list[ScanItem] = []
    if not agents_dir.is_dir():
        return items
    for f in sorted(agents_dir.iterdir()):
        if not f.is_file() or f.suffix != ".md":
            continue
        if is_ignored(f"{scan_rel}/{f.name}"):
            continue
        fm = _frontmatter_text(f)
        name = str(fm.get("name") or "").strip() or f.stem
        description = str(fm["description"]) if fm.get("description") else None
        tags = [str(t) for t in fm["tags"]] if isinstance(fm.get("tags"), list) else []
        items.append(ScanItem(tool, "agent", name, description, tags, f))
    return items


def _scan_skills(tool: str, skills_dir: Path, scan_rel: str) -> list[ScanItem]:
    """Detect ``skills/*/SKILL.md`` directories directly under *skills_dir*."""
    items: list[ScanItem] = []
    if not skills_dir.is_dir():
        return items
    for d in sorted(skills_dir.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        skill_file = d / "SKILL.md"
        if not skill_file.is_file():
            continue
        if is_ignored(f"{scan_rel}/{d.name}/SKILL.md"):
            continue
        fm = _frontmatter_text(skill_file)
        name = str(fm.get("name") or "").strip() or d.name
        description = str(fm["description"]) if fm.get("description") else None
        tags = [str(t) for t in fm["tags"]] if isinstance(fm.get("tags"), list) else []
        version = str(fm["version"]) if fm.get("version") is not None else None
        update_date = str(fm["update_date"]) if fm.get("update_date") is not None else None
        items.append(ScanItem(tool, "skill", name, description, tags, skill_file, version, update_date))
    return items


def _scan_user_instruction(tool: str, path: Path, scan_rel: str) -> list[ScanItem]:
    """Detect a user-scope root instruction file (AGENTS.md / CLAUDE.md).

    Only the well-known filename per platform is checked and no content is
    read (security rule: filenames only). :func:`is_ignored` is still applied
    so credential patterns stay excluded even if they ever cover these paths.
    """
    if not path.is_file() or is_ignored(scan_rel):
        return []
    return [ScanItem(tool, "instruction", path.name, path=path)]


def _scan_mcp_servers(tool: str, config_file: Path, scan_rel: str) -> list[ScanItem]:
    """Read MCP server *names* from a JSON config (never values).

    Recognizes the ``mcpServers`` (standard / Cursor / Claude) and ``mcp``
    (OpenCode) keys.  The file is parsed so malformed JSON is skipped, but
    only server names are reported.
    """
    items: list[ScanItem] = []
    if not config_file.is_file() or is_ignored(scan_rel):
        return items
    try:
        data = json.loads(config_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return items
    if not isinstance(data, dict):
        return items
    names: set[str] = set()
    for key in _MCP_SERVER_KEYS:
        servers = data.get(key)
        if isinstance(servers, dict):
            names.update(n for n in servers if isinstance(n, str))
    items.extend(ScanItem(tool, "mcp", name, path=config_file) for name in sorted(names))
    return items


# ── Tool-specific detection ─────────────────────────────────────────────


def scan_claude(home: Path, project_dir: Path | None = None) -> list[ScanItem]:
    """Detect Claude Code agents, skills, settings, MCP servers, and CLAUDE.md.

    Covers both scopes: the user directory ``~/.claude/`` and, when
    *project_dir* is given, the project's ``.claude/`` directory
    (design 02 task 02-4).  Project-scope items use tool ``"claude"``
    per the master design §2.6 taxonomy — they are distinct from
    ``scan_project``'s ``.github/`` detection (tool ``"project"``), so
    the same-named files in different directories never collide.
    """
    items: list[ScanItem] = []
    claude_dir = home / ".claude"
    if claude_dir.is_dir():
        items.extend(_scan_agents("claude", claude_dir / "agents", ".claude/agents"))
        items.extend(_scan_skills("claude", claude_dir / "skills", ".claude/skills"))
        items.extend(_scan_user_instruction("claude", claude_dir / "CLAUDE.md", ".claude/CLAUDE.md"))
        settings = claude_dir / "settings.json"
        if settings.is_file():
            items.append(ScanItem("claude", "settings", "settings.json", path=settings))
            items.extend(_scan_mcp_servers("claude", settings, ".claude/settings.json"))

    # Project pass. When home and the project resolve to the same directory
    # (tests, or a project scanned from its own root) the user pass above
    # already covered ".claude/" — skip it so nothing is reported twice.
    if project_dir is not None:
        project_claude = project_dir / ".claude"
        if project_claude.resolve() != claude_dir.resolve():
            items.extend(_scan_agents("claude", project_claude / "agents", ".claude/agents"))
            items.extend(_scan_skills("claude", project_claude / "skills", ".claude/skills"))
    return items


def scan_codex(home: Path) -> list[ScanItem]:
    """Detect Codex config, agents, skills, and AGENTS.md.

    ``~/.codex/auth.json`` is never reported (see :data:`SCAN_IGNORE_PATTERNS`).
    Skills are detected in both ``~/.codex/skills/`` and the spec path
    ``~/.agents/skills/`` (design 03); a skill present in both is reported
    once per path, so the ``.codex/`` copy stays recognisable as an opt-in
    compat mirror.
    """
    items: list[ScanItem] = []
    codex_dir = home / ".codex"
    if codex_dir.is_dir():
        config_toml = codex_dir / "config.toml"
        if config_toml.is_file():
            items.append(ScanItem("codex", "settings", "config.toml", path=config_toml))
        items.extend(_scan_agents("codex", codex_dir / "agents", ".codex/agents"))
        items.extend(_scan_skills("codex", codex_dir / "skills", ".codex/skills"))
        items.extend(_scan_user_instruction("codex", codex_dir / "AGENTS.md", ".codex/AGENTS.md"))
    items.extend(_scan_skills("codex", home / ".agents" / "skills", ".agents/skills"))
    return items


def scan_cursor(home: Path) -> list[ScanItem]:
    """Detect Cursor rules and MCP configuration."""
    items: list[ScanItem] = []
    cursor_dir = home / ".cursor"
    if not cursor_dir.is_dir():
        return items
    rules_dir = cursor_dir / "rules"
    if rules_dir.is_dir():
        for f in sorted(rules_dir.iterdir()):
            if not f.is_file() or f.suffix not in (".mdc", ".md"):
                continue
            if is_ignored(f".cursor/rules/{f.name}"):
                continue
            fm = _frontmatter_text(f)
            name = str(fm.get("name") or "").strip() or f.stem
            description = str(fm["description"]) if fm.get("description") else None
            items.append(ScanItem("cursor", "skill", name, description, [], f))
    mcp_json = cursor_dir / "mcp.json"
    if mcp_json.is_file():
        items.append(ScanItem("cursor", "settings", "mcp.json", path=mcp_json))
        items.extend(_scan_mcp_servers("cursor", mcp_json, ".cursor/mcp.json"))
    return items


def scan_opencode(home: Path) -> list[ScanItem]:
    """Detect the global OpenCode config and user instruction file."""
    items: list[ScanItem] = []
    opencode_dir = home / ".config" / "opencode"
    if not opencode_dir.is_dir():
        return items
    config_file = opencode_dir / "opencode.json"
    if config_file.is_file():
        items.append(ScanItem("opencode", "settings", "opencode.json", path=config_file))
        items.extend(_scan_mcp_servers("opencode", config_file, ".config/opencode/opencode.json"))
    items.extend(_scan_user_instruction("opencode", opencode_dir / "AGENTS.md", ".config/opencode/AGENTS.md"))
    return items


def scan_project(project_dir: Path, home: Path | None = None) -> list[ScanItem]:
    """Detect project-local agents, skills, instructions, and MCP servers.

    When *home* is given and *project_dir* resolves to the same directory
    (tests, or a project scanned from its own root), the Codex native-path
    pass is skipped so ``scan_codex``'s user-scope detection is not
    double-reported (design 03).
    """
    items: list[ScanItem] = []
    if not project_dir.is_dir():
        return items
    github = project_dir / ".github"
    items.extend(_scan_agents("project", github / "agents", ".github/agents"))
    items.extend(_scan_skills("project", github / "skills", ".github/skills"))
    instructions_dir = github / "instructions"
    if instructions_dir.is_dir():
        for f in sorted(instructions_dir.iterdir()):
            if not f.is_file() or f.suffix != ".md":
                continue
            if is_ignored(f".github/instructions/{f.name}"):
                continue
            items.append(ScanItem("project", "instruction", f.name, path=f))
    for fname in ("AGENTS.md", "CLAUDE.md", "copilot-instructions.md"):
        candidate = project_dir / fname
        if candidate.is_file():
            items.append(ScanItem("project", "instruction", fname, path=candidate))
    # GitHub Copilot instruction file (design 08 task 08-3): deployed to
    # .github/copilot-instructions.md by `agent get --target github-copilot`.
    copilot_github = github / "copilot-instructions.md"
    if copilot_github.is_file():
        items.append(ScanItem("project", "instruction", "copilot-instructions.md", path=copilot_github))
    mcp_json = project_dir / ".mcp.json"
    if mcp_json.is_file():
        items.append(ScanItem("project", "settings", ".mcp.json", path=mcp_json))
        items.extend(_scan_mcp_servers("project", mcp_json, ".mcp.json"))
    # Codex native paths (design 03): project config.toml + spec-path skills.
    # Skip when project_dir == home so scan_codex's user pass isn't doubled.
    if home is None or project_dir.resolve() != home.resolve():
        codex_config = project_dir / ".codex" / "config.toml"
        if codex_config.is_file():
            items.append(ScanItem("codex", "settings", ".codex/config.toml", path=codex_config))
        items.extend(_scan_skills("codex", project_dir / ".agents" / "skills", ".agents/skills"))
    return items


def scan_vscode(project_dir: Path) -> list[ScanItem]:
    """Detect VS Code configurations under ``.vscode/`` (design 08 task 08-7).

    Covers ``mcp.json`` (settings + MCP server names via the ``servers``
    key), ``extensions.json``, and ``launch.json`` / ``tasks.json``
    (detected but not managed — scan only).
    """
    items: list[ScanItem] = []
    vscode_dir = project_dir / ".vscode"
    if not vscode_dir.is_dir():
        return items
    mcp = vscode_dir / "mcp.json"
    if mcp.is_file():
        items.append(ScanItem("vscode", "settings", "mcp.json", path=mcp))
        items.extend(_scan_mcp_servers("vscode", mcp, ".vscode/mcp.json"))
    ext = vscode_dir / "extensions.json"
    if ext.is_file():
        items.append(ScanItem("vscode", "settings", "extensions.json", path=ext))
    for fname in ("launch.json", "tasks.json"):
        f = vscode_dir / fname
        if f.is_file():
            items.append(ScanItem("vscode", "settings", fname, path=f))
    return items


def _scan_gemini_commands(commands_dir: Path, scan_rel: str) -> list[ScanItem]:
    """Detect ``*.toml`` custom-command files under *commands_dir*."""
    items: list[ScanItem] = []
    if not commands_dir.is_dir():
        return items
    for f in sorted(commands_dir.rglob("*.toml")):
        rel = f"{scan_rel}/{f.relative_to(commands_dir).as_posix()}"
        if is_ignored(rel):
            continue
        items.append(ScanItem("gemini", "command", f.stem, path=f))
    return items


def _scan_gemini_settings(settings: Path, scan_rel: str) -> list[ScanItem]:
    """Detect a settings.json plus the MCP server names it defines."""
    if not settings.is_file():
        return []
    items = [ScanItem("gemini", "settings", "settings.json", path=settings)]
    items.extend(_scan_mcp_servers("gemini", settings, scan_rel))
    return items


def scan_gemini(home: Path, project_dir: Path | None = None) -> list[ScanItem]:
    """Detect Gemini CLI configurations (design 05 task 05-7).

    Covers user scope (``~/.gemini/``: commands, settings.json, GEMINI.md,
    installed extension manifests), project scope (``.gemini/``: commands,
    settings.json), and the project-root ``GEMINI.md``.
    """
    items: list[ScanItem] = []
    gemini_dir = home / ".gemini"
    if gemini_dir.is_dir():
        items.extend(_scan_gemini_commands(gemini_dir / "commands", ".gemini/commands"))
        items.extend(_scan_gemini_settings(gemini_dir / "settings.json", ".gemini/settings.json"))
        items.extend(_scan_user_instruction("gemini", gemini_dir / "GEMINI.md", ".gemini/GEMINI.md"))
        extensions_dir = gemini_dir / "extensions"
        if extensions_dir.is_dir():
            for manifest in sorted(extensions_dir.rglob("gemini-extension.json")):
                items.append(ScanItem("gemini", "settings", manifest.parent.name, path=manifest))

    if project_dir is None:
        return items

    # Skip the project pass when project_dir resolves to home (tests, or a
    # project scanned from its own root) — the user pass above already
    # covered ".gemini/" (same guard as scan_claude).
    project_gemini = project_dir / ".gemini"
    if project_gemini.resolve() != gemini_dir.resolve():
        items.extend(_scan_gemini_commands(project_gemini / "commands", ".gemini/commands"))
        items.extend(_scan_gemini_settings(project_gemini / "settings.json", ".gemini/settings.json"))

    # Project-root GEMINI.md — Gemini reads it as project context. Not part
    # of scan_project's root-instruction list, so there is no double count.
    root_context = project_dir / "GEMINI.md"
    if root_context.is_file():
        items.append(ScanItem("gemini", "instruction", "GEMINI.md", path=root_context))
    return items


def scan_zed(home: Path, project_dir: Path | None = None) -> list[ScanItem]:
    """Detect Zed editor configurations (design 06 task 06-5).

    User scope (OS-dependent directory resolved via
    :func:`ai_adapter.config.get_zed_user_dir`): ``settings.json``,
    ``AGENTS.md``, ``keymap.json``.  Project scope: ``.zed/settings.json``
    and ``.zed/tasks.json``.  Project-root ``AGENTS.md`` is already
    reported by :func:`scan_project` (tool ``project``), and Zed's
    ``.agents/skills/`` by the Codex pass — neither is re-reported here to
    avoid double counting.

    SCAN_IGNORE_PATTERNS: no Zed-specific entries needed — Zed keeps auth
    in a database outside the config directory, and :func:`is_ignored`
    still applies to every detected path as a safety net.
    """
    from ai_adapter.config import get_zed_user_dir

    items: list[ScanItem] = []
    user_dir = get_zed_user_dir(home)
    for fname in ("settings.json", "keymap.json"):
        f = user_dir / fname
        if f.is_file():
            items.append(ScanItem("zed", "settings", fname, path=f))
    user_agents = user_dir / "AGENTS.md"
    if user_agents.is_file():
        try:
            scan_rel = user_agents.resolve().relative_to(home.resolve()).as_posix()
        except ValueError:
            scan_rel = user_agents.name
        if not is_ignored(scan_rel):
            items.append(ScanItem("zed", "instruction", "AGENTS.md", path=user_agents))

    if project_dir is None:
        return items
    zed_dir = project_dir / ".zed"
    for fname in ("settings.json", "tasks.json"):
        f = zed_dir / fname
        if f.is_file():
            items.append(ScanItem("zed", "settings", fname, path=f))
    return items


def scan_all(home: Path | None = None, project_dir: Path | None = None) -> ScanResult:
    """Run every detection pass and attach the diagnostic problems.

    Args:
        home: Directory used as ``~`` (defaults to ``Path.home()``).
        project_dir: Project directory to scan (defaults to ``Path.cwd()``).
    """
    root = home or Path.home()
    project = (project_dir or Path.cwd()).resolve()
    items: list[ScanItem] = []
    items.extend(scan_claude(root, project))
    items.extend(scan_codex(root))
    items.extend(scan_cursor(root))
    items.extend(scan_opencode(root))
    items.extend(scan_project(project, root))
    items.extend(scan_vscode(project))
    items.extend(scan_gemini(root, project))
    items.extend(scan_zed(root, project))
    result = ScanResult(items=items)
    result.problems = diagnose(result)
    return result


# ── Problem diagnosis (1-2, read-only) ──────────────────────────────────


def diagnose(result: ScanResult, stale_threshold_days: int = STALE_SKILL_THRESHOLD_DAYS) -> list[ValidationIssue]:
    """Detect potential problems in *result* (read-only).

    Returns :class:`~ai_adapter.agent_plugins.ValidationIssue` objects so
    phase 3's ``doctor --fix`` can act on the same model.
    """
    problems: list[ValidationIssue] = []
    problems.extend(_check_duplicate_mcp(result))
    problems.extend(_check_skill_mismatch(result))
    problems.extend(_check_stale_skills(result, stale_threshold_days))
    return problems


def _check_duplicate_mcp(result: ScanResult) -> list[ValidationIssue]:
    """Flag MCP servers defined in more than one config file."""
    issues: list[ValidationIssue] = []
    by_name: dict[str, list[ScanItem]] = {}
    for item in result.items:
        if item.category == "mcp":
            by_name.setdefault(item.name, []).append(item)
    for name, occurrences in sorted(by_name.items()):
        locations = sorted({str(i.path) for i in occurrences if i.path})
        if len(locations) > 1:
            issues.append(
                ValidationIssue(
                    "scan",
                    f"duplicate MCP server '{name}' is defined in multiple locations: {', '.join(locations)}",
                    severity="warning",
                    path=locations[0],
                )
            )
    return issues


def _file_sha256(path: Path) -> str:
    """Return the SHA-256 of a file (content is compared, never printed)."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_skill_mismatch(result: ScanResult) -> list[ValidationIssue]:
    """Flag skills whose SKILL.md content differs between Claude and Codex."""
    issues: list[ValidationIssue] = []
    by_name: dict[str, dict[str, ScanItem]] = {}
    for item in result.items:
        if item.category == "skill" and item.tool in ("claude", "codex"):
            by_name.setdefault(item.name, {})[item.tool] = item
    for name, per_tool in sorted(by_name.items()):
        claude_item = per_tool.get("claude")
        codex_item = per_tool.get("codex")
        if claude_item is None or codex_item is None:
            continue
        if claude_item.path is None or codex_item.path is None:
            continue
        try:
            same = _file_sha256(claude_item.path) == _file_sha256(codex_item.path)
        except OSError:
            continue
        if not same:
            issues.append(
                ValidationIssue(
                    "scan",
                    f"skill '{name}' content differs between Claude ({claude_item.path}) and Codex ({codex_item.path})",
                    severity="warning",
                    path=str(claude_item.path),
                )
            )
    return issues


def _parse_date(value: str) -> date | None:
    """Parse a YYYY-MM-DD (or ISO datetime) string into a date, or None."""
    text = value.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt).date()
        except ValueError:
            continue
    return None


def _check_stale_skills(result: ScanResult, stale_threshold_days: int) -> list[ValidationIssue]:
    """Flag skills whose ``update_date`` is older than the threshold (info)."""
    issues: list[ValidationIssue] = []
    for item in result.items:
        if item.category != "skill" or not item.update_date:
            continue
        parsed = _parse_date(item.update_date)
        if parsed is None:
            continue
        age_days = (date.today() - parsed).days
        if age_days > stale_threshold_days:
            loc = str(item.path) if item.path else ""
            issues.append(
                ValidationIssue(
                    "scan",
                    f"skill '{item.name}' has not been updated since {item.update_date} "
                    f"({age_days} days ago; threshold is {stale_threshold_days} days)",
                    severity="info",
                    path=loc,
                )
            )
    return issues


# ── Serialization ───────────────────────────────────────────────────────


def scan_result_to_dict(result: ScanResult) -> dict:
    """Serialize a :class:`ScanResult` to a JSON-compatible dict (CI-ready).

    Uninstalled tools appear with a count of 0 so CI consumers can rely on
    a stable key set.  ``tools`` adds a per-tool ``installed`` flag and
    ``settings`` count so consumers can distinguish "not installed" from
    "installed with settings only" (e.g. ``~/.codex/config.toml``).
    """
    skills = result.by_category("skill")
    mcp = result.by_category("mcp")
    instructions = result.by_category("instruction")
    return {
        "agents": {tool: result.count(tool=tool, category="agent") for tool in TOOL_ORDER},
        "tools": {
            tool: {
                "installed": result.count(tool=tool) > 0,
                "settings": result.count(tool=tool, category="settings"),
            }
            for tool in TOOL_ORDER
        },
        "skills": {"total": len(skills), "items": [i.to_dict() for i in skills]},
        "mcp": {"total": len(mcp), "items": [i.to_dict() for i in mcp]},
        "instructions": {"total": len(instructions), "items": [i.to_dict() for i in instructions]},
        "problems": [
            {"component": p.component, "message": p.message, "severity": p.severity, "path": p.path}
            for p in result.problems
        ],
    }


# ── Import detected items (1-3, init hook) ──────────────────────────────


def _read_mcp_servers_from_file(path: Path) -> list:
    """Extract MCP server definitions from a config file.

    Handles both the standard ``mcpServers`` map (command + args) and the
    OpenCode ``mcp`` map (command as a list).  Returns
    :class:`~ai_adapter.models.MCPServer` objects.
    """
    from ai_adapter.models import MCPServer

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict):
        return []
    servers: list = []
    for key in _MCP_SERVER_KEYS:
        entries = data.get(key)
        if not isinstance(entries, dict):
            continue
        for name, definition in entries.items():
            if not isinstance(name, str) or not isinstance(definition, dict):
                continue
            if isinstance(definition.get("command"), list):
                command = definition["command"][0] if definition["command"] else ""
                args = [str(a) for a in definition["command"][1:]]
            else:
                command = definition.get("command", "")
                args = [str(a) for a in definition.get("args", [])] if isinstance(definition.get("args"), list) else []
            env = definition.get("env") or definition.get("environment") or {}
            env_keys = [str(k) for k in env.keys()] if isinstance(env, dict) else []
            servers.append(
                MCPServer(
                    name=name,
                    command=str(command),
                    args=args,
                    env_keys=env_keys,
                    enabled=definition.get("enabled", True),
                )
            )
    return servers


def import_detected_items(result: ScanResult) -> int:
    """Import detected items into ``~/.ai-adapter/`` and register them.

    Reuses the registration patterns from ``add-all-rec`` (agent / skill /
    instruction copy + config registration, MCP server extraction) so the
    imported store is identical in shape to a manually curated one.

    Returns the number of items imported.
    """
    from ai_adapter import config as _config

    _config.init()
    config = _config.load_config()
    if config is None:
        return 0

    imported = 0
    for item in result.items:
        if item.path is None or not item.path.exists():
            continue
        importers = {
            "agent": _import_agent,
            "skill": _import_skill,
            "instruction": _import_instruction,
            "mcp": _import_mcp,
        }
        importer = importers.get(item.category)
        if importer is not None and importer(config, item):
            imported += 1

    _config.save_config(config)
    return imported


def _import_agent(config: Config, item: ScanItem) -> bool:
    """Copy an agent file into the store and register it in config."""
    import shutil

    from ai_adapter import config as _config
    from ai_adapter.commands.agent import _get_agent_name_from_path
    from ai_adapter.models import Agent

    if item.path is None:
        return False
    agents_dir = _config.get_agents_dir()
    agents_dir.mkdir(parents=True, exist_ok=True)
    dest = agents_dir / item.path.name
    shutil.copy2(item.path, dest)
    name = _get_agent_name_from_path(item.path)
    config.agents = [a for a in config.agents if a.name != name]
    config.agents.append(Agent(name=name))
    return True


def _import_skill(config: Config, item: ScanItem) -> bool:
    """Copy a skill directory into the store and register it in config.

    The frontmatter ``name`` is used as the destination directory name, so
    it is validated with :func:`~ai_adapter.config.is_safe_store_name`
    before any copy or delete happens — a name such as ``../../evil`` must
    never escape the store or trigger an ``rmtree`` outside of it.
    """
    import shutil

    from ai_adapter import config as _config
    from ai_adapter.config import is_safe_store_name
    from ai_adapter.models import Skill

    if item.path is None or not is_safe_store_name(item.name):
        return False
    skills_dir = _config.get_skills_dir()
    skills_dir.mkdir(parents=True, exist_ok=True)
    dest = skills_dir / item.name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(item.path.parent, dest)
    config.skills = [s for s in config.skills if s.name != item.name]
    config.skills.append(
        Skill(
            name=item.name,
            description=item.description or "",
            path=f"skills/{item.name}",
            tags=item.tags,
        )
    )
    return True


def _import_instruction(config: Config, item: ScanItem) -> bool:
    """Copy an instruction file into the store and register it in config."""
    import shutil

    from ai_adapter import config as _config
    from ai_adapter.models import Instruction

    if item.path is None:
        return False
    instructions_dir = _config.get_instructions_dir()
    instructions_dir.mkdir(parents=True, exist_ok=True)
    dest = instructions_dir / item.path.name
    if not dest.exists():
        shutil.copy2(item.path, dest)
    name = item.path.stem
    config.instructions = [i for i in config.instructions if i.name != name]
    config.instructions.append(Instruction(name=name))
    return True


def _import_mcp(config: Config, item: ScanItem) -> bool:
    """Register a detected MCP server in config (no file copy needed)."""
    if item.path is None:
        return False
    if any(m.name == item.name for m in config.mcp_servers):
        return False
    matched = next((s for s in _read_mcp_servers_from_file(item.path) if s.name == item.name), None)
    if matched is None:
        return False
    config.mcp_servers.append(matched)
    return True
