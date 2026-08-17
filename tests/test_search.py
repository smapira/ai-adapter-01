"""Tests for the search command and search module."""

import json
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from ai_adapter.cli import main
from ai_adapter.models import (
    Agent,
    AgentBinding,
    Bin,
    Command,
    Config,
    Instruction,
    MCPServer,
    Prompt,
    Skill,
)
from ai_adapter.search import (
    SearchHit,
    SearchResult,
    _matches_env,
    _matches_keyword,
    _matches_tag,
    search,
)


def _init_config(config_obj: Config) -> None:
    """Save a config to the test environment."""
    from ai_adapter import config as cfg

    cfg.save_config(config_obj)


def _make_populated_config() -> Config:
    """Create a Config populated with test data."""
    return Config(
        version=1,
        default_env="default",
        agents=[
            Agent(name="reviewer", description="Code review agent"),
            Agent(name="implementer", description="Implementation agent"),
            Agent(name="secretary", description="Secretary agent"),
        ],
        agent_bindings=[
            AgentBinding(agent="reviewer", env="production"),
            AgentBinding(agent="secretary", env="default"),
        ],
        bins=[
            Bin(name="build.sh", description="Build script"),
            Bin(name="deploy.sh", description="Deploy script"),
        ],
        skills=[
            Skill(
                name="seo-analysis",
                description="SEO data analysis skill",
                path="skills/seo-analysis",
                tags=["seo", "analytics"],
                agent="reviewer",
            ),
            Skill(
                name="web-writing",
                description="Web article writing skill",
                path="skills/web-writing",
                tags=["writing", "seo"],
            ),
            Skill(
                name="db-check",
                description="Database check skill",
                path="skills/db-check",
                tags=["database"],
                env="production",
            ),
        ],
        commands=[
            Command(name="hello", description="Say hello", content="Hello!"),
            Command(name="review-code", description="Review code", content="Review this"),
        ],
        prompts=[
            Prompt(name="code-review", description="Review this code"),
            Prompt(name="summarize", description="Summarize content"),
        ],
        instructions=[
            Instruction(name="coding-style", description="Coding style guide"),
        ],
        mcp_servers=[
            MCPServer(
                name="github-mcp",
                command="npx",
                args=["@github/mcp"],
                enabled=True,
                env="production",
            ),
            MCPServer(
                name="db-mcp",
                command="npx",
                args=["@db/mcp"],
                enabled=False,
            ),
        ],
    )


class TestSearchMatchesKeyword(unittest.TestCase):
    """Unit tests for keyword matching."""

    def test_exact_match(self):
        self.assertTrue(_matches_keyword("hello world", "hello"))

    def test_case_insensitive(self):
        self.assertTrue(_matches_keyword("Hello World", "hello"))

    def test_partial_match(self):
        self.assertTrue(_matches_keyword("seo-analysis", "seo"))

    def test_no_match(self):
        self.assertFalse(_matches_keyword("hello world", "xyz"))

    def test_empty_keyword_matches_everything(self):
        self.assertTrue(_matches_keyword("hello", ""))


class TestSearchMatchesTag(unittest.TestCase):
    """Unit tests for tag matching."""

    def test_exact_match(self):
        self.assertTrue(_matches_tag(["seo", "analytics"], "seo"))

    def test_case_insensitive(self):
        self.assertTrue(_matches_tag(["SEO", "Analytics"], "seo"))

    def test_no_match(self):
        self.assertFalse(_matches_tag(["seo", "analytics"], "writing"))


class TestSearchMatchesEnv(unittest.TestCase):
    """Unit tests for env matching."""

    def test_none_filter_matches_all(self):
        self.assertTrue(_matches_env("production", None))
        self.assertTrue(_matches_env(None, None))

    def test_exact_match(self):
        self.assertTrue(_matches_env("production", "production"))

    def test_unbound_matches_any(self):
        self.assertTrue(_matches_env(None, "production"))

    def test_no_match(self):
        self.assertFalse(_matches_env("production", "staging"))


