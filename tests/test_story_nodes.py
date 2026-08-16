import json
import tempfile
import unittest
from pathlib import Path

from editor.story_nodes import StoryNodeError, create_node, inspect_node_folder, list_nodes, load_node


class StoryNodeTests(unittest.TestCase):
    def test_create_node_writes_required_files_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            node = create_node(root, root, "03", title="勇者覚醒")

            self.assertEqual(node.id, "03")
            self.assertEqual(node.title, "勇者覚醒")
            self.assertEqual(node.status, "draft")
            self.assertTrue((root / "03" / "main.md").is_file())
            manifest = json.loads((root / "03" / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest, {"id": "03", "title": "勇者覚醒", "status": "draft"})

    def test_optional_files_are_not_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_node(root, root, "01")

            inspection = inspect_node_folder(root, root / "01")

            self.assertTrue(inspection.is_node)
            self.assertEqual(inspection.missing_required, ())
            self.assertEqual(inspection.optional_files, ())

    def test_invalid_manifest_is_reported_without_loading_node(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            node_dir = root / "bad"
            node_dir.mkdir()
            (node_dir / "main.md").write_text("", encoding="utf-8")
            (node_dir / "manifest.json").write_text("{", encoding="utf-8")

            inspection = inspect_node_folder(root, node_dir)

            self.assertFalse(inspection.is_node)
            self.assertTrue(inspection.errors)
            with self.assertRaises(StoryNodeError):
                load_node(root, node_dir)

    def test_non_utf8_manifest_is_reported_without_loading_node(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            node_dir = root / "bad-encoding"
            node_dir.mkdir()
            (node_dir / "main.md").write_text("", encoding="utf-8")
            (node_dir / "manifest.json").write_bytes(b"\xff\xfe\x00")

            inspection = inspect_node_folder(root, node_dir)

            self.assertFalse(inspection.is_node)
            self.assertIn("manifest.json must be UTF-8 text.", inspection.errors)
            with self.assertRaises(StoryNodeError):
                load_node(root, node_dir)

    def test_missing_required_file_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            node_dir = root / "missing"
            node_dir.mkdir()
            (node_dir / "manifest.json").write_text('{"id": "missing"}', encoding="utf-8")

            inspection = inspect_node_folder(root, node_dir)

            self.assertFalse(inspection.is_node)
            self.assertEqual(inspection.missing_required, ("main.md",))

    def test_list_nodes_ignores_plain_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_node(root, root, "b")
            create_node(root, root, "a")
            (root / "plain").mkdir()

            nodes = list_nodes(root, root)

            self.assertEqual([node.id for node in nodes], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
