import json
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path

try:
    from .story_nodes import StoryNode, StoryNodeError, list_nodes
except ImportError:
    from story_nodes import StoryNode, StoryNodeError, list_nodes


GRAPH_FILE_NAME = "graph.json"


class StoryGraphError(ValueError):
    pass


@dataclass(frozen=True, order=True)
class StoryEdge:
    source: str
    target: str

    def to_dict(self) -> dict[str, str]:
        return {"from": self.source, "to": self.target}


@dataclass(frozen=True)
class StoryGraph:
    start: str | None
    edges: tuple[StoryEdge, ...]
    main_next: dict[str, str]

    def to_dict(self) -> dict:
        return {
            "start": self.start,
            "edges": [edge.to_dict() for edge in self.edges],
            "main_next": dict(sorted(self.main_next.items())),
        }


def graph_path(work_dir: Path) -> Path:
    return work_dir / GRAPH_FILE_NAME


def node_ids(nodes: list[StoryNode]) -> set[str]:
    return {node.id for node in nodes}


def default_graph(nodes: list[StoryNode]) -> StoryGraph:
    return StoryGraph(start=None, edges=(), main_next={})


def load_graph(work_dir: Path) -> StoryGraph:
    path = graph_path(work_dir)
    if not path.exists():
        return default_graph(list_nodes(work_dir.parent, work_dir))
    if not path.is_file():
        raise StoryGraphError("graph.json must be a file.")

    try:
        raw_graph = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise StoryGraphError("graph.json must be UTF-8 text.") from exc
    except JSONDecodeError as exc:
        raise StoryGraphError(f"graph.json is invalid JSON: {exc.msg}.") from exc

    if not isinstance(raw_graph, dict):
        raise StoryGraphError("graph.json must contain a JSON object.")

    start = raw_graph.get("start")
    if start is not None and not isinstance(start, str):
        raise StoryGraphError("graph.start must be a string or null.")

    raw_edges = raw_graph.get("edges", [])
    if not isinstance(raw_edges, list):
        raise StoryGraphError("graph.edges must be an array.")

    edges = []
    for raw_edge in raw_edges:
        if not isinstance(raw_edge, dict):
            raise StoryGraphError("Each edge must be an object.")
        source = raw_edge.get("from")
        target = raw_edge.get("to")
        if not isinstance(source, str) or not source.strip():
            raise StoryGraphError("Each edge.from must be a non-empty string.")
        if not isinstance(target, str) or not target.strip():
            raise StoryGraphError("Each edge.to must be a non-empty string.")
        edges.append(StoryEdge(source.strip(), target.strip()))

    raw_main_next = raw_graph.get("main_next", {})
    if not isinstance(raw_main_next, dict):
        raise StoryGraphError("graph.main_next must be an object.")

    main_next = {}
    for source, target in raw_main_next.items():
        if not isinstance(source, str) or not source.strip():
            raise StoryGraphError("Each main route source must be a non-empty string.")
        if not isinstance(target, str) or not target.strip():
            raise StoryGraphError("Each main route target must be a non-empty string.")
        main_next[source.strip()] = target.strip()

    return StoryGraph(start=start.strip() if isinstance(start, str) and start.strip() else None, edges=tuple(edges), main_next=main_next)


