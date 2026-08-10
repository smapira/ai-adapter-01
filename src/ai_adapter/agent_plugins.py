"""Agent Plugins 1.0.0 validation and generation.

Implements the normative requirements from the Agent Plugins 1.0.0
specification (https://agent-plugins.org/specification):

- ``plugin.json`` manifest validation (spec §5)
- ``mcp.json`` MCP server configuration validation (spec §7.2)
- Skills discovery (spec §6, §7.1)
- Placeholder / plugin name constraints (spec §4, §5.5)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# ── Canonical schema identifiers ──────────────────────────────────────────

PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
MCP_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"

# ── Allowed top-level fields in plugin.json (§5.2) ──────────────────────
PLUGIN_MANIFEST_FIELDS = frozenset(
    {
        "$schema",
        "name",
        "version",
        "description",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
        "extensions",
    }
)

AUTHOR_FIELDS = frozenset({"name", "email", "url"})

# ── plugin.json name constraints (§5.5) ──────────────────────────────────
_PLUGIN_NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
_PLUGIN_NAME_INVALID_CHARS = re.compile(r"[^a-z0-9.\-]")
_PLUGIN_NAME_DOUBLE_HYPHEN = re.compile(r"--")
_PLUGIN_NAME_DOUBLE_DOT = re.compile(r"\.\.")


@dataclass
class ValidationIssue:
    """A single validation finding."""

    component: str
    message: str
    severity: str = "error"  # "error" or "warning"
    path: str = ""

    def __str__(self) -> str:
        prefix = f"[{self.component}]" if self.component else ""
        loc = f" ({self.path})" if self.path else ""
        label = "ERROR" if self.severity == "error" else "WARN"
        return f"{label}: {prefix}{loc} {self.message}"


@dataclass
class ValidationResult:
    """Validation outcome for a plugin package."""

    valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)


# ── plugin.json validation (§5) ──────────────────────────────────────────


def validate_plugin_name(name: object) -> str | None:
    """Validate a plugin ``name`` value, returning an error message or None.

    Implements the constraints from spec §5.5.
    """
    if not isinstance(name, str):
        return f"name must be a string, got {type(name).__name__}"
    if not 1 <= len(name) <= 64:
        return f"name must be 1-64 characters (got {len(name)})"
    if _PLUGIN_NAME_INVALID_CHARS.search(name):
        return f"name must contain only lowercase alphanumeric, hyphens, and periods (got '{name}')"
    if _PLUGIN_NAME_DOUBLE_HYPHEN.search(name):
        return f"name must not contain consecutive hyphens (got '{name}')"
    if _PLUGIN_NAME_DOUBLE_DOT.search(name):
        return f"name must not contain consecutive periods (got '{name}')"
    if not _PLUGIN_NAME_RE.match(name):
        return f"name must start and end with an alphanumeric character (got '{name}')"
    return None


def _validate_author(author: object, issues: list[ValidationIssue], path: str) -> bool:
    """Validate the ``author`` object (spec §5.4). Returns True when valid."""
    if not isinstance(author, dict):
        issues.append(
            ValidationIssue("plugin.json", f"author must be an object, got {type(author).__name__}", path=path)
        )
        return False
    ok = True
    for key, val in author.items():
        if key not in AUTHOR_FIELDS:
            issues.append(
                ValidationIssue(
                    "plugin.json",
                    f"author contains unknown field '{key}' (allowed: {', '.join(sorted(AUTHOR_FIELDS))})",
                    path=f"{path}.{key}",
                )
            )
            ok = False
        elif not isinstance(val, str):
            issues.append(
                ValidationIssue(
                    "plugin.json",
                    f"author.{key} must be a string, got {type(val).__name__}",
                    path=f"{path}.{key}",
                )
            )
            ok = False
    return ok


def validate_plugin_manifest(data: object, path: str = "plugin.json") -> ValidationResult:
    """Validate a parsed ``plugin.json`` manifest (spec §5).

    Returns a result where ``valid`` is True only when the manifest
    satisfies all fatal requirements.  Non-fatal issues (unknown top-level
    fields, non-object ``extensions``) are reported as warnings and do not
    make the plugin invalid.
    """
    issues: list[ValidationIssue] = []
    valid = True

    if not isinstance(data, dict):
        issues.append(
            ValidationIssue(
                "plugin.json",
                f"manifest must be a JSON object, got {type(data).__name__}",
                path=path,
            )
        )
        return ValidationResult(valid=False, issues=issues)

    # Unknown top-level fields are reported then ignored (non-fatal, §5.2)
    for key in data:
        if key not in PLUGIN_MANIFEST_FIELDS:
            issues.append(
                ValidationIssue(
                    "plugin.json",
                    f"unknown top-level field '{key}' is ignored; client-specific data belongs under 'extensions'",
                    severity="warning",
                    path=f"{path}.{key}",
                )
            )

    # $schema (required, §5.2/§5.3)
    schema = data.get("$schema")
    if schema != PLUGIN_SCHEMA:
        issues.append(
            ValidationIssue(
                "plugin.json",
                f"$schema must be '{PLUGIN_SCHEMA}' (got {schema!r})",
                path=f"{path}.$schema",
            )
        )
        valid = False

    # name (required, §5.3)
    name = data.get("name")
    if name is None:
        issues.append(ValidationIssue("plugin.json", "missing required field 'name'", path=f"{path}.name"))
        valid = False
    else:
        name_err = validate_plugin_name(name)
        if name_err:
            issues.append(ValidationIssue("plugin.json", name_err, path=f"{path}.name"))
            valid = False

    # extensions must be an object if present (non-fatal, §8.1)
    if "extensions" in data and not isinstance(data["extensions"], dict):
        issues.append(
            ValidationIssue(
                "plugin.json",
                f"'extensions' must be an object, got {type(data['extensions']).__name__} (ignored)",
                severity="warning",
                path=f"{path}.extensions",
            )
        )

    # author object (metadata, §5.4)
    if "author" in data:
        author_ok = _validate_author(data["author"], issues, f"{path}.author")
        valid = valid and author_ok

    # Field type checks (fatal on violation, §5.2)
    for field_name, expected in (
        ("version", str),
        ("description", str),
        ("homepage", str),
        ("repository", str),
        ("license", str),
        ("keywords", list),
    ):
        if field_name not in data:
            continue
        val = data[field_name]
        if not isinstance(val, expected):
            issues.append(
                ValidationIssue(
                    "plugin.json",
                    f"'{field_name}' must be {expected.__name__}, got {type(val).__name__}",
                    path=f"{path}.{field_name}",
                )
            )
            valid = False
        elif field_name == "keywords" and not all(isinstance(k, str) for k in val):
            issues.append(ValidationIssue("plugin.json", "keywords items must be strings", path=f"{path}.keywords"))
            valid = False

    return ValidationResult(valid=valid, issues=issues)


# ── mcp.json validation (§7.2) ───────────────────────────────────────────

# First components of an IPv4 loopback address (127.0.0.0/8).
_LOOPBACK_PREFIXES = ("127.", "0.")

# Servers allowed to be non-loopback without HTTPS (rare; not used here).
_MCP_SERVER_TYPES = ("stdio", "streamable-http", "sse")


def _is_loopback_url(url: str) -> bool:
    """Return True when ``url`` targets localhost (hostname or 127.0.0.0/8)."""
    lowered = url.lower()
    if lowered.startswith("https://127.") or lowered.startswith("http://127."):
        rest = lowered.split("://", 1)[1]
        host = rest.split("/", 1)[0].split(":", 1)[0]
        return host.startswith(_LOOPBACK_PREFIXES)
    if "://localhost" in lowered or lowered.startswith("localhost:"):
        return True
    # http://localhost/... and https://localhost/... forms
    for scheme in ("http://", "https://"):
        if lowered.startswith(scheme):
            rest = lowered[len(scheme) :]
            host = rest.split("/", 1)[0].split(":", 1)[0]
            if host in ("localhost", "127.0.0.1"):
                return True
    return False


def validate_mcp_url(url: object, issues: list[ValidationIssue], path: str) -> None:
    """Validate a streamable-http / sse ``url`` (spec §7.2)."""
    if not isinstance(url, str):
        issues.append(ValidationIssue("mcp.json", f"url must be a string, got {type(url).__name__}", path=path))
        return
    if "://" not in url:
        issues.append(ValidationIssue("mcp.json", f"url must be an absolute URL (got '{url}')", path=path))
        return
    scheme = url.split("://", 1)[0].lower()
    if scheme not in ("http", "https"):
        issues.append(ValidationIssue("mcp.json", f"url scheme must be http or https (got '{scheme}')", path=path))
        return
    # userinfo / fragment are not allowed
    if "@" in url.split("://", 1)[1].split("/", 1)[0]:
        issues.append(ValidationIssue("mcp.json", f"url must not contain userinfo (got '{url}')", path=path))
    if "#" in url:
        issues.append(ValidationIssue("mcp.json", f"url must not contain a fragment (got '{url}')", path=path))
    # non-loopback must be HTTPS
    if scheme == "http" and not _is_loopback_url(url):
        issues.append(
            ValidationIssue(
                "mcp.json",
                f"non-loopback url must use https (got '{url}')",
                path=path,
            )
        )


def _validate_headers(headers: object, issues: list[ValidationIssue], path: str) -> None:
    """Validate ``headers`` (must be a string->string map, §7.2)."""
    if not isinstance(headers, dict):
        issues.append(
            ValidationIssue("mcp.json", f"headers must be an object, got {type(headers).__name__}", path=path)
        )
        return
    keys_seen: set[str] = set()
    for key, val in headers.items():
        if not isinstance(key, str) or not isinstance(val, str):
            issues.append(ValidationIssue("mcp.json", "headers keys and values must be strings", path=f"{path}.{key}"))
            continue
        lowered = key.lower()
        if lowered in keys_seen:
            issues.append(
                ValidationIssue(
                    "mcp.json",
                    f"duplicate header '{key}' (case-insensitive) is not allowed",
                    path=f"{path}.{key}",
                )
            )
        keys_seen.add(lowered)
        # Reserved placeholders are not allowed in header values
        if "${" in val:
            issues.append(
                ValidationIssue(
                    "mcp.json",
                    f"header value must not contain placeholders like '${{...}}' (got '{val}')",
                    path=f"{path}.{key}",
                )
            )


def _validate_cwd(cwd: object, issues: list[ValidationIssue], path: str) -> None:
    """Validate ``cwd`` (must reference ${PLUGIN_ROOT}, §7.2)."""
    if not isinstance(cwd, str):
        issues.append(ValidationIssue("mcp.json", f"cwd must be a string, got {type(cwd).__name__}", path=path))
    elif "${PLUGIN_ROOT}" not in cwd:
        issues.append(
            ValidationIssue(
                "mcp.json",
                "cwd must reference ${PLUGIN_ROOT} (absolute paths are not allowed)",
                path=path,
            )
        )


def _validate_command(command: object, issues: list[ValidationIssue], path: str) -> None:
    """Validate ``command`` for stdio servers (spec §7.2)."""
    if not isinstance(command, str):
        issues.append(ValidationIssue("mcp.json", f"command must be a string, got {type(command).__name__}", path=path))
        return
    if " " in command:
        issues.append(
            ValidationIssue(
                "mcp.json",
                f"command must be a single token, got '{command}' (move options to 'args')",
                path=path,
            )
        )
    if "${" in command:
        issues.append(
            ValidationIssue(
                "mcp.json",
                f"command must not contain placeholders like '${{...}}' (got '{command}')",
                path=path,
            )
        )


def _validate_env(env: object, issues: list[ValidationIssue], path: str) -> None:
    """Validate ``env`` (spec §7.2 placeholders and reserved keys)."""
    if not isinstance(env, dict):
        issues.append(ValidationIssue("mcp.json", f"env must be an object, got {type(env).__name__}", path=path))
        return
    for key, val in env.items():
        if not isinstance(key, str) or not isinstance(val, str):
            issues.append(ValidationIssue("mcp.json", "env keys and values must be strings", path=f"{path}.{key}"))
            continue
        if key in ("PLUGIN_ROOT", "PLUGIN_DATA"):
            issues.append(
                ValidationIssue(
                    "mcp.json",
                    f"env key '{key}' is reserved by the client and must not be set",
                    path=f"{path}.{key}",
                )
            )


def validate_mcp_server(name: str, server: object, issues: list[ValidationIssue]) -> bool:
    """Validate a single entry in ``mcpServers`` (spec §7.2). Returns True when valid."""
    if not isinstance(server, dict):
        issues.append(ValidationIssue("mcp.json", f"server '{name}' must be an object, got {type(server).__name__}"))
        return False

    mcp_type = server.get("type")
    if not isinstance(mcp_type, str):
        issues.append(ValidationIssue("mcp.json", f"server '{name}' is missing required 'type'"))
        return False
    if mcp_type not in _MCP_SERVER_TYPES:
        issues.append(
            ValidationIssue(
                "mcp.json",
                f"server '{name}' has unknown type '{mcp_type}' (allowed: {', '.join(_MCP_SERVER_TYPES)})",
            )
        )
        return False

    ok = True
    if mcp_type == "stdio":
        before = len(issues)
        _validate_command(server.get("command"), issues, f"mcpJson.servers.{name}.command")
        env = server.get("env")
        if env is not None:
            if isinstance(env, dict):
                _validate_env(env, issues, f"mcpJson.servers.{name}.env")
            else:
                issues.append(
                    ValidationIssue(
                        "mcp.json", f"server '{name}' env must be an object", path=f"mcpJson.servers.{name}"
                    )
                )
                ok = False
        args = server.get("args")
        if args is not None and not isinstance(args, list):
            issues.append(
                ValidationIssue("mcp.json", f"server '{name}' args must be a list", path=f"mcpJson.servers.{name}")
            )
            ok = False
        cwd = server.get("cwd")
        if cwd is not None:
            _validate_cwd(cwd, issues, f"mcpJson.servers.{name}.cwd")
        if len(issues) > before:
            ok = False
    else:
        before = len(issues)
        validate_mcp_url(server.get("url"), issues, f"mcpJson.servers.{name}.url")
        headers = server.get("headers")
        if headers is not None:
            _validate_headers(headers, issues, f"mcpJson.servers.{name}.headers")
        if len(issues) > before:
            ok = False
    return ok


def validate_mcp_config(data: object, path: str = "mcp.json") -> ValidationResult:
    """Validate a parsed ``mcp.json`` (spec §7.2).

    The top-level schema (``$schema`` + ``mcpServers``) is closed: unknown
    servers are reported and skipped, unknown server types are reported and
    skipped, but other fields are allowed to be client hints.
    """
    issues: list[ValidationIssue] = []
    valid = True

    if not isinstance(data, dict):
        issues.append(ValidationIssue("mcp.json", f"mcp.json must be a JSON object, got {type(data).__name__}"))
        return ValidationResult(valid=False, issues=issues)

    schema = data.get("$schema")
    if schema != MCP_SCHEMA:
        issues.append(
            ValidationIssue("mcp.json", f"$schema must be '{MCP_SCHEMA}' (got {schema!r})", path="mcpJson.$schema")
        )
        valid = False

    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        issues.append(
            ValidationIssue(
                "mcp.json",
                "missing required 'mcpServers' object",
                path="mcpJson.mcpServers",
            )
        )
        return ValidationResult(valid=False, issues=issues)

    for name, server in servers.items():
        if not isinstance(name, str):
            issues.append(ValidationIssue("mcp.json", f"mcpServers keys must be strings, got {type(name).__name__}"))
            continue
        server_ok = validate_mcp_server(name, server, issues)
        valid = valid and server_ok

    return ValidationResult(valid=valid, issues=issues)


# ── Skills discovery & validation (§6, §7.1) ─────────────────────────────


def discover_skills(plugin_root: Path) -> list[Path]:
    """Return paths to candidate skill directories under ``skills/``.

    Only direct children of ``skills/`` are considered (spec §7.1); nesting
    deeper than one level is not part of the 1.0.0 package format.
    """
    skills_dir = plugin_root / "skills"
    if not skills_dir.is_dir():
        return []
    return sorted(p for p in skills_dir.iterdir() if p.is_dir() and not p.name.startswith("."))


def validate_skill_dir(skill_dir: Path, issues: list[ValidationIssue]) -> None:
    """Validate a single skill directory (best-effort per Agent Skills spec).

    Requires a ``SKILL.md`` whose frontmatter contains ``name`` and
    ``description``.  Additional files (scripts/, references/, images/)
    are allowed and not checked for content.
    """
    name = skill_dir.name
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        issues.append(
            ValidationIssue(
                "skills",
                f"skill '{name}' is missing SKILL.md",
                path=str(skill_dir),
            )
        )
        return

    try:
        raw = skill_md.read_text(encoding="utf-8")
    except OSError as exc:
        issues.append(
            ValidationIssue(
                "skills",
                f"skill '{name}' SKILL.md could not be read: {exc}",
                path=str(skill_md),
            )
        )
        return

    if not raw.lstrip().startswith("---"):
        issues.append(
            ValidationIssue(
                "skills",
                f"skill '{name}' SKILL.md must start with '---' frontmatter",
                path=str(skill_md),
            )
        )
        return

    fm_end = raw.find("\n---", raw.find("---") + 3)
    if fm_end == -1:
        issues.append(
            ValidationIssue(
                "skills",
                f"skill '{name}' SKILL.md has unterminated frontmatter",
                path=str(skill_md),
            )
        )
        return

    fm_text = raw[raw.find("---") + 3 : fm_end]
    try:
        fm = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError as exc:
        issues.append(
            ValidationIssue(
                "skills",
                f"skill '{name}' frontmatter is not valid YAML: {exc}",
                path=str(skill_md),
            )
        )
        return

    if not isinstance(fm, dict):
        issues.append(
            ValidationIssue(
                "skills",
                f"skill '{name}' frontmatter must be a mapping",
                path=str(skill_md),
            )
        )
        return

    if not fm.get("name"):
        issues.append(
            ValidationIssue(
                "skills",
                f"skill '{name}' frontmatter is missing required 'name'",
                path=str(skill_md),
            )
        )
    if not fm.get("description"):
        issues.append(
            ValidationIssue(
                "skills",
                f"skill '{name}' frontmatter is missing required 'description'",
                path=str(skill_md),
            )
        )


# ── Package-level validation (§8) ────────────────────────────────────────


def validate_plugin_package(plugin_root: Path) -> ValidationResult:
    """Validate an entire Agent Plugins package directory.

    Checks (in order):

    1. ``plugin.json`` manifest (spec §5) — fatal on violation.
    2. ``mcp.json`` if present (spec §7.2) — fatal on violation.
    3. Skills under ``skills/`` (spec §6) — warnings only.
    4. Package completeness — plugin.json is required.
    """
    issues: list[ValidationIssue] = []
    valid = True

    plugin_json = plugin_root / "plugin.json"
    if not plugin_json.is_file():
        issues.append(ValidationIssue("package", "missing required plugin.json", path=str(plugin_root)))
        return ValidationResult(valid=False, issues=issues)

    try:
        manifest = _load_json(plugin_json)
    except ValueError as exc:
        issues.append(ValidationIssue("package", f"plugin.json is not valid JSON: {exc}", path=str(plugin_json)))
        return ValidationResult(valid=False, issues=issues)

    manifest_result = validate_plugin_manifest(manifest, path=str(plugin_json))
    issues.extend(manifest_result.issues)
    valid = valid and manifest_result.valid

    mcp_json = plugin_root / "mcp.json"
    if mcp_json.is_file():
        try:
            mcp_data = _load_json(mcp_json)
        except ValueError as exc:
            issues.append(ValidationIssue("package", f"mcp.json is not valid JSON: {exc}", path=str(mcp_json)))
            valid = False
        else:
            mcp_result = validate_mcp_config(mcp_data, path=str(mcp_json))
            issues.extend(mcp_result.issues)
            valid = valid and mcp_result.valid
    else:
        issues.append(
            ValidationIssue(
                "package",
                "mcp.json is optional in 1.0.0 but recommended; omit only when the plugin has no MCP servers",
                severity="warning",
                path=str(plugin_root),
            )
        )

    for skill_dir in discover_skills(plugin_root):
        validate_skill_dir(skill_dir, issues)

    return ValidationResult(valid=valid, issues=issues)


def _load_json(path: Path) -> object:
    """Load a JSON document, raising ValueError on parse failure."""
    import json

    with path.open(encoding="utf-8") as fh:
        return json.load(fh)
