import json
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path


REQUIRED_NODE_FILES = ("main.md", "manifest.json")
OPTIONAL_NODE_FILES = ("free_memo.md", "illust.png")
DEFAULT_NODE_STATUS = "draft"


class StoryNodeError(ValueError):
    pass


@dataclass(frozen=True)
class NodeManifest:
    id: str
    title: str
    status: str


@dataclass(frozen=True)
class StoryNode:
    id: str
    title: str
    status: str
    folder_name: str
    path: str
    main_path: str
    manifest_path: str
    optional_files: tuple[str, ...]


@dataclass(frozen=True)
class NodeInspection:
    folder_name: str
    path: str
    is_node: bool
    manifest: NodeManifest | None
    missing_required: tuple[str, ...]
    errors: tuple[str, ...]
    optional_files: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return self.is_node and not self.errors and not self.missing_required


def relative_path_for(root: Path, target: Path) -> str:
    relative = target.resolve().relative_to(root.resolve())
    return relative.as_posix() if str(relative) != "." else ""


def read_manifest(node_dir: Path) -> NodeManifest:
    manifest_path = node_dir / "manifest.json"
    try:
        raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StoryNodeError("manifest.json is missing.") from exc
    except JSONDecodeError as exc:
        raise StoryNodeError(f"manifest.json is invalid JSON: {exc.msg}.") from exc

    if not isinstance(raw_manifest, dict):
        raise StoryNodeError("manifest.json must contain a JSON object.")

    node_id = raw_manifest.get("id")
    title = raw_manifest.get("title", "")
    status = raw_manifest.get("status", DEFAULT_NODE_STATUS)

    if not isinstance(node_id, str) or not node_id.strip():
        raise StoryNodeError("manifest.id must be a non-empty string.")
    if not isinstance(title, str):
        raise StoryNodeError("manifest.title must be a string when present.")
    if not isinstance(status, str) or not status.strip():
        raise StoryNodeError("manifest.status must be a non-empty string.")

    return NodeManifest(id=node_id.strip(), title=title.strip(), status=status.strip())


def inspect_node_folder(root: Path, folder: Path) -> NodeInspection:
    missing_required = tuple(name for name in REQUIRED_NODE_FILES if not (folder / name).is_file())
    errors: list[str] = []
    manifest = None

    if (folder / "manifest.json").is_file():
        try:
            manifest = read_manifest(folder)
        except StoryNodeError as exc:
            errors.append(str(exc))

    optional_files = tuple(name for name in OPTIONAL_NODE_FILES if (folder / name).exists())

    return NodeInspection(
        folder_name=folder.name,
        path=relative_path_for(root, folder),
        is_node=not missing_required and manifest is not None and not errors,
        manifest=manifest,
        missing_required=missing_required,
        errors=tuple(errors),
        optional_files=optional_files,
    )


def load_node(root: Path, node_dir: Path) -> StoryNode:
    if not node_dir.is_dir():
        raise StoryNodeError("Node folder not found.")

    missing_required = [name for name in REQUIRED_NODE_FILES if not (node_dir / name).is_file()]
    if missing_required:
        raise StoryNodeError(f"Required file is missing: {', '.join(missing_required)}.")

    manifest = read_manifest(node_dir)
    optional_files = tuple(name for name in OPTIONAL_NODE_FILES if (node_dir / name).exists())
    node_path = relative_path_for(root, node_dir)

    return StoryNode(
        id=manifest.id,
        title=manifest.title,
        status=manifest.status,
        folder_name=node_dir.name,
        path=node_path,
        main_path=relative_path_for(root, node_dir / "main.md"),
        manifest_path=relative_path_for(root, node_dir / "manifest.json"),
        optional_files=optional_files,
    )


def list_nodes(root: Path, work_dir: Path) -> list[StoryNode]:
    nodes = []
    for child in work_dir.iterdir():
        if child.is_dir():
            try:
                nodes.append(load_node(root, child))
            except StoryNodeError:
                continue
    return sorted(nodes, key=lambda node: node.id.lower())


def create_node(root: Path, parent_dir: Path, folder_name: str, *, title: str | None = None) -> StoryNode:
    if not folder_name or "/" in folder_name or "\\" in folder_name or folder_name in {".", ".."}:
        raise StoryNodeError("Invalid node folder name.")

    node_dir = parent_dir / folder_name
    if node_dir.exists():
        raise StoryNodeError("Node folder already exists.")

    node_title = folder_name if title is None or title.strip() == "" else title.strip()
    node_dir.mkdir()
    (node_dir / "main.md").write_text("", encoding="utf-8")
    manifest = {
        "id": folder_name,
        "title": node_title,
        "status": DEFAULT_NODE_STATUS,
    }
    (node_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return load_node(root, node_dir)
