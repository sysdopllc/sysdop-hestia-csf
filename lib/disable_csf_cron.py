#!/usr/bin/env python3
"""Comment active CSF/LFD updater or restart entries without deleting history."""

from __future__ import annotations

import sys
from pathlib import Path


MARKER = "# SYSDOP disabled with CSF/LFD: "


def patch(path: Path) -> None:
    if not path.exists():
        return
    original = path.read_text(encoding="utf-8")
    output: list[str] = []
    for line in original.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped and not stripped.startswith("#") and (
            "/usr/sbin/csf" in line
            or "/usr/sbin/lfd" in line
            or "csget" in line.lower()
        ):
            newline = "\n" if line.endswith("\n") else ""
            output.append(MARKER + line.rstrip("\n") + newline)
        else:
            output.append(line)
    rendered = "".join(output)
    if rendered != original:
        path.write_text(rendered, encoding="utf-8")


def main() -> int:
    for name in sys.argv[1:]:
        patch(Path(name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
