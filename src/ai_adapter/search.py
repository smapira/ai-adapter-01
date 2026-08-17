"""Search module.

Provides cross-category search across all registered items in the
ai-adapter configuration.  Searches agents, skills, MCP servers,
commands, prompts, instructions, and bins by keyword against
name/description/tags fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ai_adapter.config import load_config
from ai_adapter.models import Config

# ── Data structures ─────────────────────────────────────────────────────


@dataclass
class SearchHit:
    """A single search result."""

    category: str  # "agent" | "skill" | "mcp" | "command" | "prompt" | "instruction" | "bin"
    name: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    env: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"category": self.category, "name": self.name}
        if self.description:
            d["description"] = self.description
        if self.tags:
            d["tags"] = self.tags
        if self.env:
            d["env"] = self.env
        if self.extra:
            d.update(self.extra)
        return d


@dataclass
class SearchResult:
    """Aggregated search results grouped by category."""

    hits: list[SearchHit] = field(default_factory=list)

    def by_category(self, category: str) -> list[SearchHit]:
        """Return hits in the given category (sorted by name)."""
        return sorted(
            (h for h in self.hits if h.category == category),
            key=lambda h: h.name,
        )

    def categories(self) -> list[str]:
        """Return distinct categories present in results (in display order)."""
        seen: set[str] = set()
        result: list[str] = []
        for h in self.hits:
            if h.category not in seen:
                seen.add(h.category)
                result.append(h.category)
        return result

    def total(self) -> int:
        return len(self.hits)


# ── Category labels ─────────────────────────────────────────────────────

CATEGORY_LABELS: dict[str, str] = {
    "agent": "Agents",
    "skill": "Skills",
    "mcp": "MCP Servers",
    "command": "Commands",
    "prompt": "Prompts",
    "instruction": "Instructions",
    "bin": "Bins",
}

# Default display order
CATEGORY_ORDER: list[str] = [
    "agent",
    "skill",
    "mcp",
    "command",
    "prompt",
    "instruction",
    "bin",
]

# All valid category names (used for option validation)
ALL_CATEGORIES: frozenset[str] = frozenset(CATEGORY_ORDER)

# Map from CLI flag name to category name
FLAG_TO_CATEGORY: dict[str, str] = {
    "agent": "agent",
    "skill": "skill",
    "mcp": "mcp",
    "command": "command",
    "prompt": "prompt",
    "instruction": "instruction",
    "bin": "bin",
}


# ── Matching logic ──────────────────────────────────────────────────────


def _matches_keyword(text: str, keyword: str) -> bool:
    """Return True when *keyword* is found case-insensitively in *text*."""
    return keyword.lower() in text.lower()


def _matches_tag(tags: list[str], tag: str) -> bool:
    """Return True when *tag* is found case-insensitively in *tags*."""
    return tag.lower() in {t.lower() for t in tags}


def _matches_env(item_env: str | None, env: str | None) -> bool:
    """Return True when the item's env matches the filter.

    Items with env=None (unbound) always match.
    """
    if env is None:
        return True
    return item_env is None or item_env == env


# ── Search functions ────────────────────────────────────────────────────


def search(
    keyword: str = "",
    categories: list[str] | None = None,
    tag: str | None = None,
    env: str | None = None,
) -> SearchResult:
    """Search registered items across all (or selected) categories.

    Args:
        keyword: Search term.  Empty string matches everything.
        categories: Restrict to these category names.  ``None`` means all.
        tag: Optional tag filter (case-insensitive).
        env: Optional environment filter.

    Returns:
        :class:`SearchResult` with all matching hits.
    """
    config = load_config()
    if config is None:
        return SearchResult()

    target_categories = categories or list(CATEGORY_ORDER)
    hits: list[SearchHit] = []

    for cat in target_categories:
        collector = _COLLECTORS.get(cat)
        if collector is None:
            continue
        hits.extend(collector(config, keyword, tag, env))

    return SearchResult(hits=hits)


# ── Per-category collectors ─────────────────────────────────────────────


def _collect_agents(
    config: Config,
    keyword: str,
    tag: str | None,
    env: str | None,
) -> list[SearchHit]:
    hits: list[SearchHit] = []
    for a in config.agents:
        if not _matches_env(None, env):
            continue
        # Resolve agent's env from bindings
        agent_env = None
        for b in config.agent_bindings:
            if b.agent == a.name:
                agent_env = b.env
                break
        if not _matches_env(agent_env, env):
            continue
        if keyword and not (_matches_keyword(a.name, keyword) or _matches_keyword(a.description, keyword)):
            continue
        hits.append(
            SearchHit(
                category="agent",
                name=a.name,
                description=a.description,
                env=agent_env,
            )
        )
    return hits


def _collect_skills(
    config: Config,
    keyword: str,
    tag: str | None,
    env: str | None,
) -> list[SearchHit]:
    hits: list[SearchHit] = []
    for s in config.skills:
        if not _matches_env(s.env, env):
            continue
        if tag and not _matches_tag(s.tags, tag):
            continue
        if keyword and not (
            _matches_keyword(s.name, keyword)
            or _matches_keyword(s.description, keyword)
            or any(_matches_keyword(t, keyword) for t in s.tags)
        ):
            continue
        hits.append(
            SearchHit(
                category="skill",
                name=s.name,
                description=s.description,
                tags=s.tags,
                env=s.env,
                extra={"agent": s.agent} if s.agent else {},
            )
        )
    return hits


def _collect_mcp(
    config: Config,
    keyword: str,
    tag: str | None,
    env: str | None,
) -> list[SearchHit]:
    hits: list[SearchHit] = []
    for m in config.mcp_servers:
        if not _matches_env(m.env, env):
            continue
        if keyword and not (_matches_keyword(m.name, keyword) or _matches_keyword(m.command, keyword)):
            continue
        hits.append(
            SearchHit(
                category="mcp",
                name=m.name,
                description=m.command,
                env=m.env,
                extra={
                    "args": m.args,
                    "enabled": m.enabled,
                },
            )
        )
    return hits


def _collect_commands(
    config: Config,
    keyword: str,
    tag: str | None,
    env: str | None,
) -> list[SearchHit]:
    hits: list[SearchHit] = []
    for c in config.commands:
        if not _matches_env(c.env, env):
            continue
        if keyword and not (
            _matches_keyword(c.name, keyword)
            or _matches_keyword(c.description, keyword)
            or _matches_keyword(c.content, keyword)
        ):
            continue
        hits.append(
            SearchHit(
                category="command",
                name=c.name,
                description=c.description,
                env=c.env,
            )
        )
    return hits


def _collect_prompts(
    config: Config,
    keyword: str,
    tag: str | None,
    env: str | None,
) -> list[SearchHit]:
    hits: list[SearchHit] = []
    for p in config.prompts:
        if not _matches_env(p.env, env):
            continue
        if keyword and not (
            _matches_keyword(p.name, keyword)
            or _matches_keyword(p.description, keyword)
            or _matches_keyword(p.content, keyword)
        ):
            continue
        hits.append(
            SearchHit(
                category="prompt",
                name=p.name,
                description=p.description,
                env=p.env,
            )
        )
    return hits


def _collect_instructions(
    config: Config,
    keyword: str,
    tag: str | None,
    env: str | None,
) -> list[SearchHit]:
    hits: list[SearchHit] = []
    for i in config.instructions:
        if not _matches_env(i.env, env):
            continue
        if keyword and not (
            _matches_keyword(i.name, keyword)
            or _matches_keyword(i.description, keyword)
            or _matches_keyword(i.content, keyword)
        ):
            continue
        hits.append(
            SearchHit(
                category="instruction",
                name=i.name,
                description=i.description,
                env=i.env,
            )
        )
    return hits


def _collect_bins(
    config: Config,
    keyword: str,
    tag: str | None,
    env: str | None,
) -> list[SearchHit]:
    hits: list[SearchHit] = []
    for b in config.bins:
        if not _matches_env(b.env, env):
            continue
        if keyword and not (_matches_keyword(b.name, keyword) or _matches_keyword(b.description, keyword)):
            continue
        hits.append(
            SearchHit(
                category="bin",
                name=b.name,
                description=b.description,
                env=b.env,
            )
        )
    return hits


_COLLECTORS: dict[str, Any] = {
    "agent": _collect_agents,
    "skill": _collect_skills,
    "mcp": _collect_mcp,
    "command": _collect_commands,
    "prompt": _collect_prompts,
    "instruction": _collect_instructions,
    "bin": _collect_bins,
}
