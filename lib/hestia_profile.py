#!/usr/bin/env python3
"""Discover a Hestia host and render the conservative SYSDOP CSF profile."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


BACKEND_PORTS = {3306, 5432, 6379, 8080, 8081, 8082, 8443, 11211}


@dataclass
class Profile:
    root_user: str
    hestia_port: int
    ssh_ports: list[int]
    ftp_port: int | None
    ftp_passive: str | None
    mail: bool
    dns: bool
    quic: bool
    ipv6: bool
    docker: bool
    tcp_in: str
    tcp_out: str
    udp_in: str
    udp_out: str
    sshd_log: str
    ftpd_log: str
    smtpauth_log: str
    dovecot_log: str
    apache_log: str
    iptables_log: str
    syslog_log: str
    hestia_log: str
    excluded_backend_ports: list[int]


def rooted(root: Path, absolute: str) -> Path:
    return root / absolute.lstrip("/")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def shell_assignment(text: str, key: str) -> str | None:
    match = re.search(
        rf"(?m)^\s*{re.escape(key)}\s*=\s*(['\"]?)([^'\"\s#]+)\1\s*(?:#.*)?$",
        text,
    )
    return match.group(2) if match else None


def valid_port(value: str | int | None) -> int | None:
    try:
        port = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return port if 1 <= port <= 65535 else None


def find_hestia_port(root: Path, conf: str) -> int:
    configured = valid_port(shell_assignment(conf, "HESTIA_PORT"))
    if configured:
        return configured

    candidates = [
        rooted(root, "/usr/local/hestia/nginx/conf/nginx.conf"),
        rooted(root, "/usr/local/hestia/nginx/conf/nginx.conf.default"),
    ]
    ports: list[int] = []
    for path in candidates:
        text = read_text(path)
        for match in re.finditer(
            r"(?m)^\s*listen\s+(?:\[[^]]+\]:|(?:\d{1,3}\.){3}\d{1,3}:)?(\d+)\b",
            text,
        ):
            port = valid_port(match.group(1))
            if port and port not in {80, 443}:
                ports.append(port)
    return ports[0] if ports else 8083


def strip_sshd(text: str) -> Iterable[str]:
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.lower().startswith("match "):
            break
        yield line


def find_ssh_ports(root: Path) -> list[int]:
    if root == Path("/"):
        sshd = next((name for name in ("sshd", "/usr/sbin/sshd") if Path(name).exists() or shutil_which(name)), None)
        if sshd:
            try:
                result = subprocess.run(
                    [str(sshd), "-T", "-C", "user=root,host=localhost,addr=127.0.0.1"],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                runtime = [
                    valid_port(line.split()[1])
                    for line in result.stdout.splitlines()
                    if line.startswith("port ")
                ]
                runtime_ports = sorted({port for port in runtime if port})
                if runtime_ports:
                    return runtime_ports
            except (OSError, subprocess.SubprocessError):
                pass

    paths = [rooted(root, "/etc/ssh/sshd_config")]
    paths.extend(
        sorted(rooted(root, "/etc/ssh/sshd_config.d").glob("*.conf"))
    )
    ports: list[int] = []
    for path in paths:
        for line in strip_sshd(read_text(path)):
            match = re.match(r"(?i)^port\s+(\d+)\s*$", line)
            if match:
                port = valid_port(match.group(1))
                if port:
                    ports.append(port)
    return sorted(set(ports)) or [22]


def shutil_which(name: str) -> str | None:
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        path = Path(directory) / name
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    return None


def parse_simple_conf(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in read_text(path).splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip().lower()] = value.strip().strip("'\"")
    return values


def find_ftp(root: Path) -> tuple[int | None, str | None]:
    for absolute in ("/etc/vsftpd.conf", "/etc/vsftpd/vsftpd.conf"):
        path = rooted(root, absolute)
        if not path.exists():
            continue
        values = parse_simple_conf(path)
        port = valid_port(values.get("listen_port")) or 21
        start = valid_port(values.get("pasv_min_port"))
        end = valid_port(values.get("pasv_max_port"))
        passive = f"{start}:{end}" if start and end and start <= end else None
        return port, passive

    for absolute in ("/etc/proftpd/proftpd.conf", "/etc/proftpd.conf"):
        text = read_text(rooted(root, absolute))
        if not text:
            continue
        port_match = re.search(r"(?mi)^\s*Port\s+(\d+)\b", text)
        passive_match = re.search(r"(?mi)^\s*PassivePorts\s+(\d+)\s+(\d+)\b", text)
        port = valid_port(port_match.group(1)) if port_match else 21
        passive = None
        if passive_match:
            start = valid_port(passive_match.group(1))
            end = valid_port(passive_match.group(2))
            if start and end and start <= end:
                passive = f"{start}:{end}"
        return port, passive
    return None, None


def path_any(root: Path, names: Iterable[str]) -> bool:
    return any(rooted(root, name).exists() for name in names)


def find_first(root: Path, candidates: Iterable[str], fallback: str) -> str:
    for name in candidates:
        if rooted(root, name).exists():
            return name
    return fallback


def detect_ipv6(root: Path) -> bool:
    disabled = read_text(rooted(root, "/proc/sys/net/ipv6/conf/all/disable_ipv6")).strip()
    if disabled == "1":
        return False
    if root != Path("/"):
        return rooted(root, "/fixture-ipv6-enabled").exists()
    try:
        result = subprocess.run(
            ["ip", "-6", "-o", "addr", "show", "scope", "global"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return bool(result.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return False


def detect_docker(root: Path) -> bool:
    if root != Path("/"):
        return rooted(root, "/fixture-docker-active").exists()
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "docker"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() == "active"
    except (OSError, subprocess.SubprocessError):
        return False


def nginx_has_quic(root: Path) -> bool:
    base = rooted(root, "/etc/nginx")
    hestia = rooted(root, "/usr/local/hestia/nginx/conf")
    for folder in (base, hestia):
        if not folder.exists():
            continue
        for path in folder.rglob("*.conf"):
            text = read_text(path)
            if re.search(r"(?mi)^\s*listen\s+[^;]*(?:\bquic\b|\bhttp3\b)", text):
                return True
            if re.search(r"(?mi)^\s*http3\s+on\s*;", text):
                return True
    return False


def port_key(value: str) -> tuple[int, int]:
    first = value.split(":", 1)[0]
    return (int(first), 1 if ":" in value else 0)


def render_ports(values: Iterable[int | str]) -> str:
    unique = {str(value) for value in values if str(value)}
    return ",".join(sorted(unique, key=port_key))


def discover(root: Path) -> Profile:
    root = root.resolve()
    hestia_conf = read_text(rooted(root, "/usr/local/hestia/conf/hestia.conf"))
    if not hestia_conf:
        raise SystemExit("HestiaCP fixture/host is missing hestia.conf")

    root_user = shell_assignment(hestia_conf, "ROOT_USER") or "admin"
    hestia_port = find_hestia_port(root, hestia_conf)
    ssh_ports = find_ssh_ports(root)
    ftp_port, ftp_passive = find_ftp(root)

    mail = path_any(
        root,
        ("/etc/exim4", "/etc/exim", "/etc/postfix", "/etc/dovecot"),
    )
    dns = path_any(root, ("/etc/bind", "/etc/pdns", "/etc/powerdns"))
    if (shell_assignment(hestia_conf, "MAIL_SYSTEM") or "").lower() in {"no", "none", "disabled"}:
        mail = False
    if (shell_assignment(hestia_conf, "DNS_SYSTEM") or "").lower() in {"no", "none", "disabled"}:
        dns = False
    quic = nginx_has_quic(root)
    ipv6 = detect_ipv6(root)
    docker = detect_docker(root)

    tcp_in: list[int | str] = [80, 443, hestia_port, *ssh_ports]
    if dns:
        tcp_in.append(53)
    if mail:
        tcp_in.extend((25, 110, 143, 465, 587, 993, 995))
    if ftp_port:
        tcp_in.append(ftp_port)
    if ftp_passive:
        tcp_in.append(ftp_passive)

    tcp_out: list[int | str] = [20, 21, 22, 25, 43, 53, 80, 110, 113, 443, 465, 587, 873, 993, 995]
    udp_in: list[int | str] = [53] if dns else []
    if quic:
        udp_in.extend((80, 443))
    udp_out: list[int | str] = [53, 123]

    sshd_log = find_first(root, ("/var/log/auth.log", "/var/log/secure"), "/var/log/auth.log")
    ftpd_log = find_first(root, ("/var/log/vsftpd.log", "/var/log/proftpd/proftpd.log"), "/var/log/vsftpd.log")
    smtpauth_log = find_first(root, ("/var/log/exim4/mainlog", "/var/log/exim_mainlog", "/var/log/maillog"), "/var/log/exim4/mainlog")
    dovecot_log = find_first(root, ("/var/log/dovecot.log", "/var/log/mail.log", "/var/log/maillog"), "/var/log/dovecot.log")
    apache_log = find_first(root, ("/var/log/apache2/error.log", "/var/log/httpd/error_log"), "/var/log/apache2/error.log")
    iptables_log = find_first(root, ("/var/log/kern.log", "/var/log/messages"), "/var/log/kern.log")
    syslog_log = find_first(root, ("/var/log/syslog", "/var/log/messages"), "/var/log/syslog")
    hestia_log = "/var/log/hestia/auth.log"

    return Profile(
        root_user=root_user,
        hestia_port=hestia_port,
        ssh_ports=ssh_ports,
        ftp_port=ftp_port,
        ftp_passive=ftp_passive,
        mail=mail,
        dns=dns,
        quic=quic,
        ipv6=ipv6,
        docker=docker,
        tcp_in=render_ports(tcp_in),
        tcp_out=render_ports(tcp_out),
        udp_in=render_ports(udp_in),
        udp_out=render_ports(udp_out),
        sshd_log=sshd_log,
        ftpd_log=ftpd_log,
        smtpauth_log=smtpauth_log,
        dovecot_log=dovecot_log,
        apache_log=apache_log,
        iptables_log=iptables_log,
        syslog_log=syslog_log,
        hestia_log=hestia_log,
        excluded_backend_ports=sorted(BACKEND_PORTS),
    )


def config_updates(profile: Profile, hestia_custom_key: str) -> dict[str, str]:
    return {
        "TESTING": "0",
        "RESTRICT_SYSLOG": "3",
        "RESTRICT_UI": "1",
        "AUTO_UPDATES": "0",
        "TCP_IN": profile.tcp_in,
        "TCP_OUT": profile.tcp_out,
        "UDP_IN": profile.udp_in,
        "UDP_OUT": profile.udp_out,
        "IPV6": "1" if profile.ipv6 else "0",
        "TCP6_IN": profile.tcp_in if profile.ipv6 else "",
        "TCP6_OUT": profile.tcp_out if profile.ipv6 else "",
        "UDP6_IN": profile.udp_in if profile.ipv6 else "",
        "UDP6_OUT": profile.udp_out if profile.ipv6 else "",
        "LF_SSHD": "5",
        "LF_FTPD": "10" if profile.ftp_port else "0",
        "LF_SMTPAUTH": "5" if profile.mail else "0",
        "LF_EXIMSYNTAX": "10" if profile.mail else "0",
        "LF_POP3D": "10" if profile.mail else "0",
        "LF_IMAPD": "10" if profile.mail else "0",
        "UI": "0",
        "DOCKER": "1" if profile.docker else "0",
        "HTACCESS_LOG": profile.apache_log,
        "MODSEC_LOG": profile.apache_log,
        "SSHD_LOG": profile.sshd_log,
        "SU_LOG": profile.sshd_log,
        "SUDO_LOG": profile.sshd_log,
        "FTPD_LOG": profile.ftpd_log,
        "SMTPAUTH_LOG": profile.smtpauth_log,
        "POP3D_LOG": profile.dovecot_log,
        "IMAPD_LOG": profile.dovecot_log,
        "IPTABLES_LOG": profile.iptables_log,
        "SUHOSIN_LOG": profile.syslog_log,
        "BIND_LOG": profile.syslog_log,
        "SYSLOG_LOG": profile.syslog_log,
        "WEBMIN_LOG": profile.sshd_log,
        hestia_custom_key: profile.hestia_log,
        "PORTS_pop3d": "110,995",
        "PORTS_imapd": "143,993",
        "PORTS_htpasswd": "80,443",
        "PORTS_mod_security": "80,443",
        "PORTS_bind": "53;udp,53;tcp",
        "PORTS_ftpd": str(profile.ftp_port or 21),
        "PORTS_smtpauth": "25,465,587",
        "PORTS_eximsyntax": "25,465,587",
        "PORTS_sshd": ",".join(str(port) for port in profile.ssh_ports),
        "GENERIC": "1",
        "DEBUG": "0",
    }


ASSIGNMENT = re.compile(r'^([A-Z][A-Za-z0-9_]*)\s*=\s*"([^"]*)"\s*$')


def configure(path: Path, updates: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8")
    counts: dict[str, int] = {}
    for line in text.splitlines():
        match = ASSIGNMENT.match(line)
        if match:
            counts[match.group(1)] = counts.get(match.group(1), 0) + 1

    duplicates = sorted(name for name, count in counts.items() if count != 1)
    if duplicates:
        raise SystemExit(f"duplicate CSF keys: {', '.join(duplicates)}")
    missing = sorted(set(updates) - set(counts))
    if missing:
        raise SystemExit(f"CSF 15.10 keys missing: {', '.join(missing)}")

    rendered: list[str] = []
    for line in text.splitlines(keepends=True):
        match = ASSIGNMENT.match(line.rstrip("\n"))
        if match and match.group(1) in updates:
            name = match.group(1)
            value = updates[name]
            if any(character in value for character in ('"', "\r", "\n")):
                raise SystemExit(f"unsafe value for {name}")
            newline = "\n" if line.endswith("\n") else ""
            rendered.append(f'{name} = "{value}"{newline}')
        else:
            rendered.append(line)
    path.write_text("".join(rendered), encoding="utf-8")


def choose_hestia_custom_key(path: Path, hestia_log: str) -> str:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = ASSIGNMENT.match(line)
        if match and re.fullmatch(r"CUSTOM[1-9]_LOG", match.group(1)):
            values[match.group(1)] = match.group(2)
    for key, value in values.items():
        if value == hestia_log:
            return key
    for number in range(1, 10):
        key = f"CUSTOM{number}_LOG"
        if key in values and not values[key]:
            return key
    raise SystemExit("no free CUSTOM1_LOG..CUSTOM9_LOG slot for Hestia auth.log")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--root", type=Path, default=Path("/"))
    conf = sub.add_parser("configure")
    conf.add_argument("--root", type=Path, default=Path("/"))
    conf.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()

    profile = discover(args.root)
    if args.command == "configure":
        custom_key = choose_hestia_custom_key(args.config, profile.hestia_log)
        configure(args.config, config_updates(profile, custom_key))
    print(json.dumps(asdict(profile), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