class TestSearchFunction(unittest.TestCase):
    """Tests for the search() function."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patch_home = Path(self.temp_dir.name)

        import pathlib

        self._original_home = pathlib.Path.home
        pathlib.Path.home = staticmethod(lambda: self.patch_home)

        from ai_adapter import config as cfg

        cfg.AI_ADAPTER_DIR = self.patch_home / ".ai-adapter"
        cfg.AI_ADAPTER_DIR.mkdir(parents=True, exist_ok=True)

        config = _make_populated_config()
        _init_config(config)

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        from ai_adapter import config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_search_all_items(self):
        """Empty keyword returns all items."""
        result = search()
        self.assertGreater(result.total(), 0)
        # Should have items from multiple categories
        self.assertIn("agent", result.categories())
        self.assertIn("skill", result.categories())

    def test_search_keyword_match(self):
        """Keyword matches items across categories."""
        result = search(keyword="review")
        # Should match: reviewer (agent), code-review (prompt), review-code (command)
        self.assertGreater(result.total(), 0)
        names = [h.name for h in result.hits]
        self.assertIn("reviewer", names)
        self.assertIn("code-review", names)
        self.assertIn("review-code", names)

    def test_search_keyword_match_description(self):
        """Keyword matches against descriptions."""
        result = search(keyword="deploy")
        names = [h.name for h in result.hits]
        self.assertIn("deploy.sh", names)

    def test_search_keyword_match_tags(self):
        """Keyword matches against skill tags."""
        result = search(keyword="analytics")
        names = [h.name for h in result.hits]
        self.assertIn("seo-analysis", names)

    def test_search_no_match(self):
        """Non-matching keyword returns empty result."""
        result = search(keyword="nonexistent_xyz_123")
        self.assertEqual(result.total(), 0)

    def test_search_category_filter(self):
        """Category filter restricts results."""
        result = search(keyword="review", categories=["agent"])
        names = [h.name for h in result.hits]
        self.assertIn("reviewer", names)
        # Should not include skills/commands
        self.assertNotIn("code-review", names)

    def test_search_multiple_categories(self):
        """Multiple category filters combine."""
        result = search(keyword="review", categories=["agent", "skill"])
        names = [h.name for h in result.hits]
        self.assertIn("reviewer", names)
        self.assertNotIn("review-code", names)  # command not included

    def test_search_tag_filter(self):
        """Tag filter restricts to matching skills."""
        result = search(tag="seo")
        names = [h.name for h in result.hits]
        self.assertIn("seo-analysis", names)
        self.assertIn("web-writing", names)
        self.assertNotIn("db-check", names)

    def test_search_env_filter(self):
        """Env filter restricts to matching items."""
        result = search(env="production")
        names = [h.name for h in result.hits]
        self.assertIn("reviewer", names)  # bound to production
        self.assertIn("github-mcp", names)  # env=production
        self.assertIn("db-check", names)  # env=production
        self.assertNotIn("secretary", names)  # bound to default

    def test_search_result_by_category(self):
        """SearchResult.by_category returns sorted hits."""
        result = search()
        agents = result.by_category("agent")
        self.assertEqual(len(agents), 3)
        # Should be sorted by name
        self.assertEqual(agents[0].name, "implementer")
        self.assertEqual(agents[1].name, "reviewer")
        self.assertEqual(agents[2].name, "secretary")

    def test_search_result_categories(self):
        """SearchResult.categories returns distinct categories in order."""
        result = search()
        cats = result.categories()
        self.assertIn("agent", cats)
        self.assertIn("skill", cats)
        # No duplicates
        self.assertEqual(len(cats), len(set(cats)))


class TestSearchCLI(unittest.TestCase):
    """CLI integration tests for the search command."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patch_home = Path(self.temp_dir.name)
        self.runner = CliRunner()

        import pathlib

        self._original_home = pathlib.Path.home
        pathlib.Path.home = staticmethod(lambda: self.patch_home)

        from ai_adapter import config as cfg

        cfg.AI_ADAPTER_DIR = self.patch_home / ".ai-adapter"
        cfg.AI_ADAPTER_DIR.mkdir(parents=True, exist_ok=True)

        config = _make_populated_config()
        _init_config(config)

    def tearDown(self):
        import pathlib

        pathlib.Path.home = staticmethod(self._original_home)
        from ai_adapter import config as cfg

        cfg.AI_ADAPTER_DIR = Path.home() / ".ai-adapter"
        self.temp_dir.cleanup()

    def test_search_help(self):
        """Verify --help displays correctly."""
        result = self.runner.invoke(main, ["search", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Search registered items", result.output)
        self.assertIn("--agent", result.output)
        self.assertIn("--skill", result.output)
        self.assertIn("--mcp", result.output)
        self.assertIn("--json", result.output)

    def test_search_all_items(self):
        """Search without keyword lists all items."""
        result = self.runner.invoke(main, ["search"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("All registered items", result.output)
        self.assertIn("[Agents]", result.output)
        self.assertIn("[Skills]", result.output)
        self.assertIn("Total:", result.output)

    def test_search_keyword(self):
        """Search with keyword matches items."""
        result = self.runner.invoke(main, ["search", "review"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Search results for 'review'", result.output)
        self.assertIn("reviewer", result.output)

    def test_search_agent_flag(self):
        """--agent flag restricts to agents."""
        result = self.runner.invoke(main, ["search", "review", "--agent"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("reviewer", result.output)
        # Commands/prompts should not appear
        self.assertNotIn("[Commands]", result.output)

    def test_search_skill_flag(self):
        """--skill flag restricts to skills."""
        result = self.runner.invoke(main, ["search", "seo", "--skill"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("seo-analysis", result.output)

    def test_search_mcp_flag(self):
        """--mcp flag restricts to MCP servers."""
        result = self.runner.invoke(main, ["search", "github", "--mcp"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("github-mcp", result.output)

    def test_search_tag_filter(self):
        """--tag flag filters by tag."""
        result = self.runner.invoke(main, ["search", "", "--tag", "seo"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("seo-analysis", result.output)
        self.assertIn("web-writing", result.output)

    def test_search_env_filter(self):
        """--env flag filters by environment."""
        result = self.runner.invoke(main, ["search", "", "--env", "production"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("reviewer", result.output)
        self.assertIn("github-mcp", result.output)

    def test_search_json_output(self):
        """--json flag produces JSON output."""
        result = self.runner.invoke(main, ["search", "review", "--json"])
        self.assertEqual(result.exit_code, 0)
        data = json.loads(result.output)
        self.assertEqual(data["keyword"], "review")
        self.assertGreater(data["total"], 0)
        self.assertIn("categories", data)

    def test_search_no_results(self):
        """No results shows helpful message."""
        result = self.runner.invoke(main, ["search", "nonexistent_xyz_123"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No items found", result.output)

    def test_search_before_init(self):
        """Search before init shows appropriate message."""
        from ai_adapter import config as cfg

        cfg.AI_ADAPTER_DIR = self.patch_home / ".ai-adapter-empty"
        cfg.AI_ADAPTER_DIR.mkdir(parents=True, exist_ok=True)

        result = self.runner.invoke(main, ["search", "hello"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("not found", result.output)

        # Restore
        cfg.AI_ADAPTER_DIR = self.patch_home / ".ai-adapter"

    def test_search_multiple_flags(self):
        """Multiple category flags combine (OR)."""
        result = self.runner.invoke(main, ["search", "review", "--agent", "--skill"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("reviewer", result.output)
        # Should NOT include commands (review-code)
        self.assertNotIn("[Commands]", result.output)

    def test_search_combined_tag_and_env(self):
        """--tag and --env can be combined."""
        result = self.runner.invoke(main, ["search", "", "--tag", "seo", "--env", "default"])
        self.assertEqual(result.exit_code, 0)
        # seo-analysis (tag=seo, env=None) and web-writing (tag=seo, env=None) should match
        self.assertIn("seo-analysis", result.output)
        self.assertIn("web-writing", result.output)
        # db-check (env=production) should not match
        self.assertNotIn("db-check", result.output)


class TestSearchHit(unittest.TestCase):
    """Tests for SearchHit data class."""

    def test_to_dict_basic(self):
        hit = SearchHit(category="agent", name="reviewer", description="Code review")
        d = hit.to_dict()
        self.assertEqual(d["category"], "agent")
        self.assertEqual(d["name"], "reviewer")
        self.assertEqual(d["description"], "Code review")
        self.assertNotIn("tags", d)
        self.assertNotIn("env", d)

    def test_to_dict_with_tags(self):
        hit = SearchHit(category="skill", name="seo", tags=["seo", "web"])
        d = hit.to_dict()
        self.assertEqual(d["tags"], ["seo", "web"])

    def test_to_dict_with_env(self):
        hit = SearchHit(category="skill", name="seo", env="production")
        d = hit.to_dict()
        self.assertEqual(d["env"], "production")

    def test_to_dict_with_extra(self):
        hit = SearchHit(category="mcp", name="github", extra={"enabled": True})
        d = hit.to_dict()
        self.assertTrue(d["enabled"])


class TestSearchResult(unittest.TestCase):
    """Tests for SearchResult data class."""

    def test_total(self):
        result = SearchResult(
            hits=[
                SearchHit(category="agent", name="a"),
                SearchHit(category="skill", name="b"),
            ]
        )
        self.assertEqual(result.total(), 2)

    def test_by_category_sorted(self):
        result = SearchResult(
            hits=[
                SearchHit(category="agent", name="zebra"),
                SearchHit(category="agent", name="alpha"),
                SearchHit(category="skill", name="skill-a"),
            ]
        )
        agents = result.by_category("agent")
        self.assertEqual(len(agents), 2)
        self.assertEqual(agents[0].name, "alpha")
        self.assertEqual(agents[1].name, "zebra")

    def test_categories_preserves_order(self):
        result = SearchResult(
            hits=[
                SearchHit(category="skill", name="s"),
                SearchHit(category="agent", name="a"),
                SearchHit(category="skill", name="s2"),
            ]
        )
        cats = result.categories()
        self.assertEqual(cats, ["skill", "agent"])


if __name__ == "__main__":
    unittest.main()
