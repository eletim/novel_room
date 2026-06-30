from datetime import datetime
from pathlib import Path, PurePosixPath

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for

app = Flask(__name__)

WORKS_ROOT = (Path(__file__).resolve().parent.parent / "works").resolve()
ALLOWED_SUFFIXES = {".txt", ".md"}

WORKS_ROOT.mkdir(parents=True, exist_ok=True)


def normalize_relative_path(raw_path: str | None) -> str:
    raw_path = (raw_path or "").strip().replace("\\", "/")
    if raw_path in {"", "."}:
        return ""

    relative_path = PurePosixPath(raw_path)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        abort(400, description="Invalid path.")

    normalized = relative_path.as_posix()
    return "" if normalized == "." else normalized


def relative_path_for(target: Path) -> str:
    try:
        relative = target.resolve().relative_to(WORKS_ROOT)
    except ValueError:
        abort(400, description="Invalid path.")
    return relative.as_posix() if str(relative) != "." else ""


def resolve_path(raw_path: str | None, *, must_exist: bool = True, expect: str | None = None) -> Path:
    relative_path = normalize_relative_path(raw_path)
    target = (WORKS_ROOT / relative_path).resolve(strict=must_exist)

    try:
        target.relative_to(WORKS_ROOT)
    except ValueError:
        abort(400, description="Invalid path.")

    if must_exist and not target.exists():
        abort(404, description="Path not found.")

    if expect == "dir" and not target.is_dir():
        abort(404, description="Folder not found.")
    if expect == "file" and not target.is_file():
        abort(404, description="File not found.")

    if expect == "file" or (target.exists() and target.is_file()):
        validate_file_type(target.name)

    return target


def validate_file_type(name: str) -> None:
    if Path(name).suffix.lower() not in ALLOWED_SUFFIXES:
        abort(400, description="Only .txt and .md files are supported.")


def validate_name(raw_name: str | None, *, expect_file: bool) -> str:
    name = (raw_name or "").strip()
    if not name:
        abort(400, description="Name cannot be empty.")
    if "/" in name or "\\" in name or name in {".", ".."}:
        abort(400, description="Invalid name.")

    name_path = PurePosixPath(name)
    if len(name_path.parts) != 1:
        abort(400, description="Invalid name.")

    if expect_file:
        validate_file_type(name)

    return name


def get_parent_path(current_path: str) -> str | None:
    current_path = normalize_relative_path(current_path)
    if not current_path:
        return None

    parent = PurePosixPath(current_path).parent.as_posix()
    return "" if parent == "." else parent


def build_child_path(parent_path: str, name: str) -> str:
    parent = PurePosixPath(normalize_relative_path(parent_path))
    child = parent / name
    return child.as_posix() if str(child) != "." else ""


def safe_directory_entries(directory: Path) -> tuple[list[dict], list[dict]]:
    folders = []
    files = []

    for entry in directory.iterdir():
        try:
            resolved = entry.resolve()
            resolved.relative_to(WORKS_ROOT)
        except (FileNotFoundError, RuntimeError, ValueError, OSError):
            continue

        if entry.is_dir():
            folders.append(
                {
                    "name": entry.name,
                    "path": relative_path_for(resolved),
                    "last_modified": datetime.fromtimestamp(entry.stat().st_mtime),
                }
            )
            continue

        if entry.is_file() and entry.suffix.lower() in ALLOWED_SUFFIXES:
            files.append(
                {
                    "name": entry.name,
                    "path": relative_path_for(resolved),
                    "last_modified": datetime.fromtimestamp(entry.stat().st_mtime),
                    "length": len(entry.read_text(encoding="utf-8")),
                }
            )

    folders.sort(key=lambda item: item["name"].lower())
    files.sort(key=lambda item: item["name"].lower())
    return folders, files


def render_folder(current_path: str):
    folder_path = resolve_path(current_path, expect="dir")
    folders, files = safe_directory_entries(folder_path)

    return render_template(
        "index.html",
        current_path=normalize_relative_path(current_path),
        current_name="works" if folder_path == WORKS_ROOT else folder_path.name,
        parent_path=get_parent_path(current_path),
        folders=folders,
        files=files,
        notice=request.args.get("notice", ""),
        error=request.args.get("error", ""),
    )


