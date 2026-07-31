#!/usr/bin/env python3
# show-logfiles.py
"""Interactively browse log files matching a pattern in a directory."""

import fnmatch
import sys
from pathlib import Path
from typing import List

try:
    import termios
    import tty

    # For arrow key handling (POSIX only)
    HAS_UNIX_KEYS = True
except ImportError:
    HAS_UNIX_KEYS = False


def clear_screen() -> None:
    """Clear the terminal screen and move cursor to top-left."""
    # ANSI escape codes: clear screen + move cursor home
    print("\033[2J\033[H", end="")


def get_keypress() -> str:
    """Get a single keypress (arrow keys, Enter, etc.)."""
    if not HAS_UNIX_KEYS:
        input("Press Enter to continue...")
        return "enter"

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":  # ESC
            ch += sys.stdin.read(2)
            if ch == "\x1b[A":
                return "up"
            if ch == "\x1b[B":
                return "down"
            if ch == "\x1b[C":
                return "right"
            if ch == "\x1b[D":
                return "left"
        if ch in ("\r", "\n"):
            return "enter"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def find_logfiles(path: Path, pattern: str) -> List[Path]:
    """Find files matching pattern (supports *? glob wildcards or regex)."""
    if not path.is_dir():
        print(f"❌ Path is not a directory: {path}")
        return []

    files = []
    for item in path.rglob("*"):
        if item.is_file():
            # Try fnmatch first (wildcards like *.log)
            if fnmatch.fnmatch(item.name, pattern):
                files.append(item)
                continue
            # Fallback: try regex
            import re

            try:
                if re.search(pattern, str(item)):
                    files.append(item)
            except re.error:
                pass  # skip invalid regex

    return sorted(files)


def show_file(filepath: Path) -> None:
    """Print filename and content."""
    clear_screen()
    print("=" * 80)
    print(f"📄 {filepath}")
    print("=" * 80)
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
        print(content)
    except Exception as e:
        print(f"Error reading file: {e}")
    print("=" * 80)


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python show-logfiles.py <path> <pattern>")
        print("Example: python show-logfiles.py ./logs '*.log'")
        sys.exit(1)

    log_path = Path(sys.argv[1]).resolve()
    pattern = sys.argv[2]

    files = find_logfiles(log_path, pattern)
    if not files:
        print(f"No matching files found for pattern '{pattern}' in {log_path}")
        sys.exit(0)

    # Show intro before first file
    print(f"✅ Found {len(files)} matching file(s). Press:")
    print("   ➡️  Enter, Right Arrow: next")
    print("   ⬅️  Left Arrow: previous")
    print("   ⏏️  Ctrl-C to quit")
    input("\nPress Enter to start browsing...")

    idx = 0
    while True:
        show_file(files[idx])
        print(f"[{idx + 1}/{len(files)}] [Enter/→] Next | [←] Prev | [Ctrl-C] Exit")

        try:
            key = get_keypress().lower()
        except KeyboardInterrupt:
            print("\n\nExiting gracefully...")
            break

        if key in ("enter", "right"):
            idx = (idx + 1) % len(files)
        elif key == "left":
            idx = (idx - 1) % len(files)
        # Ignore other keys silently


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting gracefully...")
        sys.exit(0)
