#!/usr/bin/env python3
"""Preserve felix-rub Railway Dockerfile invariants after upstream syncs.

The public fork deploys directly to Railway. Upstream owns the Dockerfile, so
scheduled syncs should take upstream's Docker architecture and re-apply only the
small Railway-specific runtime contract:

* do not declare /opt/data as a Docker VOLUME (Railway volume handling differs)
* keep the container's main process alive with sleep infinity while supervised
  services run in the background
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


RAILWAY_COMMENT = (
    "# Railway deploys the container as a long-running service; keep the main process\n"
    "# alive while s6-supervised services start and run in the background.\n"
)
RAILWAY_CMD = 'CMD ["sleep", "infinity"]'
RAILWAY_BLOCK = f"{RAILWAY_COMMENT}{RAILWAY_CMD}\n"


def apply_railway_patch(dockerfile: Path) -> bool:
    """Apply Railway runtime invariants to *dockerfile*.

    Returns True when the file changed.
    """

    original = dockerfile.read_text(encoding="utf-8")
    text = original

    # Upstream image metadata should not force /opt/data into a Docker-managed
    # anonymous volume on Railway.
    text = re.sub(
        r'(?m)^\s*VOLUME\s+\[\s*["\']/opt/data["\']\s*\]\s*\r?\n',
        "",
        text,
    )

    # Remove any older copy of our managed block before inserting the canonical
    # version. This keeps the script idempotent across repeated sync runs.
    escaped_comment = re.escape(RAILWAY_COMMENT)
    escaped_cmd = re.escape(RAILWAY_CMD)
    text = re.sub(
        rf"(?m){escaped_comment}{escaped_cmd}\s*\r?\n",
        "",
        text,
    )

    cmd_matches = list(re.finditer(r"(?m)^CMD\s+.*$", text))
    if cmd_matches:
        last_cmd = cmd_matches[-1]
        line_end = text.find("\n", last_cmd.end())
        if line_end == -1:
            line_end = len(text)
            newline = "\n"
        else:
            line_end += 1
            newline = ""
        text = text[: last_cmd.start()] + RAILWAY_BLOCK + newline + text[line_end:]
    else:
        if not text.endswith("\n"):
            text += "\n"
        text += RAILWAY_BLOCK

    if text != original:
        dockerfile.write_text(text, encoding="utf-8", newline="")
        return True
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "dockerfile",
        nargs="?",
        default="Dockerfile",
        type=Path,
        help="Dockerfile path to patch (default: ./Dockerfile)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the Dockerfile is not already patched",
    )
    args = parser.parse_args(argv)

    if not args.dockerfile.exists():
        print(f"error: {args.dockerfile} does not exist", file=sys.stderr)
        return 2

    changed = apply_railway_patch(args.dockerfile)
    if args.check and changed:
        print(f"error: {args.dockerfile} required Railway patch changes", file=sys.stderr)
        return 1

    print("updated" if changed else "already patched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())