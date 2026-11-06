import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

CATEGORY_MAP = {
    ".txt": "Documents",
    ".docx": "Documents",
    ".pdf": "Documents",
    ".md": "Documents",
    ".csv": "Data",
    ".json": "Data",
    ".xlsx": "Data",
    ".py": "Code",
    ".sh": "Code",
    ".cpp": "Code",
    ".zip": "Archives",
    ".tar": "Archives",
    ".gz": "Archives",
}

from pathlib import Path
import json
import shutil

def restore_from_trash(filename: str, trash_dir: str = ".aether_trash") -> dict[str, str]:
    """Restores a trashed file back to its original path using `manifest.json`."""
    trash_path = Path(trash_dir).resolve()
    manifest_file = trash_path / "manifest.json"

    if not manifest_file.exists():
        raise FileNotFoundError("Trash manifest does not exist.")

    manifest: dict[str, str] = json.loads(
        manifest_file.read_text(encoding="utf-8")
    )
    if filename not in manifest:
        raise KeyError(f"'{filename}' not found in trash manifest.")

    trashed_file = trash_path / filename
    if not trashed_file.exists():
        raise FileNotFoundError(
            f"Trashed payload missing on disk: {trashed_file}"
        )

    original_dest = Path(manifest[filename])
    original_dest.parent.mkdir(parents=True, exist_ok=True)

    # Transactional Restore
    shutil.move(str(trashed_file), str(original_dest))

    manifest.pop(filename)

    manifest_file.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8"
    )

    return {
        "status": "restored",
        "filename": filename,
        "restored_to": str(original_dest),
    }

def compute_file_sha256(filepath: Path) -> str:
    """Computes the SHA-256 hash of a file's contents in 64KB chunks."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def scan_directory_summary(target_dir: str) -> list[dict[str, Any]]:
    """Returns metadata (name, path, extension, size_bytes) for all top-level files in target_dir."""
    root = Path(target_dir)
    if not root.exists():
        return []

    files_info = []
    for item in sorted(root.iterdir()):
        if item.is_file():
            files_info.append({
                "name": item.name,
                "path": str(item),
                "extension": item.suffix.lower(),
                "size_bytes": item.stat().st_size,
            })
    return files_info


def find_duplicate_files(target_dir: str) -> list[str]:
    """Finds exact duplicate files in target_dir using SHA-256 content hashing.
    Returns a list of filepaths that are redundant duplicates (keeping the first seen file).
    """
    root = Path(target_dir)
    seen_hashes: dict[str, str] = {}
    duplicates: list[str] = []

    for item in sorted(root.iterdir()):
        if item.is_file():
            file_hash = compute_file_sha256(item)
            if file_hash in seen_hashes:
                duplicates.append(str(item))
            else:
                seen_hashes[file_hash] = str(item)
    return duplicates


def safe_delete_file(filepath: str, trash_dir: str = ".aether_trash") -> dict[str, str]:
    """Moves a file to `trash_dir` instead of permanently deleting it, recording its original path."""
    src = Path(filepath).resolve()
    if not src.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    trash_path = Path(trash_dir).resolve()
    trash_path.mkdir(parents=True, exist_ok=True)

    dest = trash_path / src.name
    manifest_file = trash_path / "manifest.json"

    manifest = {}
    if manifest_file.exists():
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))

    shutil.move(str(src), str(dest))
    manifest[src.name] = str(src)
    manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"status": "trashed", "original_path": str(src), "trash_path": str(dest)}


def auto_organize_directory(target_dir: str) -> dict[str, list[str]]:
    """Sorts top-level files in `target_dir` into subfolders based on `CATEGORY_MAP`."""
    root = Path(target_dir)
    moved_summary: dict[str, list[str]] = {}

    for item in sorted(root.iterdir()):
        if item.is_file():
            category = CATEGORY_MAP.get(item.suffix.lower(), "Misc")
            dest_folder = root / category
            dest_folder.mkdir(exist_ok=True)
            dest_path = dest_folder / item.name
            shutil.move(str(item), str(dest_path))
            moved_summary.setdefault(category, []).append(item.name)

    return moved_summary


if __name__ == "__main__":
    sandbox = Path("sandbox_dir")
    if sandbox.exists():
        shutil.rmtree(sandbox)
    sandbox.mkdir(exist_ok=True)

    (sandbox / "notes_v1.txt").write_text("Linux OS Agent spec v1", encoding="utf-8")
    (sandbox / "notes_copy_duplicate.txt").write_text("Linux OS Agent spec v1", encoding="utf-8")
    (sandbox / "metrics.csv").write_text("epoch,loss\n1,0.42", encoding="utf-8")
    (sandbox / "deploy.sh").write_text("#!/bin/bash\necho 'ready'", encoding="utf-8")

    print("📂 1. Initial Scan:", [f["name"] for f in scan_directory_summary("sandbox_dir")])

    dups = find_duplicate_files("sandbox_dir")
    print("🔍 2. Exact SHA-256 Duplicates Found:", dups)

    for d in dups:
        print("🗑️  3. Safe-Deleting Duplicate:", safe_delete_file(d))

    organized = auto_organize_directory("sandbox_dir")
    print("✨ 4. Auto-Organized Remaining Files:", organized)