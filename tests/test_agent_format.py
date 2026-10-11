"""Tests for agent_format.py."""

import tempfile
import unittest
from pathlib import Path

from ai_adapter.agent_format import (
    _convert_tools_in_frontmatter,
    _convert_tools_in_frontmatter_to_array,
    _convert_tools_in_frontmatter_to_string,
    batch_validate_and_fix,
    convert_agent_file,
    convert_agent_file_to_array,
    convert_agent_file_to_string,
    convert_tools_to_array,
    convert_tools_to_object,
    convert_tools_to_string,
    parse_frontmatter,
    validate_agent_file,
)


class TestConvertToolsToObject(unittest.TestCase):
    """Tests for convert_tools_to_object()."""

    def test_convert_tools_array_to_object(self):
        """Array format ``["execute", "read"]`` → object format."""
        result, modified = convert_tools_to_object(["execute", "read"])
        self.assertEqual(result, {"execute": True, "read": True})
        self.assertTrue(modified)

    def test_convert_tools_object_preserved(self):
        """Object format is returned as-is."""
        result, modified = convert_tools_to_object({"execute": True, "read": True})
        self.assertEqual(result, {"execute": True, "read": True})
        self.assertFalse(modified)

    def test_convert_tools_empty_array(self):
        """Empty list ``[]`` → ``{}``."""
        result, modified = convert_tools_to_object([])
        self.assertEqual(result, {})
        self.assertTrue(modified)

    def test_convert_tools_none(self):
        """``None`` → ``{}``, no modification flag."""
        result, modified = convert_tools_to_object(None)
        self.assertEqual(result, {})
        self.assertFalse(modified)

    def test_convert_tools_invalid_type_string(self):
        """String value → ``{}``, no modification flag."""
        result, modified = convert_tools_to_object("invalid")
        self.assertEqual(result, {})
        self.assertFalse(modified)

    def test_convert_tools_invalid_type_int(self):
        """Integer value → ``{}``, no modification flag."""
        result, modified = convert_tools_to_object(42)
        self.assertEqual(result, {})
        self.assertFalse(modified)

    def test_convert_tools_was_modified_flag(self):
        """Flag is True on conversion, False on no conversion."""
        _, modified_array = convert_tools_to_object(["execute"])
        self.assertTrue(modified_array)

        _, modified_dict = convert_tools_to_object({"execute": True})
        self.assertFalse(modified_dict)

        _, modified_none = convert_tools_to_object(None)
        self.assertFalse(modified_none)

    def test_convert_tools_mixed_list(self):
        """List with non-string items; only strings are kept."""
        result, modified = convert_tools_to_object(["execute", 42, "read"])
        self.assertEqual(result, {"execute": True, "read": True})
        self.assertTrue(modified)


class TestConvertToolsToArray(unittest.TestCase):
    """Tests for convert_tools_to_array() — object → array (VS Code)."""

    def test_convert_tools_object_to_array(self):
        result, modified = convert_tools_to_array({"execute": True, "read": True})
        self.assertEqual(result, ["execute", "read"])
        self.assertTrue(modified)

    def test_convert_tools_object_drops_falsy(self):
        result, modified = convert_tools_to_array({"execute": True, "read": False})
        self.assertEqual(result, ["execute"])
        self.assertTrue(modified)

    def test_convert_tools_array_preserved(self):
        result, modified = convert_tools_to_array(["execute", "read"])
        self.assertEqual(result, ["execute", "read"])
        self.assertFalse(modified)

    def test_convert_tools_none(self):
        result, modified = convert_tools_to_array(None)
        self.assertEqual(result, [])
        self.assertFalse(modified)

    def test_convert_tools_invalid_type(self):
        result, modified = convert_tools_to_array("invalid")
        self.assertEqual(result, [])
        self.assertFalse(modified)


