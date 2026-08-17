"""search command implementation.

Cross-category search across all registered items in the ai-adapter
configuration.  Searches agents, skills, MCP servers, commands,
prompts, instructions, and bins by keyword.
"""

from __future__ import annotations

import json

import click

from ai_adapter.config import load_config
from ai_adapter.search import (
    CATEGORY_LABELS,
    CATEGORY_ORDER,
    SearchResult,
    search,
)


@click.command(name="search")
@click.argument("keyword", required=False, default="")
@click.option("--agent", "flag_agent", is_flag=True, help="Search only agents")
@click.option("--skill", "flag_skill", is_flag=True, help="Search only skills")
@click.option("--mcp", "flag_mcp", is_flag=True, help="Search only MCP servers")
@click.option("--command", "flag_command", is_flag=True, help="Search only commands")
@click.option("--prompt", "flag_prompt", is_flag=True, help="Search only prompts")
@click.option("--instruction", "flag_instruction", is_flag=True, help="Search only instructions")
@click.option("--bin", "flag_bin", is_flag=True, help="Search only bins")
@click.option("--tag", default=None, help="Filter by tag (skills only)")
@click.option("--env", "-e", default=None, help="Filter by environment name")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def cmd_search(
    keyword: str,
    flag_agent: bool,
    flag_skill: bool,
    flag_mcp: bool,
    flag_command: bool,
    flag_prompt: bool,
    flag_instruction: bool,
    flag_bin: bool,
    tag: str | None,
    env: str | None,
    as_json: bool,
) -> None:
    """Search registered items by keyword.

    Searches across all categories (agents, skills, MCP servers,
    commands, prompts, instructions, bins) by default.

    Use category flags (--agent, --skill, etc.) to restrict the search.
    Multiple flags can be combined.

    \b
    Examples:
      ai-adapter search review
      ai-adapter search review --agent
      ai-adapter search review --skill --tag seo
      ai-adapter search review --env prod
      ai-adapter search --json
    """
    config = load_config()
    if config is None:
        click.echo("Configuration file not found. Run ai-adapter init first.")
        return

    # Determine which categories to search
    categories = _resolve_categories(
        flag_agent=flag_agent,
        flag_skill=flag_skill,
        flag_mcp=flag_mcp,
        flag_command=flag_command,
        flag_prompt=flag_prompt,
        flag_instruction=flag_instruction,
        flag_bin=flag_bin,
    )

    # Run search
    result = search(
        keyword=keyword,
        categories=categories,
        tag=tag,
        env=env,
    )

    # Output
    if as_json:
        _output_json(result, keyword)
    else:
        _output_text(result, keyword, tag, env)


def _resolve_categories(
    *,
    flag_agent: bool,
    flag_skill: bool,
    flag_mcp: bool,
    flag_command: bool,
    flag_prompt: bool,
    flag_instruction: bool,
    flag_bin: bool,
) -> list[str] | None:
    """Return the list of categories to search, or None for all."""
    flags = {
        "agent": flag_agent,
        "skill": flag_skill,
        "mcp": flag_mcp,
        "command": flag_command,
        "prompt": flag_prompt,
        "instruction": flag_instruction,
        "bin": flag_bin,
    }
    selected = [cat for cat, enabled in flags.items() if enabled]
    return selected if selected else None


def _output_text(result: SearchResult, keyword: str, tag: str | None, env: str | None) -> None:
    """Print search results in human-readable format."""
    if result.total() == 0:
        if keyword:
            click.echo(f"No items found matching '{keyword}'.")
        else:
            click.echo("No items registered.")
        _print_hint(tag, env)
        return

    # Header
    if keyword:
        click.echo(f"Search results for '{keyword}':")
    else:
        click.echo("All registered items:")
    click.echo("-" * 60)

    # Group by category in display order
    for cat in CATEGORY_ORDER:
        hits = result.by_category(cat)
        if not hits:
            continue
        label = CATEGORY_LABELS.get(cat, cat)
        click.echo(f"\n  [{label}] ({len(hits)})")
        for h in hits:
            parts: list[str] = []
            if h.description:
                parts.append(h.description)
            if h.tags:
                parts.append(f"tags: {', '.join(h.tags)}")
            if h.env:
                parts.append(f"env: {h.env}")
            if h.extra.get("agent"):
                parts.append(f"agent: {h.extra['agent']}")
            detail = f"  —  {'; '.join(parts)}" if parts else ""
            click.echo(f"    {h.name}{detail}")

    # Summary
    click.echo()
    click.echo(f"  Total: {result.total()} item(s) across {len(result.categories())} category(ies)")


def _output_json(result: SearchResult, keyword: str) -> None:
    """Print search results as JSON."""
    data: dict = {
        "keyword": keyword,
        "total": result.total(),
        "categories": {},
    }
    for cat in CATEGORY_ORDER:
        hits = result.by_category(cat)
        if hits:
            data["categories"][cat] = {
                "count": len(hits),
                "items": [h.to_dict() for h in hits],
            }
    click.echo(json.dumps(data, indent=2, ensure_ascii=False))


def _print_hint(tag: str | None, env: str | None) -> None:
    """Print a helpful hint after no results."""
    hints: list[str] = []
    if tag:
        hints.append(f"No skill has the tag '{tag}'.")
    if env:
        hints.append(f"No items are bound to environment '{env}'.")
    if not hints:
        hints.append("Run 'ai-adapter status' to see registered items.")
    for h in hints:
        click.echo(f"Hint: {h}")
