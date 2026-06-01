#!/usr/bin/env python3
"""Preserve felix-rub Railway Dockerfile invariants after upstream syncs.

The public fork deploys directly to Railway. Upstream owns the Dockerfile, so
scheduled syncs should take upstream's Docker architecture and re-apply only the
small Railway-specific runtime contract:

* do not declare /opt/data as a Docker VOLUME (Railway volume handling differs)
* run the s6-supervised dashboard on Railway's public target port 9119
* keep the container's main process alive while s6 services serve traffic
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


RAILWAY_ENV_COMMENT = (
    "# Railway's public domain is wired to target port 9119. Let the upstream\n"
    "# s6-supervised dashboard own that port and keep the container's main process\n"
    "# as a simple lifetime keeper.\n"
)
RAILWAY_ENV_BLOCK = (
    f"{RAILWAY_ENV_COMMENT}"
    "ENV HERMES_DASHBOARD=1\n"
    "ENV HERMES_DASHBOARD_HOST=0.0.0.0\n"
    "ENV HERMES_DASHBOARD_PORT=9119\n"
    "ENV HERMES_DASHBOARD_INSECURE=1\n"
)
RAILWAY_COMMENT = (
    "# Railway serves the s6-supervised dashboard on port 9119. Keep the main\n"
    "# program alive so /init does not enter shutdown while s6 services run.\n"
)
RAILWAY_CMD = 'CMD ["sleep", "infinity"]'
RAILWAY_BLOCK = f"{RAILWAY_COMMENT}{RAILWAY_CMD}\n"

LEGACY_RAILWAY_COMMENT = (
    "# Railway deploys the container as a long-running service; keep the main process\n"
    "# alive while s6-supervised services start and run in the background.\n"
)
LEGACY_RAILWAY_CMD = 'CMD ["sleep", "infinity"]'
LEGACY_DASHBOARD_COMMENT = (
    "# Railway serves the dashboard from the container's main process and injects\n"
    "# PORT at runtime. Use sh -c so ${PORT:-9119} is expanded after deployment.\n"
)
LEGACY_DASHBOARD_CMD = (
    'CMD ["sh", "-c", '
    '"exec hermes dashboard --host 0.0.0.0 --port ${PORT:-9119} --no-open --insecure"]'
)


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
    # version. This keeps the script idempotent across repeated sync runs and
    # cleanly migrates the previous sleep-infinity keepalive block.
    for managed_comment, managed_cmd in (
        (RAILWAY_COMMENT, RAILWAY_CMD),
        (LEGACY_RAILWAY_COMMENT, LEGACY_RAILWAY_CMD),
        (LEGACY_DASHBOARD_COMMENT, LEGACY_DASHBOARD_CMD),
    ):
        escaped_comment = re.escape(managed_comment)
        escaped_cmd = re.escape(managed_cmd)
        text = re.sub(
            rf"(?m){escaped_comment}{escaped_cmd}\s*\r?\n",
            "",
            text,
        )

    text = re.sub(
        rf"(?m){re.escape(RAILWAY_ENV_COMMENT)}"
        r"ENV HERMES_DASHBOARD=1\r?\n"
        r"ENV HERMES_DASHBOARD_HOST=0\.0\.0\.0\r?\n"
        r"ENV HERMES_DASHBOARD_PORT=9119\r?\n"
        r"ENV HERMES_DASHBOARD_INSECURE=1\r?\n",
        "",
        text,
    )

    home_env = "ENV HERMES_HOME=/opt/data\n"
    if home_env in text:
        text = text.replace(home_env, f"{home_env}\n{RAILWAY_ENV_BLOCK}", 1)
        text = text.replace(f"{RAILWAY_ENV_BLOCK}\n\n", f"{RAILWAY_ENV_BLOCK}\n", 1)
    else:
        text = f"{RAILWAY_ENV_BLOCK}\n{text}"

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