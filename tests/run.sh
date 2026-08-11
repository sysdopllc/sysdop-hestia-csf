#!/usr/bin/env bash
set -Eeuo pipefail

TEST_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
KIT_DIR="$(cd -- "$TEST_DIR/.." && pwd -P)"
TEST_TMP="$(mktemp -d /tmp/sysdop-hestia-csf-test.XXXXXX)"

cleanup() {
	rm -rf -- "$TEST_TMP"
}
trap cleanup EXIT

cp -a "$TEST_DIR/fixtures/hestia-root" "$TEST_TMP/root"
cp -a "$TEST_DIR/fixtures/upstream" "$TEST_TMP/upstream"
cp -a "$TEST_DIR/fixtures/hestia-root" "$TEST_TMP/nested-root"
cp -a "$TEST_DIR/fixtures/hestia-root" "$TEST_TMP/legacy-root"
cp "$TEST_DIR/fixtures/panel-nested.php" \
	"$TEST_TMP/nested-root/usr/local/hestia/web/templates/includes/panel.php"
cp "$TEST_DIR/fixtures/regex-legacy.pm" \
	"$TEST_TMP/legacy-root/usr/local/csf/bin/regex.custom.pm"

python3 -m py_compile "$KIT_DIR"/lib/*.py
bash -n "$KIT_DIR/bin/sysdop-hestia-csf"
bash -n "$KIT_DIR/tests/run.sh"
bash -n "$KIT_DIR/templates/csfpost.sh"
grep -q '788317da71d31a338da4cff3bdae9471137efc3978436692fe9d005eb70f54b3' "$KIT_DIR/UPSTREAM.lock"
grep -q '788317da71d31a338da4cff3bdae9471137efc3978436692fe9d005eb70f54b3' "$KIT_DIR/bin/sysdop-hestia-csf"
if grep -R -E 'refs/heads/main|archive/(main|master)|main\.tar' "$KIT_DIR/bin" "$KIT_DIR/lib"; then
	exit 1
fi

python3 "$KIT_DIR/lib/patch_upstream.py" "$TEST_TMP/upstream" > "$TEST_TMP/upstream-first.txt"
python3 "$KIT_DIR/lib/patch_upstream.py" "$TEST_TMP/upstream" > "$TEST_TMP/upstream-second.txt"
if grep -q 'systemctl enable csf.service' "$TEST_TMP/upstream/install.generic.sh"; then
	exit 1
fi
if grep -q 'systemctl disable firewalld' "$TEST_TMP/upstream/install.generic.sh"; then
	exit 1
fi
grep -q 'SYSDOP_Hestia_safety_patch_v1' "$TEST_TMP/upstream/install.generic.sh"

python3 "$KIT_DIR/lib/hestia_profile.py" configure \
	--root "$TEST_TMP/nested-root" \
	--config "$TEST_TMP/nested-root/etc/csf/csf.conf" > "$TEST_TMP/nested-configure.json"
python3 "$KIT_DIR/lib/patch_hestia_ui.py" \
	--root "$TEST_TMP/nested-root" \
	--source "$TEST_TMP/upstream" \
	--templates "$KIT_DIR/templates" > "$TEST_TMP/nested-ui.txt"
nested_panel="$TEST_TMP/nested-root/usr/local/hestia/web/templates/includes/panel.php"
[[ "$(grep -c 'href="/fm/"' "$nested_panel")" == "1" ]]
[[ "$(grep -c 'href="/list/csf/"' "$nested_panel")" == "1" ]]
[[ "$(grep -c 'SYSDOP Hestia CSF integration' "$nested_panel")" == "1" ]]

python3 "$KIT_DIR/lib/hestia_profile.py" configure \
	--root "$TEST_TMP/legacy-root" \
	--config "$TEST_TMP/legacy-root/etc/csf/csf.conf" > "$TEST_TMP/legacy-configure.json"
python3 "$KIT_DIR/lib/patch_hestia_ui.py" \
	--root "$TEST_TMP/legacy-root" \
	--source "$TEST_TMP/upstream" \
	--templates "$KIT_DIR/templates" > "$TEST_TMP/legacy-ui.txt"
legacy_regex="$TEST_TMP/legacy-root/usr/local/csf/bin/regex.custom.pm"
[[ "$(grep -c 'SYSDOP_HESTIA_REGEX_BEGIN' "$legacy_regex")" == "1" ]]
[[ "$(grep -c 'Failed HestiaCP login from' "$legacy_regex")" == "1" ]]

python3 "$KIT_DIR/lib/hestia_profile.py" audit --root "$TEST_TMP/root" > "$TEST_TMP/profile.json"
python3 - "$TEST_TMP/profile.json" <<'PY'
import json
import sys

profile = json.load(open(sys.argv[1], encoding="utf-8"))
assert profile["root_user"] == "opsadmin"
assert profile["hestia_port"] == 56464
assert profile["ssh_ports"] == [56463]
assert profile["ftp_port"] == 56364
assert profile["ftp_passive"] == "12000:12100"
assert profile["ipv6"] is True
assert profile["docker"] is False
assert profile["quic"] is False
assert profile["mail"] is True
assert profile["dns"] is True
for forbidden in (3306, 6379, 8080, 8443, 11211):
    assert str(forbidden) not in profile["tcp_in"].split(",")
PY

python3 "$KIT_DIR/lib/hestia_profile.py" configure \
	--root "$TEST_TMP/root" \
	--config "$TEST_TMP/root/etc/csf/csf.conf" > "$TEST_TMP/configure-first.json"
python3 "$KIT_DIR/lib/ensure_syslogusers.py" \
	--root "$TEST_TMP/root" \
	--file "$TEST_TMP/root/etc/csf/csf.syslogusers" > "$TEST_TMP/syslogusers-first.txt"
python3 "$KIT_DIR/lib/patch_hestia_ui.py" \
	--root "$TEST_TMP/root" \
	--source "$TEST_TMP/upstream" \
	--templates "$KIT_DIR/templates" > "$TEST_TMP/ui-first.txt"

sha256sum \
	"$TEST_TMP/root/etc/csf/csf.conf" \
	"$TEST_TMP/root/etc/csf/csf.syslogusers" \
	"$TEST_TMP/root/usr/local/hestia/web/templates/includes/panel.php" \
	"$TEST_TMP/root/usr/local/csf/bin/regex.custom.pm" \
	> "$TEST_TMP/hashes-first.txt"

python3 "$KIT_DIR/lib/hestia_profile.py" configure \
	--root "$TEST_TMP/root" \
	--config "$TEST_TMP/root/etc/csf/csf.conf" > "$TEST_TMP/configure-second.json"
python3 "$KIT_DIR/lib/ensure_syslogusers.py" \
	--root "$TEST_TMP/root" \
	--file "$TEST_TMP/root/etc/csf/csf.syslogusers" > "$TEST_TMP/syslogusers-second.txt"
python3 "$KIT_DIR/lib/patch_hestia_ui.py" \
	--root "$TEST_TMP/root" \
	--source "$TEST_TMP/upstream" \
	--templates "$KIT_DIR/templates" > "$TEST_TMP/ui-second.txt"

sha256sum \
	"$TEST_TMP/root/etc/csf/csf.conf" \
	"$TEST_TMP/root/etc/csf/csf.syslogusers" \
	"$TEST_TMP/root/usr/local/hestia/web/templates/includes/panel.php" \
	"$TEST_TMP/root/usr/local/csf/bin/regex.custom.pm" \
	> "$TEST_TMP/hashes-second.txt"
diff -u "$TEST_TMP/hashes-first.txt" "$TEST_TMP/hashes-second.txt"
[[ "$(grep -c '^root$' "$TEST_TMP/root/etc/csf/csf.syslogusers")" == "1" ]]
[[ "$(grep -c '^hestiaweb$' "$TEST_TMP/root/etc/csf/csf.syslogusers")" == "1" ]]
[[ "$(grep -c '^customlogger$' "$TEST_TMP/root/etc/csf/csf.syslogusers")" == "1" ]]

config="$TEST_TMP/root/etc/csf/csf.conf"
grep -q '^TCP_IN = "25,53,80,110,143,443,465,587,993,995,12000:12100,56364,56463,56464"$' "$config"
grep -q '^TCP6_IN = "25,53,80,110,143,443,465,587,993,995,12000:12100,56364,56463,56464"$' "$config"
grep -q '^UDP_IN = "53"$' "$config"
grep -q '^PORTS_sshd = "56463"$' "$config"
grep -q '^PORTS_ftpd = "56364"$' "$config"
grep -q '^AUTO_UPDATES = "0"$' "$config"
grep -q '^UI = "0"$' "$config"
grep -q '^CUSTOM1_LOG = "/var/log/custom-app.log"$' "$config"
grep -q '^CUSTOM2_LOG = "/var/log/hestia/auth.log"$' "$config"

panel="$TEST_TMP/root/usr/local/hestia/web/templates/includes/panel.php"
[[ "$(grep -c 'SYSDOP Hestia CSF integration' "$panel")" == "1" ]]
[[ "$(grep -c 'href="/list/csf/"' "$panel")" == "1" ]]
grep -q 'userContext.*admin' "$panel"
grep -q 'empty.*look' "$panel"

regex="$TEST_TMP/root/usr/local/csf/bin/regex.custom.pm"
grep -q 'Existing tenant-specific rule' "$regex"
grep -q 'SYSDOP_HESTIA_REGEX_BEGIN' "$regex"
grep -q '56464' "$regex"
grep -q 'CUSTOM2_LOG' "$regex"
perl -c "$regex"

php -l "$TEST_TMP/root/usr/local/hestia/web/list/csf/index.php"
php -l "$TEST_TMP/root/usr/local/hestia/web/list/csf/frame.php"
php -l "$TEST_TMP/root/usr/local/hestia/web/templates/pages/list_csf.php"
php -l "$panel"

# Adopt the exact pre-kit certified menu entry (same auth guard, old comment).
perl -0pi -e 's/<!-- SYSDOP Hestia CSF integration -->/<!-- CSF Firewall -->/' "$panel"
python3 "$KIT_DIR/lib/patch_hestia_ui.py" \
	--root "$TEST_TMP/root" \
	--source "$TEST_TMP/upstream" \
	--templates "$KIT_DIR/templates" > "$TEST_TMP/ui-adopt-legacy.txt"
[[ "$(grep -c 'SYSDOP Hestia CSF integration' "$panel")" == "1" ]]
[[ "$(grep -c 'href="/list/csf/"' "$panel")" == "1" ]]

printf 'PASS: local fixture, security guards, integration and idempotency\n'