class TestConvertToolsInFrontmatterToArray(unittest.TestCase):
    """Tests for _convert_tools_in_frontmatter_to_array()."""

    def test_convert_object_block(self):
        fm = "name: x\ntools:\n  execute: true\n  read: true\n"
        result, modified = _convert_tools_in_frontmatter_to_array(fm)
        self.assertTrue(modified)
        self.assertIn("tools: [execute, read]", result)
        self.assertNotIn("  execute: true", result)

    def test_convert_object_block_drops_falsy(self):
        fm = "tools:\n  execute: true\n  read: false\n"
        result, modified = _convert_tools_in_frontmatter_to_array(fm)
        self.assertTrue(modified)
        self.assertIn("tools: [execute]", result)

    def test_array_format_untouched(self):
        fm = "tools: [execute, read]\n"
        result, modified = _convert_tools_in_frontmatter_to_array(fm)
        self.assertFalse(modified)

    def test_quoted_keys_preserved(self):
        fm = "tools:\n  'codebase-memory-mcp/*': true\n  vscode: true\n"
        result, modified = _convert_tools_in_frontmatter_to_array(fm)
        self.assertTrue(modified)
        # Quotes are stripped; "name/*" mid-token is valid YAML in flow sequences.
        self.assertIn("tools: [codebase-memory-mcp/*, vscode]", result)


