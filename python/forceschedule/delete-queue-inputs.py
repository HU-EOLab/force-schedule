#!/usr/bin/env python3
# delete-level0-inputs.py
"""Delete Sentinel-2 Level-0 input folders listed in a queue file, based on their status."""

import argparse
import shutil
from pathlib import Path
from typing import Dict, List


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Delete Sentinel-2 Level-0 input folders from a status queue file."
    )
    parser.add_argument(
        "path_queue",
        type=Path,
        help="Path to queue.txt file containing lines like: <path> DONE|FAIL|...",
    )
    parser.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        help="Only print folders that would be deleted, without actually deleting them.",
    )
    parser.add_argument(
        "-f",
        "--failed",
        action="store_true",
        help="Also delete folders with status 'FAIL'.",
    )
    parser.add_argument(
        "-q",
        "--queued",
        action="store_true",
        help="Also delete folders with status 'QUEUED' (i.e., no status word).",
    )
    return parser.parse_args()


def read_queue(path_queue: Path) -> Dict[str, List[Path]]:
    """
    Read the queue file and return it as Dict with lists by status

    Expected lines: /path/to/folder STATUS
    Empty lines and malformed lines are skipped.
    """

    if not path_queue.exists():
        raise FileNotFoundError(f"Queue file not found: {path_queue}")

    results = {c: [] for c in ["DONE", "FAIL", "QUEUED"]}

    for i, line in enumerate(path_queue.read_text().splitlines()):
        line = line.strip()
        if not line:
            continue
        parts = line.rsplit(maxsplit=1)
        if len(parts) != 2:
            raise Exception(f"Malformed line in {path_queue}: {i + 1}: {line}")

        folder_path, status = parts
        status_files = results.get(status, [])
        status_files.append(Path(folder_path))
        results[status] = status_files
    return results


def delete_inputs(
    path_queue: Path,
    delete_failed: bool = False,
    delete_queued: bool = False,
    dry_run: bool = False,
) -> None:
    """Process queue and delete folders ending with 'DONE' status."""
    entries = read_queue(path_queue)

    to_delete = ["DONE"]
    if delete_failed:
        to_delete.append("FAIL")
    if delete_queued:
        to_delete.append("QUEUED")

    info = [f"Queue Status: {path_queue}"]
    for status, e in entries.items():
        info.append(f"{status}: {len(e)}")

    print("\n".join(info))

    for status, files in entries.items():
        if status in to_delete:
            for path in files:
                if not path.exists():
                    print(f"Does not exists: {path} ({status})")
                    continue
                if dry_run:
                    print(f"Would delete {path} ({status})")
                else:
                    print(f"Delete {path}")
                    if path.is_dir():
                        shutil.rmtree(path)
                    elif path.is_file():
                        path.unlink()


def main() -> None:
    args = parse_args()
    delete_inputs(
        args.path_queue,
        dry_run=args.dry_run,
        delete_failed=args.failed,
        delete_queued=args.queued,
    )


if __name__ == "__main__":
    main()
