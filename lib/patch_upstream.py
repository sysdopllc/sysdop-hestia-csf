#!/usr/bin/env python3
"""Apply the minimal safety delta to the pinned generic CSF installer."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


EXPECTED_VERSION = "15.10"
MARKER = "SYSDOP_Hestia_safety_patch_v1"

ORIGINAL = """\tinfo \"    Enabling systemctl services ${bluel}csf.service${greym} and ${bluel}lfd.service${greym}\"
    run systemctl enable csf.service
    run systemctl enable lfd.service

\tinfo \"    Disabling systemctl service ${bluel}firewalld${greym}\"
    run systemctl disable firewalld
    run systemctl stop firewalld
    run systemctl mask firewalld
"""

REPLACEMENT = f"""\t# {MARKER}
\tinfo \"    SYSDOP safety: leaving CSF/LFD disabled and firewalld untouched\"
    run systemctl disable csf.service
    run systemctl disable lfd.service
"""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    args = parser.parse_args()

    source = args.source.resolve()
    version = (source / "version.txt").read_text(encoding="utf-8").strip()
    if version != EXPECTED_VERSION:
        raise SystemExit(f"unsupported upstream version: {version!r}")

    installer = source / "install.generic.sh"
    text = installer.read_text(encoding="utf-8")
    if MARKER in text:
        patched = text
    else:
        count = text.count(ORIGINAL)
        if count != 1:
            raise SystemExit(
                "upstream installer safety block changed; refusing an unreviewed install"
            )
        patched = text.replace(ORIGINAL, REPLACEMENT)
        installer.write_text(patched, encoding="utf-8")

    forbidden = (
        "systemctl enable csf.service",
        "systemctl enable lfd.service",
        "systemctl disable firewalld",
        "systemctl stop firewalld",
        "systemctl mask firewalld",
    )
    leftovers = [needle for needle in forbidden if needle in patched]
    if leftovers:
        raise SystemExit(f"unsafe upstream actions remain: {', '.join(leftovers)}")

    print(f"patched={installer}")
    print(f"sha256={sha256(installer)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