def save_graph(work_dir: Path, graph: StoryGraph) -> None:
    graph_path(work_dir).write_text(json.dumps(graph.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_graph(graph: StoryGraph, nodes: list[StoryNode]) -> None:
    ids = node_ids(nodes)
    if graph.start is not None and graph.start not in ids:
        raise StoryGraphError(f"Start node does not exist: {graph.start}.")

    seen_edges: set[StoryEdge] = set()
    for edge in graph.edges:
        if edge.source == edge.target:
            raise StoryGraphError("Self edges are not allowed.")
        if edge.source not in ids:
            raise StoryGraphError(f"Edge source does not exist: {edge.source}.")
        if edge.target not in ids:
            raise StoryGraphError(f"Edge target does not exist: {edge.target}.")
        if edge in seen_edges:
            raise StoryGraphError(f"Duplicate edge: {edge.source} -> {edge.target}.")
        seen_edges.add(edge)

    if has_cycle(graph.edges):
        raise StoryGraphError("Cycles are not allowed.")

    edge_pairs = {(edge.source, edge.target) for edge in graph.edges}
    for source, target in graph.main_next.items():
        if source not in ids:
            raise StoryGraphError(f"Main route source does not exist: {source}.")
        if target not in ids:
            raise StoryGraphError(f"Main route target does not exist: {target}.")
        if (source, target) not in edge_pairs:
            raise StoryGraphError(f"Main route must follow an existing edge: {source} -> {target}.")


def load_valid_graph(work_dir: Path) -> StoryGraph:
    nodes = list_nodes(work_dir.parent, work_dir)
    graph = load_graph(work_dir)
    validate_graph(graph, nodes)
    return graph


def safe_load_graph(work_dir: Path) -> tuple[StoryGraph, tuple[str, ...]]:
    nodes = list_nodes(work_dir.parent, work_dir)
    try:
        graph = load_graph(work_dir)
        validate_graph(graph, nodes)
    except (StoryGraphError, StoryNodeError) as exc:
        return default_graph(nodes), (str(exc),)
    return graph, ()


def has_cycle(edges: tuple[StoryEdge, ...]) -> bool:
    outgoing: dict[str, list[str]] = {}
    for edge in edges:
        outgoing.setdefault(edge.source, []).append(edge.target)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> bool:
        if node_id in visiting:
            return True
        if node_id in visited:
            return False

        visiting.add(node_id)
        for target in outgoing.get(node_id, []):
            if visit(target):
                return True
        visiting.remove(node_id)
        visited.add(node_id)
        return False

    return any(visit(node_id) for node_id in list(outgoing))


def add_edge(graph: StoryGraph, nodes: list[StoryNode], source: str, target: str) -> StoryGraph:
    next_graph = StoryGraph(
        start=graph.start,
        edges=tuple(sorted(set(graph.edges) | {StoryEdge(source, target)})),
        main_next=dict(graph.main_next),
    )
    validate_graph(next_graph, nodes)
    return next_graph


def remove_edge(graph: StoryGraph, source: str, target: str) -> StoryGraph:
    removed = StoryEdge(source, target)
    main_next = dict(graph.main_next)
    if main_next.get(source) == target:
        del main_next[source]

    return StoryGraph(
        start=graph.start,
        edges=tuple(edge for edge in graph.edges if edge != removed),
        main_next=main_next,
    )


def set_start(graph: StoryGraph, nodes: list[StoryNode], start: str | None) -> StoryGraph:
    next_graph = StoryGraph(start=start, edges=graph.edges, main_next=dict(graph.main_next))
    validate_graph(next_graph, nodes)
    return next_graph


def set_main_next(graph: StoryGraph, nodes: list[StoryNode], source: str, target: str | None) -> StoryGraph:
    main_next = dict(graph.main_next)
    if target is None or target == "":
        main_next.pop(source, None)
    else:
        main_next[source] = target

    next_graph = StoryGraph(start=graph.start, edges=graph.edges, main_next=main_next)
    validate_graph(next_graph, nodes)
    return next_graph


def successors(graph: StoryGraph) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for edge in graph.edges:
        targets = result.setdefault(edge.source, [])
        if edge.target not in targets:
            targets.append(edge.target)

    for source, main_target in graph.main_next.items():
        targets = result.get(source)
        if targets and main_target in targets:
            targets.remove(main_target)
            targets.insert(0, main_target)
    return result


def main_route(graph: StoryGraph) -> list[str]:
    if graph.start is None:
        return []

    route = [graph.start]
    seen = {graph.start}
    current = graph.start

    while current in graph.main_next:
        next_node = graph.main_next[current]
        if next_node in seen:
            break
        route.append(next_node)
        seen.add(next_node)
        current = next_node

    return route


def ordered_nodes(graph: StoryGraph, nodes: list[StoryNode]) -> list[StoryNode]:
    node_by_id = {node.id: node for node in nodes}
    ordered_ids: list[str] = []
    seen: set[str] = set()
    outgoing = successors(graph)

    def visit(node_id: str) -> None:
        if node_id in seen or node_id not in node_by_id:
            return
        seen.add(node_id)
        ordered_ids.append(node_id)
        for target in outgoing.get(node_id, []):
            visit(target)

    if graph.start is not None:
        visit(graph.start)

    for node in nodes:
        visit(node.id)

    return [node_by_id[node_id] for node_id in ordered_ids]
