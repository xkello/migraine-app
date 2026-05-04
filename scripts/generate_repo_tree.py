"""Generate repository tree from non-ignored files (git-aware)."""
from __future__ import annotations

import subprocess
from pathlib import PurePosixPath, Path


def list_non_ignored_files() -> list[str]:
    """Return git-tracked + untracked files that are not ignored by gitignore."""
    res = subprocess.run(
        ["git", "--no-pager", "ls-files", "-co", "--exclude-standard"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in res.stdout.splitlines() if line.strip()]


def build_tree_lines(paths: list[str], repo_name: str = "migraine-app") -> list[str]:
    """Convert flat file paths into an indented tree representation."""
    root: dict[str, dict] = {}

    for p in sorted(paths):
        parts = PurePosixPath(p).parts
        cur = root
        for part in parts:
            cur = cur.setdefault(part, {})

    lines = [f"- {repo_name}\\"]

    def walk(node: dict[str, dict], depth: int) -> None:
        items = sorted(node.items(), key=lambda kv: (0 if kv[1] else 1, kv[0].lower()))
        indent = "  " * depth
        for name, child in items:
            if child:
                lines.append(f"{indent}- {name}\\")
                walk(child, depth + 1)
            else:
                lines.append(f"{indent}- {name}")

    walk(root, 1)
    return lines


def main() -> None:
    """Generate `REPO_TREE.txt` in repository root and print a short preview."""
    repo_root = Path(__file__).resolve().parent.parent
    paths = list_non_ignored_files()
    lines = build_tree_lines(paths, repo_name=repo_root.name)

    out_file = repo_root / "REPO_TREE.txt"
    out_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Generated {out_file} ({len(lines)} lines)")
    print("Preview:")
    for line in lines[:30]:
        print(line)


if __name__ == "__main__":
    main()

