"""Tests for agent_format.py."""

import tempfile
import unittest
from pathlib import Path

from ai_adapter.agent_format import (
    _convert_tools_in_frontmatter,
    batch_validate_and_fix,
    convert_agent_file,
    convert_tools_to_object,
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