class TestConvertAgentFileToArray(unittest.TestCase):
    """Tests for convert_agent_file_to_array()."""

    def test_converts_object_to_array(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "a.agent.md"
            f.write_text("---\nname: a\ntools:\n  read: true\n  edit: false\n---\nBody\n")
            self.assertTrue(convert_agent_file_to_array(f))
            content = f.read_text()
            self.assertIn("tools: [read]", content)
            self.assertNotIn("  read: true", content)

    def test_no_change_for_array(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "a.agent.md"
            f.write_text("---\nname: a\ntools: [read]\n---\nBody\n")
            self.assertFalse(convert_agent_file_to_array(f))

    def test_skips_non_agent_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "a.md"
            f.write_text("---\nname: a\ntools:\n  read: true\n---\n")
            self.assertFalse(convert_agent_file_to_array(f))


class TestConvertToolsToString(unittest.TestCase):
    """Tests for convert_tools_to_string() — Claude comma-separated format."""

    def test_array_to_string(self):
        result, modified = convert_tools_to_string(["Read", "Grep"])
        self.assertEqual(result, "Read, Grep")
        self.assertTrue(modified)

    def test_object_to_string(self):
        result, modified = convert_tools_to_string({"Read": True, "Grep": True})
        self.assertEqual(result, "Read, Grep")
        self.assertTrue(modified)

    def test_object_drops_falsy(self):
        result, modified = convert_tools_to_string({"Read": True, "Grep": False})
        self.assertEqual(result, "Read")
        self.assertTrue(modified)

    def test_string_passthrough(self):
        result, modified = convert_tools_to_string("Read, Grep")
        self.assertEqual(result, "Read, Grep")
        self.assertFalse(modified)

    def test_none(self):
        result, modified = convert_tools_to_string(None)
        self.assertEqual(result, "")
        self.assertFalse(modified)


class TestConvertToolsInFrontmatterToString(unittest.TestCase):
    """Tests for _convert_tools_in_frontmatter_to_string()."""

    def test_array_line(self):
        fm = "name: x\ntools: [read, grep]\n"
        result, modified = _convert_tools_in_frontmatter_to_string(fm)
        self.assertTrue(modified)
        self.assertIn("tools: read, grep", result)

    def test_object_block(self):
        fm = "tools:\n  read: true\n  grep: true\n  skip: false\n"
        result, modified = _convert_tools_in_frontmatter_to_string(fm)
        self.assertTrue(modified)
        self.assertIn("tools: read, grep", result)
        self.assertNotIn("skip", result)

    def test_string_line_untouched(self):
        fm = "tools: read, grep\n"
        result, modified = _convert_tools_in_frontmatter_to_string(fm)
        self.assertFalse(modified)


class TestConvertAgentFileToString(unittest.TestCase):
    """Tests for convert_agent_file_to_string()."""

    def test_converts_array(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "a.agent.md"
            f.write_text("---\nname: a\ntools: [read, grep]\n---\nBody\n")
            self.assertTrue(convert_agent_file_to_string(f))
            self.assertIn("tools: read, grep", f.read_text())

    def test_converts_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "a.agent.md"
            f.write_text("---\nname: a\ntools:\n  read: true\n  edit: false\n---\nBody\n")
            self.assertTrue(convert_agent_file_to_string(f))
            content = f.read_text()
            self.assertIn("tools: read", content)
            self.assertNotIn("edit", content)

    def test_string_no_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "a.agent.md"
            f.write_text("---\nname: a\ntools: read, grep\n---\nBody\n")
            self.assertFalse(convert_agent_file_to_string(f))


class TestValidateAgentFileStringTarget(unittest.TestCase):
    """validate_agent_file with target_format='string' (Claude Code)."""

    def test_array_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "a.agent.md"
            f.write_text("---\nname: a\ntools: [read]\n---\n")
            errs = validate_agent_file(f, target_format="string")
            self.assertEqual(len(errs), 1)
            self.assertIn("expected comma-separated string", errs[0])

    def test_object_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "a.agent.md"
            f.write_text("---\nname: a\ntools:\n  read: true\n---\n")
            errs = validate_agent_file(f, target_format="string")
            self.assertEqual(len(errs), 1)

    def test_string_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "a.agent.md"
            f.write_text("---\nname: a\ntools: read, grep\n---\n")
            self.assertEqual(validate_agent_file(f, target_format="string"), [])


class TestConvertToolsInFrontmatter(unittest.TestCase):
    """Tests for _convert_tools_in_frontmatter()."""

    def test_convert_tools_in_frontmatter_basic(self):
        """Array format in frontmatter text is converted to object format."""
        frontmatter = "name: test\ntools: [execute, read]\n"
        result, modified = _convert_tools_in_frontmatter(frontmatter)
        self.assertTrue(modified)
        self.assertIn("tools:", result)
        self.assertIn("  execute: true", result)
        self.assertIn("  read: true", result)
        self.assertNotIn("[execute, read]", result)

    def test_convert_tools_in_frontmatter_no_change(self):
        """Already object format → no change."""
        frontmatter = "name: test\ntools:\n  execute: true\n"
        result, modified = _convert_tools_in_frontmatter(frontmatter)
        self.assertFalse(modified)
        self.assertEqual(result, frontmatter)

    def test_convert_tools_in_frontmatter_comment(self):
        """YAML comment in frontmatter is preserved."""
        frontmatter = "name: test\n# this is a comment\ntools: [execute, read]\n"
        result, modified = _convert_tools_in_frontmatter(frontmatter)
        self.assertTrue(modified)
        self.assertIn("# this is a comment", result)
        self.assertIn("  execute: true", result)

    def test_convert_tools_in_frontmatter_empty_array(self):
        """Empty array ``tools: []`` becomes ``tools: {}``."""
        frontmatter = "name: test\ntools: []\n"
        result, modified = _convert_tools_in_frontmatter(frontmatter)
        self.assertTrue(modified)
        self.assertIn("tools: {}", result)

    def test_convert_tools_in_frontmatter_mixed_spacing(self):
        """Array with extra whitespace is handled."""
        frontmatter = "tools:  [  execute ,  read  ]\n"
        result, modified = _convert_tools_in_frontmatter(frontmatter)
        self.assertTrue(modified)
        self.assertIn("  execute: true", result)
        self.assertIn("  read: true", result)

    def test_convert_tools_in_frontmatter_other_lines_untouched(self):
        """Non-tools lines in frontmatter are preserved unchanged."""
        frontmatter = "name: test\ndescription: some agent\ntools: [execute, read]\ntemperature: 0.7\n"
        result, modified = _convert_tools_in_frontmatter(frontmatter)
        self.assertTrue(modified)
        self.assertIn("name: test", result)
        self.assertIn("description: some agent", result)
        self.assertIn("temperature: 0.7", result)
        self.assertIn("  execute: true", result)

    def test_convert_tools_in_frontmatter_no_tools_field(self):
        """No ``tools:`` field → no change."""
        frontmatter = "name: test\ndescription: agent\n"
        result, modified = _convert_tools_in_frontmatter(frontmatter)
        self.assertFalse(modified)
        self.assertEqual(result, frontmatter)

    def test_convert_tools_in_frontmatter_indented(self):
        """Indented tools line is preserved."""
        frontmatter = "metadata:\n  tools: [execute]\n"
        result, modified = _convert_tools_in_frontmatter(frontmatter)
        self.assertTrue(modified)
        self.assertIn("  tools:", result)
        self.assertIn("    execute: true", result)

    def test_convert_tools_in_frontmatter_inline_comment(self):
        """Line with ``#`` as inline comment is still converted."""
        frontmatter = "tools: [execute]  # allow execution\n"
        result, modified = _convert_tools_in_frontmatter(frontmatter)
        self.assertTrue(modified)
        self.assertIn("  execute: true", result)

    def test_convert_tools_in_frontmatter_quoted_items(self):
        """Items with quotes in array are handled."""
        frontmatter = "tools: [\"execute\", 'read']\n"
        result, modified = _convert_tools_in_frontmatter(frontmatter)
        self.assertTrue(modified)
        self.assertIn("  execute: true", result)
        self.assertIn("  read: true", result)


class TestConvertAgentFile(unittest.TestCase):
    """Tests for convert_agent_file()."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_convert_agent_file_array_to_object(self):
        """File with array-format tools is converted."""
        path = self.temp_path / "test.agent.md"
        path.write_text("---\nname: test\ntools: [execute, read]\n---\n# Test\n")
        result = convert_agent_file(path)
        self.assertTrue(result)
        content = path.read_text()
        self.assertIn("  execute: true", content)
        self.assertIn("  read: true", content)
        self.assertNotIn("[execute, read]", content)
        # Frontmatter name stays
        self.assertIn("name: test", content)
        # Content after --- is preserved
        self.assertIn("# Test", content)

    def test_convert_agent_file_not_agent_md(self):
        """Non-``.agent.md`` file is skipped."""
        path = self.temp_path / "test.md"
        path.write_text("---\ntools: [execute]\n---\n")
        result = convert_agent_file(path)
        self.assertFalse(result)

    def test_convert_agent_file_no_frontmatter(self):
        """File without frontmatter is skipped."""
        path = self.temp_path / "test.agent.md"
        path.write_text("# Just markdown\n")
        result = convert_agent_file(path)
        self.assertFalse(result)

    def test_convert_agent_file_already_object(self):
        """Already correct format is not modified."""
        path = self.temp_path / "test.agent.md"
        path.write_text("---\nname: test\ntools:\n  execute: true\n---\n")
        result = convert_agent_file(path)
        self.assertFalse(result)

    def test_convert_agent_file_comment_preserved(self):
        """YAML comment is preserved after conversion."""
        path = self.temp_path / "test.agent.md"
        original = "---\n# this is a comment\nname: test\ntools: [execute]\n---\n"
        path.write_text(original)
        result = convert_agent_file(path)
        self.assertTrue(result)
        content = path.read_text()
        self.assertIn("# this is a comment", content)


class TestValidateAgentFile(unittest.TestCase):
    """Tests for validate_agent_file()."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_validate_agent_file_valid_object(self):
        """Object-format tools → no errors."""
        path = self.temp_path / "valid.agent.md"
        path.write_text("---\nname: test\ntools:\n  execute: true\n---\n")
        errors = validate_agent_file(path)
        self.assertEqual(errors, [])

    def test_validate_agent_file_invalid_array(self):
        """Array-format tools → error detected."""
        path = self.temp_path / "invalid.agent.md"
        path.write_text("---\nname: test\ntools: [execute, read]\n---\n")
        errors = validate_agent_file(path)
        self.assertEqual(len(errors), 1)
        self.assertIn("array format", errors[0])

    def test_validate_agent_file_not_agent_md(self):
        """Non-``.agent.md`` file is skipped."""
        path = self.temp_path / "test.md"
        path.write_text("---\ntools: [execute]\n---\n")
        errors = validate_agent_file(path)
        self.assertEqual(errors, [])

    def test_validate_agent_file_no_frontmatter(self):
        """File without frontmatter → no errors."""
        path = self.temp_path / "test.agent.md"
        path.write_text("# Just markdown\n")
        errors = validate_agent_file(path)
        self.assertEqual(errors, [])

    def test_validate_agent_file_no_tools(self):
        """File without tools field → no errors."""
        path = self.temp_path / "test.agent.md"
        path.write_text("---\nname: test\n---\n")
        errors = validate_agent_file(path)
        self.assertEqual(errors, [])

    def test_validate_agent_file_not_found(self):
        """Non-existent file → error."""
        path = self.temp_path / "nonexistent.agent.md"
        errors = validate_agent_file(path)
        self.assertGreater(len(errors), 0)

    def test_validate_agent_file_empty_dir(self):
        """Empty directory content → (nothing, just no crash)."""
        # This test ensures validate_agent_file handles missing files gracefully
        path = self.temp_path / "ghost.agent.md"
        errors = validate_agent_file(path)
        self.assertGreater(len(errors), 0)


class TestBatchValidateAndFix(unittest.TestCase):
    """Tests for batch_validate_and_fix()."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        # Create a valid file
        self.valid = self.temp_path / "valid.agent.md"
        self.valid.write_text("---\nname: valid\ntools:\n  execute: true\n---\n")
        # Create an invalid file
        self.invalid = self.temp_path / "invalid.agent.md"
        self.invalid.write_text("---\nname: invalid\ntools: [execute, read]\n---\n")
        # Create a non-agent file (should be skipped)
        self.plain = self.temp_path / "plain.md"
        self.plain.write_text("---\ntools: [execute]\n---\n")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_batch_validate_and_fix_detect(self):
        """Detects invalid files."""
        errors = batch_validate_and_fix(self.temp_path, fix=False)
        self.assertEqual(len(errors), 1)
        self.assertIn("invalid.agent.md", errors[0])

    def test_batch_validate_and_fix_and_fix(self):
        """Fixes invalid files when fix=True."""
        errors = batch_validate_and_fix(self.temp_path, fix=True)
        # After fixing, no errors remain
        self.assertEqual(len(errors), 0)

        # Verify the file was actually fixed
        content = self.invalid.read_text()
        self.assertIn("  execute: true", content)
        self.assertNotIn("[execute, read]", content)

        # Valid file should be unchanged
        content_valid = self.valid.read_text()
        self.assertIn("  execute: true", content_valid)


class TestValidateAgentFileArrayTarget(unittest.TestCase):
    """validate_agent_file / batch_validate_and_fix with target_format='array'."""

    def test_object_format_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "a.agent.md"
            f.write_text("---\nname: a\ntools:\n  read: true\n---\n")
            errs = validate_agent_file(f, target_format="array")
            self.assertEqual(len(errs), 1)
            self.assertIn("object format (expected array)", errs[0])

    def test_array_format_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "a.agent.md"
            f.write_text("---\nname: a\ntools: [read]\n---\n")
            self.assertEqual(validate_agent_file(f, target_format="array"), [])

    def test_batch_fix_array(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "a.agent.md").write_text("---\nname: a\ntools:\n  read: true\n---\n")
            problems = batch_validate_and_fix(d, fix=False, target_format="array")
            self.assertEqual(len(problems), 1)
            problems = batch_validate_and_fix(d, fix=True, target_format="array")
            self.assertEqual(problems, [])
            self.assertIn("tools: [read]", (d / "a.agent.md").read_text())


class TestParseFrontmatter(unittest.TestCase):
    """Tests for parse_frontmatter() (moved from agent.py)."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parse_frontmatter_basic(self):
        """Basic frontmatter is parsed correctly."""
        path = self.temp_path / "test.agent.md"
        path.write_text("---\nname: TestAgent\ndescription: A test agent\n---\n# Content\n")
        data = parse_frontmatter(path)
        self.assertEqual(data.get("name"), "TestAgent")
        self.assertEqual(data.get("description"), "A test agent")

    def test_parse_frontmatter_no_frontmatter(self):
        """No frontmatter → empty dict."""
        path = self.temp_path / "test.agent.md"
        path.write_text("# Just markdown\n")
        data = parse_frontmatter(path)
        self.assertEqual(data, {})

    def test_parse_frontmatter_empty_frontmatter(self):
        """Empty frontmatter → empty dict."""
        path = self.temp_path / "test.agent.md"
        path.write_text("---\n---\n# Content\n")
        data = parse_frontmatter(path)
        self.assertEqual(data, {})

    def test_parse_frontmatter_with_tools_array(self):
        """Frontmatter with array-format tools is parsed as YAML list."""
        path = self.temp_path / "test.agent.md"
        path.write_text("---\nname: test\ntools: [execute, read]\n---\n")
        data = parse_frontmatter(path)
        self.assertEqual(data.get("name"), "test")
        self.assertEqual(data.get("tools"), ["execute", "read"])

    def test_parse_frontmatter_with_tools_object(self):
        """Frontmatter with object-format tools is parsed as YAML dict."""
        path = self.temp_path / "test.agent.md"
        path.write_text("---\nname: test\ntools:\n  execute: true\n---\n")
        data = parse_frontmatter(path)
        self.assertEqual(data.get("name"), "test")
        self.assertEqual(data.get("tools"), {"execute": True})


if __name__ == "__main__":
    unittest.main()
