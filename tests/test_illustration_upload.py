import io
import tempfile
import unittest
from pathlib import Path

import editor.app as app_module
from editor.story_nodes import create_node


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"test-png"
REPLACEMENT_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"replacement"


class IllustrationUploadTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.previous_root = app_module.WORKS_ROOT
        app_module.WORKS_ROOT = self.root
        app_module.app.config["TESTING"] = True
        self.client = app_module.app.test_client()
        create_node(self.root, self.root, "01", title="Start")

    def tearDown(self):
        app_module.WORKS_ROOT = self.previous_root
        self.tmpdir.cleanup()

    def post_png(self, data=PNG_BYTES, node_path="01"):
        return self.client.post(
            "/node/illustration",
            data={
                "node_path": node_path,
                "image": (io.BytesIO(data), "illust.png", "image/png"),
            },
        )

    def test_upload_creates_illust_png(self):
        response = self.post_png()

        self.assertEqual(response.status_code, 200)
        self.assertEqual((self.root / "01" / "illust.png").read_bytes(), PNG_BYTES)
        self.assertEqual(response.get_json()["path"], "01/illust.png")

    def test_upload_replaces_existing_illust_png(self):
        (self.root / "01" / "illust.png").write_bytes(PNG_BYTES)

        response = self.post_png(REPLACEMENT_PNG_BYTES)

        self.assertEqual(response.status_code, 200)
        self.assertEqual((self.root / "01" / "illust.png").read_bytes(), REPLACEMENT_PNG_BYTES)

    def test_upload_rejects_non_image_mimetype(self):
        response = self.client.post(
            "/node/illustration",
            data={
                "node_path": "01",
                "image": (io.BytesIO(b"hello"), "note.txt", "text/plain"),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse((self.root / "01" / "illust.png").exists())

    def test_upload_rejects_invalid_png_data(self):
        response = self.post_png(b"not-png")

        self.assertEqual(response.status_code, 400)
        self.assertFalse((self.root / "01" / "illust.png").exists())

    def test_invalid_replacement_keeps_existing_illust_png(self):
        (self.root / "01" / "illust.png").write_bytes(PNG_BYTES)

        response = self.post_png(b"not-png")

        self.assertEqual(response.status_code, 400)
        self.assertEqual((self.root / "01" / "illust.png").read_bytes(), PNG_BYTES)

    def test_upload_rejects_invalid_node_and_traversal_path(self):
        (self.root / "plain").mkdir()

        invalid_node = self.post_png(node_path="plain")
        traversal = self.post_png(node_path="../outside")

        self.assertEqual(invalid_node.status_code, 404)
        self.assertEqual(traversal.status_code, 400)
        self.assertFalse((self.root / "plain" / "illust.png").exists())

    def test_overview_contains_paste_ui_without_existing_image(self):
        response = self.client.get("/node?path=01")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("ここに画像を貼り付け / Ctrl+V", body)
        self.assertIn("Upload", body)
        self.assertIn("/static/js/node_illustration.js", body)
        self.assertIn("未作成", body)

    def test_overview_contains_replace_ui_with_existing_image(self):
        (self.root / "01" / "illust.png").write_bytes(PNG_BYTES)

        response = self.client.get("/node?path=01")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Replace", body)
        self.assertIn("/node_asset?path=01&amp;name=illust.png", body)


if __name__ == "__main__":
    unittest.main()
