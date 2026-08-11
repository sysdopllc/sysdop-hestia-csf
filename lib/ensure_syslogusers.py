#!/usr/bin/env python3
"""Merge only existing Hestia service accounts into csf.syslogusers."""

from __future__ import annotations

import argparse
import pwd
from pathlib import Path


CANDIDATES = (
    "root",
    "daemon",
    "messagebus",
    "syslog",
    "_chrony",
    "chrony",
    "bind",
    "named",
    "mysql",
    "Debian-exim",
    "postfix",
    "dovecot",
    "dovenull",
    "hestiamail",
    "hestiaweb",
)


def passwd_users(root: Path) -> set[str]:
    if root == Path("/"):
        return {entry.pw_name for entry in pwd.getpwall()}
    path = root / "etc/passwd"
    if not path.exists():
        return set()
    return {
        line.split(":", 1)[0]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#") and ":" in line
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("/"))
    parser.add_argument("--file", type=Path, required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    path = args.file
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    active = {
        line.strip()
        for line in original.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    additions = [
        user for user in CANDIDATES if user in passwd_users(root) and user not in active
    ]
    if additions:
        separator = "" if not original or original.endswith("\n") else "\n"
        block = "\n# Hestia service accounts merged by SYSDOP\n" + "\n".join(additions) + "\n"
        path.write_text(original + separator + block, encoding="utf-8")
        path.chmod(0o600)
    print("added=" + ",".join(additions))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