def redirect_to_folder(current_path: str, *, notice: str = "", error: str = ""):
    normalized_path = normalize_relative_path(current_path)
    endpoint = "index" if normalized_path == "" else "view_folder"
    kwargs = {}
    if normalized_path != "":
        kwargs["path"] = normalized_path
    if notice:
        kwargs["notice"] = notice
    if error:
        kwargs["error"] = error
    return redirect(url_for(endpoint, **kwargs))


@app.route("/")
def index():
    return render_folder("")


@app.route("/folder")
def view_folder():
    return render_folder(request.args.get("path", ""))


@app.route("/edit")
def edit_file():
    raw_path = request.args.get("path", "")
    file_path = resolve_path(raw_path, expect="file")
    content = file_path.read_text(encoding="utf-8")

    return render_template(
        "editor.html",
        file_path=relative_path_for(file_path),
        file_name=file_path.name,
        folder_path=get_parent_path(relative_path_for(file_path)) or "",
        content=content,
        length=len(content),
        last_modified=datetime.fromtimestamp(file_path.stat().st_mtime),
    )


@app.route("/save", methods=["POST"])
def save():
    payload = request.get_json(silent=True) or {}
    raw_path = payload.get("path", "")
    content = payload.get("content")

    if not isinstance(content, str):
        abort(400, description="Content must be a string.")

    file_path = resolve_path(raw_path, expect="file")
    file_path.write_text(content, encoding="utf-8")

    return jsonify(
        {
            "message": "File saved successfully.",
            "length": len(content),
            "last_modified": datetime.fromtimestamp(file_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        }
    )


@app.route("/create_file", methods=["POST"])
def create_file():
    current_path = request.form.get("current_path", "")
    directory = resolve_path(current_path, expect="dir")
    file_name = validate_name(request.form.get("name"), expect_file=True)
    new_file = resolve_path(build_child_path(relative_path_for(directory), file_name), must_exist=False)

    if new_file.exists():
        return redirect_to_folder(current_path, error="File already exists.")

    new_file.write_text("", encoding="utf-8")
    return redirect(url_for("edit_file", path=relative_path_for(new_file)))


@app.route("/create_folder", methods=["POST"])
def create_folder():
    current_path = request.form.get("current_path", "")
    directory = resolve_path(current_path, expect="dir")
    folder_name = validate_name(request.form.get("name"), expect_file=False)
    new_folder = resolve_path(build_child_path(relative_path_for(directory), folder_name), must_exist=False)

    if new_folder.exists():
        return redirect_to_folder(current_path, error="Folder already exists.")

    new_folder.mkdir()
    return redirect_to_folder(relative_path_for(new_folder), notice="Folder created.")


@app.route("/rename", methods=["POST"])
def rename_entry():
    current_path = request.form.get("current_path", "")
    original_path = request.form.get("path", "")
    target = resolve_path(original_path)
    is_directory = target.is_dir()
    new_name = validate_name(request.form.get("new_name"), expect_file=not is_directory)
    destination_relative = build_child_path(get_parent_path(relative_path_for(target)) or "", new_name)
    destination = resolve_path(destination_relative, must_exist=False)

    if destination == target:
        return redirect_to_folder(current_path, notice="Name unchanged.")
    if destination.exists():
        return redirect_to_folder(current_path, error="Target name already exists.")

    target.rename(destination)

    if is_directory and normalize_relative_path(current_path) == normalize_relative_path(original_path):
        return redirect_to_folder(relative_path_for(destination), notice="Folder renamed.")

    return redirect_to_folder(current_path, notice="Renamed successfully.")


@app.route("/delete", methods=["POST"])
def delete_entry():
    current_path = request.form.get("current_path", "")
    raw_path = request.form.get("path", "")
    target = resolve_path(raw_path)

    if target.is_dir():
        try:
            target.rmdir()
        except OSError:
            return redirect_to_folder(current_path, error="Folder must be empty before deletion.")
        return redirect_to_folder(current_path, notice="Folder deleted.")

    target.unlink()
    return redirect_to_folder(current_path, notice="File deleted.")


@app.errorhandler(400)
@app.errorhandler(404)
def handle_error(error):
    return render_template("error.html", code=error.code, message=error.description), error.code


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
