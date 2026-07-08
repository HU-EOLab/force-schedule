#!/usr/bin/env python3
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional, Union, List

from tqdm import tqdm


def is_failed(file_path: Path) -> bool:
    """Read a log file and return its status.

    Reads bytes and searches for markers directly to avoid the cost of
    decoding the whole file to text.
    """
    content = file_path.read_text().lower()
    keywords = ['success', 'skip', 'coreg failed', 'coregistration failed']
    for k in keywords:
        if k in content:
            return False
    return True


def rename_logs_process(file_path: Path, dry_run: bool) -> Optional[Path]:
    """Classify a single log file and rename it to .fail if it failed.

    Returns the renamed path on failure, otherwise None. Runs in a worker
    thread (only filesystem I/O, no shared state).
    """
    try:
        if is_failed(file_path):
            new_path = file_path.with_suffix(".fail")
            if not dry_run:
                file_path.rename(new_path)
            return new_path
        else:
            return None
    except Exception as e:
        tqdm.write(f"Could not process file {file_path.name}: {e}")
        return None


def rename_logs(
    dir_log: Union[str, Path],
    queue_file: Optional[Union[str, Path]] = None,
    n_workers: int = 8,
    dry_run: bool = False,
) -> List[Path]:
    """Scan the directory for .log files, check their content,
    and rename failed runs to .fail. Files are read in parallel using
    ``n_workers`` threads.
    """
    dir_log = Path(dir_log)
    if not dir_log.is_dir():
        raise NotADirectoryError(f"{dir_log} is not a valid directory.")

    print(f"LOG DIR={dir_log.resolve()}")

    # Scan for .log files
    flog = list(dir_log.glob("*.log"))

    if queue_file is not None:
        queue_file = Path(queue_file)
        if not queue_file.is_file():
            raise FileNotFoundError(f"{queue_file} is not a valid file.")

        print(f"QUEUE FILE={queue_file.resolve()}")

        requested_logs = []

        for line in queue_file.read_text().splitlines():
            requested_logs.append(Path(line.split()[0]).name + '.log')
        flog = [p for p in flog if p.name in requested_logs]
        if len(flog) == 0:
            print(f"No *.log files found related to inputs listed in {queue_file}")
            return []

    desc = "Checking logs (dry-run)" if dry_run else "Renaming failed logs"
    failed_logs = []
    with ThreadPoolExecutor(max_workers=max(1, n_workers)) as executor:
        results = executor.map(lambda p: rename_logs_process(p, dry_run), flog)
        for new_path in tqdm(results, total=len(flog), desc=desc):
            if new_path is not None:
                failed_logs.append(new_path)

    print(f"Failed: {len(failed_logs)}")
    return failed_logs


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
