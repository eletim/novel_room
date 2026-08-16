import json
import tempfile
import unittest
from pathlib import Path

from editor.story_graph import (
    StoryEdge,
    StoryGraph,
    StoryGraphError,
    add_edge,
    graph_layout,
    load_graph,
    remove_edge,
    safe_load_graph,
    save_graph,
    set_main_next,
    set_start,
    validate_graph,
)
from editor.story_nodes import create_node, list_nodes


class StoryGraphTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.work_dir = self.root / "work"
        self.work_dir.mkdir()
        for node_id in ("01", "02", "03", "03b", "04"):
            create_node(self.root, self.work_dir, node_id)
        self.nodes = list_nodes(self.root, self.work_dir)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_branch_and_merge_graph_validates_and_round_trips(self):
        graph = StoryGraph(
            start="01",
            edges=(
                StoryEdge("01", "02"),
                StoryEdge("02", "03"),
                StoryEdge("02", "03b"),
                StoryEdge("03", "04"),
                StoryEdge("03b", "04"),
            ),
            main_next={"01": "02", "02": "03b", "03b": "04"},
        )

        validate_graph(graph, self.nodes)
        save_graph(self.work_dir, graph)
        loaded = load_graph(self.work_dir)

        self.assertEqual(loaded, graph)

    def test_add_edge_rejects_cycle(self):
        graph = StoryGraph(
            start="01",
            edges=(StoryEdge("01", "02"), StoryEdge("02", "03")),
            main_next={},
        )

        with self.assertRaises(StoryGraphError):
            add_edge(graph, self.nodes, "03", "01")

    def test_add_edge_rejects_unknown_node_and_self_edge(self):
        graph = StoryGraph(start="01", edges=(), main_next={})

        with self.assertRaises(StoryGraphError):
            add_edge(graph, self.nodes, "01", "missing")
        with self.assertRaises(StoryGraphError):
            add_edge(graph, self.nodes, "01", "01")

    def test_main_route_must_follow_existing_edge(self):
        graph = StoryGraph(
            start="01",
            edges=(StoryEdge("01", "02"), StoryEdge("02", "03")),
            main_next={},
        )

        updated = set_main_next(graph, self.nodes, "02", "03")
        self.assertEqual(updated.main_next, {"02": "03"})
        with self.assertRaises(StoryGraphError):
            set_main_next(graph, self.nodes, "02", "03b")

    def test_remove_edge_clears_matching_main_route_choice(self):
        graph = StoryGraph(
            start="01",
            edges=(StoryEdge("01", "02"), StoryEdge("02", "03")),
            main_next={"01": "02", "02": "03"},
        )

        updated = remove_edge(graph, "02", "03")

        self.assertEqual(updated.edges, (StoryEdge("01", "02"),))
        self.assertEqual(updated.main_next, {"01": "02"})

    def test_start_node_must_exist(self):
        graph = StoryGraph(start="missing", edges=(), main_next={})

        with self.assertRaises(StoryGraphError):
            set_start(graph, self.nodes, "missing")

    def test_safe_load_graph_returns_default_with_errors_for_invalid_data(self):
        (self.work_dir / "graph.json").write_text(
            json.dumps({"start": "missing", "edges": [], "main_next": {}}),
            encoding="utf-8",
        )

        graph, errors = safe_load_graph(self.work_dir)

        self.assertIsNone(graph.start)
        self.assertEqual(graph.edges, ())
        self.assertTrue(errors)

    def test_safe_load_graph_handles_graph_path_that_is_not_a_file(self):
        (self.work_dir / "graph.json").mkdir()

        graph, errors = safe_load_graph(self.work_dir)

        self.assertIsNone(graph.start)
        self.assertEqual(graph.edges, ())
        self.assertIn("graph.json must be a file.", errors)

    def test_graph_layout_ranks_chain_by_edges_not_folder_name_sort(self):
        create_node(self.root, self.work_dir, "1to2")
        nodes = list_nodes(self.root, self.work_dir)
        graph = StoryGraph(
            start="01",
            edges=(StoryEdge("01", "1to2"), StoryEdge("1to2", "02")),
            main_next={"01": "1to2", "1to2": "02"},
        )

        layout = graph_layout(graph, nodes)
        nodes_by_id = {node.id: node for node in layout.nodes}
        edges_by_pair = {(edge.source, edge.target): edge for edge in layout.edges}

        self.assertEqual(nodes_by_id["01"].rank, 0)
        self.assertEqual(nodes_by_id["1to2"].rank, 1)
        self.assertEqual(nodes_by_id["02"].rank, 2)
        self.assertLess(nodes_by_id["01"].x, nodes_by_id["1to2"].x)
        self.assertLess(nodes_by_id["1to2"].x, nodes_by_id["02"].x)
        self.assertTrue(edges_by_pair[("01", "1to2")].is_main)
        self.assertTrue(edges_by_pair[("1to2", "02")].is_main)
        self.assertIn("C", edges_by_pair[("01", "1to2")].path)

    def test_graph_layout_places_branch_and_merge_spatially(self):
        graph = StoryGraph(
            start="01",
            edges=(
                StoryEdge("01", "02"),
                StoryEdge("01", "03b"),
                StoryEdge("02", "04"),
                StoryEdge("03b", "04"),
            ),
            main_next={"01": "03b", "03b": "04"},
        )

        layout = graph_layout(graph, self.nodes)
        nodes_by_id = {node.id: node for node in layout.nodes}
        edges_by_pair = {(edge.source, edge.target): edge for edge in layout.edges}

        self.assertEqual(nodes_by_id["02"].rank, 1)
        self.assertEqual(nodes_by_id["03b"].rank, 1)
        self.assertNotEqual(nodes_by_id["02"].lane, nodes_by_id["03b"].lane)
        self.assertTrue(nodes_by_id["01"].is_branch)
        self.assertTrue(nodes_by_id["04"].is_merge)
        self.assertEqual(nodes_by_id["04"].rank, 2)
        self.assertTrue(nodes_by_id["03b"].is_main)
        self.assertTrue(edges_by_pair[("01", "03b")].is_main)
        self.assertFalse(edges_by_pair[("01", "02")].is_main)


if __name__ == "__main__":
    unittest.main()
