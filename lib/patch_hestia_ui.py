#!/usr/bin/env python3
"""Install the Aetherinox UI assets and the Hestia-specific integration."""

from __future__ import annotations

import argparse
import os
import re
import shutil
from pathlib import Path

from hestia_profile import discover, rooted


PANEL_MARKER = "<!-- SYSDOP Hestia CSF integration -->"
REGEX_BEGIN = "\t# SYSDOP_HESTIA_REGEX_BEGIN"
REGEX_END = "\t# SYSDOP_HESTIA_REGEX_END"


def install_file(source: Path, destination: Path, mode: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    os.chmod(destination, mode)


def repair_nested_csf_link(text: str) -> str:
    """Remove only a CSF anchor nested in another anchor, a known legacy bug."""
    href = text.find('href="/list/csf/"')
    if href < 0:
        return text
    csf_open = text.rfind("<a", 0, href)
    previous_open = text.rfind("<a", 0, csf_open)
    previous_close = text.rfind("</a>", 0, csf_open)
    if csf_open < 0 or previous_open <= previous_close:
        return text
    csf_close = text.find("</a>", href)
    if csf_close < 0:
        raise SystemExit("malformed pre-existing CSF anchor")
    csf_close += len("</a>")
    line_start = text.rfind("\n", 0, csf_open) + 1
    line_end = text.find("\n", csf_close)
    if line_end < 0:
        line_end = csf_close
    else:
        line_end += 1
    return text[:line_start] + text[line_end:]


def patch_panel(panel: Path, snippet: str) -> None:
    original = panel.read_text(encoding="utf-8")
    text = original
    if PANEL_MARKER in text:
        if text.count(PANEL_MARKER) != 1 or text.count('href="/list/csf/"') != 1:
            raise SystemExit("duplicate or malformed managed CSF menu entry")
        return

    if 'href="/list/csf/"' in text:
        text = repair_nested_csf_link(text)
    if 'href="/list/csf/"' in text:
        raise SystemExit(
            "an unmanaged non-nested CSF menu entry exists; refusing to guess its scope"
        )

    anchors = ("\t\t\t\t\t\t\t<!-- Web Terminal -->", "<!-- Web Terminal -->", "<!-- Server Settings -->")
    insertion = -1
    for anchor in anchors:
        insertion = text.find(anchor)
        if insertion >= 0:
            break
    if insertion < 0:
        raise SystemExit("Hestia panel template anchor not found")

    text = text[:insertion] + snippet + text[insertion:]
    if text.count(PANEL_MARKER) != 1 or text.count('href="/list/csf/"') != 1:
        raise SystemExit("CSF menu postcondition failed")
    panel.write_text(text, encoding="utf-8")


def patch_regex(path: Path, fragment: str) -> None:
    original = path.read_text(encoding="utf-8")
    if REGEX_BEGIN in original or REGEX_END in original:
        pattern = re.compile(
            re.escape(REGEX_BEGIN) + r".*?" + re.escape(REGEX_END) + r"\n?",
            re.DOTALL,
        )
        if len(pattern.findall(original)) != 1:
            raise SystemExit("malformed managed Hestia regex block")
        replacement = fragment.rstrip("\n") + "\n"
        rendered = pattern.sub(lambda _match: replacement, original)
    else:
        matches = list(re.finditer(r"(?m)^\s*return 0;\s*$", original))
        if not matches:
            raise SystemExit("regex.custom.pm insertion point not found")
        insertion = matches[-1].start()
        rendered = original[:insertion] + fragment + original[insertion:]
    path.write_text(rendered, encoding="utf-8")
    os.chmod(path, 0o700)


def find_hestia_custom_key(config: Path, hestia_log: str) -> str:
    matches = re.findall(r'(?m)^(CUSTOM[1-9]_LOG)\s*=\s*"([^"]*)"\s*$', config.read_text(encoding="utf-8"))
    keys = [key for key, value in matches if value == hestia_log]
    if len(keys) != 1:
        raise SystemExit("expected exactly one CSF custom log slot for Hestia auth.log")
    return keys[0]


def copy_assets(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise SystemExit(f"upstream CSF UI assets missing: {source}")
    destination.mkdir(parents=True, exist_ok=True)
    for item in source.rglob("*"):
        relative = item.relative_to(source)
        target = destination / relative
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif item.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)
            os.chmod(target, 0o644)
    for folder in [destination, *[path for path in destination.rglob("*") if path.is_dir()]]:
        os.chmod(folder, 0o755)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("/"))
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--templates", type=Path, required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    source = args.source.resolve()
    templates = args.templates.resolve()
    profile = discover(root)

    panel = rooted(root, "/usr/local/hestia/web/templates/includes/panel.php")
    if not panel.exists():
        raise SystemExit(f"Hestia panel template missing: {panel}")

    install_file(
        templates / "index.php",
        rooted(root, "/usr/local/hestia/web/list/csf/index.php"),
        0o644,
    )
    install_file(
        templates / "frame.php",
        rooted(root, "/usr/local/hestia/web/list/csf/frame.php"),
        0o644,
    )
    install_file(
        templates / "list_csf.php",
        rooted(root, "/usr/local/hestia/web/templates/pages/list_csf.php"),
        0o644,
    )
    install_file(
        source / "vestacp/csf.pl",
        rooted(root, "/usr/local/hestia/bin/csf.pl"),
        0o700,
    )
    copy_assets(
        source / "csf",
        rooted(root, "/usr/local/hestia/web/list/csf/images"),
    )

    snippet = (templates / "panel-snippet.php").read_text(encoding="utf-8")
    patch_panel(panel, snippet)

    regex_path = rooted(root, "/usr/local/csf/bin/regex.custom.pm")
    if not regex_path.exists():
        install_file(source / "regex.custom.pm", regex_path, 0o700)
    fragment = (templates / "hestia-regex.pm.inc").read_text(encoding="utf-8")
    fragment = fragment.replace("@@HESTIA_PORT@@", str(profile.hestia_port))
    fragment = fragment.replace(
        "@@CUSTOM_LOG@@",
        find_hestia_custom_key(rooted(root, "/etc/csf/csf.conf"), profile.hestia_log),
    )
    patch_regex(regex_path, fragment)

    print(f"root_user={profile.root_user}")
    print(f"hestia_port={profile.hestia_port}")
    print(f"panel={panel}")
    print(f"regex={regex_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
