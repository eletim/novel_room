import json
import tempfile
import unittest
from pathlib import Path

import editor.app as app_module
from editor.story_graph import StoryEdge, StoryGraph, save_graph
from editor.story_nodes import create_node


class GraphUiRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.work_dir = self.root / "work"
        self.work_dir.mkdir()
        self.previous_root = app_module.WORKS_ROOT
        app_module.WORKS_ROOT = self.root
        app_module.app.config["TESTING"] = True
        self.client = app_module.app.test_client()

    def tearDown(self):
        app_module.WORKS_ROOT = self.previous_root
        self.tmpdir.cleanup()

    def test_graph_page_renders_nodes_and_raw_folder_link(self):
        create_node(self.root, self.work_dir, "01", title="Start")

        response = self.client.get("/graph?path=work")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("work Graph", body)
        self.assertIn("/node?path=work/01", body)
        self.assertIn("/folder?path=work", body)

    def test_work_entry_opens_graph_and_keeps_explicit_raw_folder_link(self):
        create_node(self.root, self.work_dir, "01", title="Start")

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('/graph?path=work"', body)
        self.assertIn('/folder?path=work"', body)

    def test_raw_folder_keeps_generic_folder_operations(self):
        create_node(self.root, self.work_dir, "01", title="Start")

        response = self.client.get("/folder?path=work")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('action="/create_folder"', body)
        self.assertIn('action="/create_file"', body)
        self.assertIn('action="/rename"', body)
        self.assertIn('action="/delete"', body)

        create_folder = self.client.post(
            "/create_folder",
            data={"current_path": "work", "name": "notes"},
            follow_redirects=False,
        )
        create_file = self.client.post(
            "/create_file",
            data={"current_path": "work", "name": "memo.md"},
            follow_redirects=False,
        )

        self.assertEqual(create_folder.status_code, 302)
        self.assertEqual(create_file.status_code, 302)
        self.assertTrue((self.work_dir / "notes").is_dir())
        self.assertTrue((self.work_dir / "memo.md").is_file())

    def test_graph_display_order_follows_edges_not_folder_name_sort(self):
        create_node(self.root, self.work_dir, "01")
        create_node(self.root, self.work_dir, "02")
        create_node(self.root, self.work_dir, "1to2")
        save_graph(
            self.work_dir,
            StoryGraph(
                start="01",
                edges=(StoryEdge("01", "1to2"), StoryEdge("1to2", "02")),
                main_next={"01": "1to2", "1to2": "02"},
            ),
        )

        response = self.client.get("/graph?path=work")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertLess(body.index('data-node-id="01"'), body.index('data-node-id="1to2"'))
        self.assertLess(body.index('data-node-id="1to2"'), body.index('data-node-id="02"'))
        self.assertIn("01", body)
        self.assertIn("1to2", body)
        self.assertIn("02", body)

    def test_graph_displays_branch_merge_and_main_route_from_graph_data(self):
        for node_id in ("01", "1to2", "02A", "02B", "03"):
            create_node(self.root, self.work_dir, node_id)
        save_graph(
            self.work_dir,
            StoryGraph(
                start="01",
                edges=(
                    StoryEdge("01", "1to2"),
                    StoryEdge("1to2", "02A"),
                    StoryEdge("1to2", "02B"),
                    StoryEdge("02A", "03"),
                    StoryEdge("02B", "03"),
                ),
                main_next={"01": "1to2", "1to2": "02B", "02B": "03"},
            ),
        )

        response = self.client.get("/graph?path=work")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("branch", body)
        self.assertIn("merge", body)
        self.assertIn("01", body)
        self.assertIn("1to2", body)
        self.assertIn("02B", body)
        self.assertIn("03", body)
        self.assertLess(body.index('data-node-id="1to2"'), body.index('data-node-id="02B"'))
        self.assertLess(body.index('data-node-id="02B"'), body.index('data-node-id="03"'))

    def test_graph_invalid_or_missing_data_falls_back_safely(self):
        create_node(self.root, self.work_dir, "01")
        response_without_graph = self.client.get("/graph?path=work")
        self.assertEqual(response_without_graph.status_code, 200)
        self.assertIn("未設定", response_without_graph.get_data(as_text=True))

        (self.work_dir / "graph.json").write_text('{"start": "missing", "edges": []}', encoding="utf-8")
        response_with_invalid_graph = self.client.get("/graph?path=work")

        self.assertEqual(response_with_invalid_graph.status_code, 200)
        self.assertIn("Start node does not exist: missing.", response_with_invalid_graph.get_data(as_text=True))

    def test_graph_forms_create_node_edge_and_main_route(self):
        create_node(self.root, self.work_dir, "01")
        create_node(self.root, self.work_dir, "02")
        create_node(self.root, self.work_dir, "03")

        self.client.post("/graph/set_start", data={"work_path": "work", "start": "01"})
        self.client.post("/graph/add_edge", data={"work_path": "work", "source": "01", "target": "02"})
        self.client.post("/graph/add_edge", data={"work_path": "work", "source": "01", "target": "03"})
        self.client.post("/graph/set_main", data={"work_path": "work", "edge": "01\t03"})

        graph = json.loads((self.work_dir / "graph.json").read_text(encoding="utf-8"))
        self.assertEqual(graph["start"], "01")
        self.assertIn({"from": "01", "to": "02"}, graph["edges"])
        self.assertIn({"from": "01", "to": "03"}, graph["edges"])
        self.assertEqual(graph["main_next"], {"01": "03"})

        response = self.client.get("/graph?path=work")
        body = response.get_data(as_text=True)
        self.assertIn("branch", body)
        self.assertIn("01 → 03", body)

    def test_graph_rejects_cycle_and_keeps_existing_edges(self):
        create_node(self.root, self.work_dir, "01")
        create_node(self.root, self.work_dir, "02")
        self.client.post("/graph/add_edge", data={"work_path": "work", "source": "01", "target": "02"})

        response = self.client.post(
            "/graph/add_edge",
            data={"work_path": "work", "source": "02", "target": "01"},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Cycles are not allowed.", response.get_data(as_text=True))
        graph = json.loads((self.work_dir / "graph.json").read_text(encoding="utf-8"))
        self.assertEqual(graph["edges"], [{"from": "01", "to": "02"}])

    def test_graph_create_node_posts_to_work_folder(self):
        response = self.client.post(
            "/graph/create_node",
            data={"work_path": "work", "name": "01", "title": "Start"},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/graph?path=work&notice=Story+node+created.")
        self.assertTrue((self.work_dir / "01" / "main.md").is_file())


if __name__ == "__main__":
    unittest.main()
