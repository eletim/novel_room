import tempfile
import unittest
from pathlib import Path

import editor.app as app_module
from editor.story_nodes import create_node


class NodeOverviewRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.previous_root = app_module.WORKS_ROOT
        app_module.WORKS_ROOT = self.root
        app_module.app.config["TESTING"] = True
        self.client = app_module.app.test_client()

    def tearDown(self):
        app_module.WORKS_ROOT = self.previous_root
        self.tmpdir.cleanup()

    def test_node_link_opens_overview_and_raw_folder_link_remains(self):
        create_node(self.root, self.root, "01", title="Start")

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('/node?path=01"', body)
        self.assertIn('/folder?path=01"', body)

    def test_overview_shows_main_metadata_and_optional_absence(self):
        node_dir = self.root / "01"
        create_node(self.root, self.root, "01", title="Start")
        (node_dir / "main.md").write_text("abc", encoding="utf-8")

        response = self.client.get("/node?path=01")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Start", body)
        self.assertIn("Node ID", body)
        self.assertIn("文字数: 3", body)
        self.assertIn("/edit?path=01/main.md", body)
        self.assertIn("Raw Folder", body)
        self.assertIn("未作成", body)

    def test_overview_links_free_memo_when_present(self):
        node_dir = self.root / "01"
        create_node(self.root, self.root, "01", title="Start")
        (node_dir / "free_memo.md").write_text("memo", encoding="utf-8")

        response = self.client.get("/node?path=01")

        self.assertEqual(response.status_code, 200)
        self.assertIn("/edit?path=01/free_memo.md", response.get_data(as_text=True))

    def test_create_node_redirects_to_overview(self):
        response = self.client.post(
            "/create_node",
            data={"current_path": "", "name": "02", "title": "Next"},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/node?path=02")


if __name__ == "__main__":
    unittest.main()
