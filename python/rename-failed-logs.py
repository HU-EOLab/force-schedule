#!/usr/bin/env python3
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional, Union

from tqdm import tqdm


def classify(file_path: Path) -> str:
    """Read a log file and return its status.

    Reads bytes and searches for markers directly to avoid the cost of
    decoding the whole file to text.
    """
    content = file_path.read_bytes()
    if b"Success" in content:
        return "Success"
    elif b"Skip" in content:
        return "Too cloudy"
    elif b"coreg failed" in content or b"Coregistration failed" in content:
        return "Coregistration failed"
    else:
        return "Error"


def _process(file_path: Path, dry_run: bool) -> Optional[Path]:
    """Classify a single log file and rename it to .fail if it failed.

    Returns the renamed path on failure, otherwise None. Runs in a worker
    thread (only filesystem I/O, no shared state).
    """
    try:
        if classify(file_path) != "Error":
            return None
        new_path = file_path.with_suffix(".fail")
        if not dry_run:
            file_path.rename(new_path)
        return new_path
    except Exception as e:
        tqdm.write(f"Could not process file {file_path.name}: {e}")
        return None


def rename_logs(
    dlog: Union[str, Path],
    n_workers: int = 8,
    dry_run: bool = False,
) -> None:
    """Scan the directory for .log files, check their contents,

    and rename failed runs to .fail. Files are read in parallel using
    ``n_workers`` threads.
    """
    dlog_path = Path(dlog)

    if not dlog_path.is_dir():
        print(f"Error: {dlog_path} is not a valid directory.")
        return

    print(f"LOG DIR={dlog_path.resolve()}")

    # Scan for .log files
    flog = list(dlog_path.glob("*.log"))
    nfail = 0

    desc = "Checking logs (dry-run)" if dry_run else "Renaming failed logs"
    with ThreadPoolExecutor(max_workers=max(1, n_workers)) as executor:
        results = executor.map(lambda p: _process(p, dry_run), flog)
        for new_path in tqdm(results, total=len(flog), desc=desc):
            if new_path is not None:
                nfail += 1

    print(f"Failed: {nfail}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scan log directory and rename failed log files to .fail"
    )
    parser.add_argument(
        "dlog",
        type=str,
        help="Path to the directory containing the .log files",
    )
    parser.add_argument(
        "-j", "--workers",
        type=int,
        default=8,
        help="Number of worker threads used to read log files (default: 8)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report which files would be renamed, without renaming",
    )

    args = parser.parse_args()
    rename_logs(args.dlog, n_workers=args.workers, dry_run=args.dry_run)
