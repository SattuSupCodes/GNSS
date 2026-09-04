"""Download the IO-VNBD dataset via Git LFS.

The IO-VNBD dataset is publicly hosted on GitHub and stores all CSV files in
Git LFS. Git LFS only stores pointer files when downloaded without the LFS
plugin, so it is essential to clone with Git LFS enabled. This script:

1. Verifies / installs Git LFS.
2. Clones the official repository (github.com/onyekpeu/IO-VNBD) into
   ``data/raw/IO-VNBD`` (matching the layout expected by the Phase 1 loaders).
3. Verifies the download by checking that no remaining LFS pointer files exist.

Usage:
    python scripts/download_dataset.py               # clone to data/raw/IO-VNBD
    python scripts/download_dataset.py --target DIR  # clone to a custom dir

Note:
    data/raw is gitignored, so the downloaded data is never committed to this
    repository. If your working copy already has the dataset flattened directly
    under ``data/raw``, the loaders support that layout too.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/onyekpeu/IO-VNBD.git"
DEFAULT_TARGET = (
    Path(__file__).resolve().parents[1] / "data" / "raw" / "IO-VNBD"
)

# Smallest plausible real CSV size; real data files are tens-hundreds of KB.
# Git LFS pointer files are only ~130 bytes, so anything at or below this
# threshold is almost certainly an unresolved pointer.
LFS_POINTER_SIZE_THRESHOLD = 1000


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    print(f"\n> {' '.join(cmd)}")
    return subprocess.run(cmd, check=True)


def ensure_git_lfs() -> None:
    """Install the Git LFS filter if it is not already present."""
    if shutil.which("git-lfs") is not None:
        print("Git LFS already installed.")
        return
    print("Git LFS not found. Installing the 'lfs' hook via git-lfs.")
    _run(["git", "lfs", "install", "--skip-smudge"])


def sanitize_target(target: Path) -> Path:
    """Return an absolute, expanded target path."""
    return target.expanduser().resolve()


def clone(target: Path) -> None:
    """Clone the repository into `target`, pulling LFS objects."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise SystemExit(
            f"Target already exists: {target}\n"
            "Refusing to overwrite. Remove it manually and re-run if you want a "
            "fresh clone."
        )
    _run(["git", "clone", REPO_URL, str(target)])
    # Explicitly pull LFS objects (belt-and-braces on top of default smudge).
    _run(["git", "-C", str(target), "lfs", "pull"])


def verify(target: Path) -> int:
    """Return the number of leftover LFS pointer files."""
    pointers = [
        p
        for p in target.rglob("*.csv")
        if p.is_file() and p.stat().st_size <= LFS_POINTER_SIZE_THRESHOLD
    ]
    if pointers:
        print(
            f"\nWARNING: {len(pointers)} unresolved LFS pointer(s) found, "
            "e.g.:"
        )
        for p in pointers[:5]:
            print(f"  - {p.relative_to(target)}")
    else:
        print("\nOK: no unresolved LFS pointers found. Dataset is ready.")
    return len(pointers)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        type=Path,
        default=DEFAULT_TARGET,
        help=f"Destination directory (default: {DEFAULT_TARGET})",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip the post-download verification step.",
    )
    args = parser.parse_args()

    target = sanitize_target(args.target)
    print(f"Target directory: {target}")

    ensure_git_lfs()
    clone(target)

    if args.skip_verify:
        return 0
    leftover = verify(target)
    return 1 if leftover else 0


if __name__ == "__main__":
    sys.exit(main())
