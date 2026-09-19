"""Uniform infrastructure preparation, independent of task or harness identity.

Old repositories may name removed Debian package files. Repair only the
demonstrated Bullseye security mirror and refresh indexes. Do not install or
upgrade packages or touch task instructions, solutions or tests.
Runs inside the setup phase, never inside the timed agent phase.
"""

import shlex

SNAPSHOT = 'http://snapshot.debian.org/archive/debian-security/20260831T235959Z/'
# Classic Debian 11 sources.list syntax; preserve components, signing keys and
# architecture options. Only the historical Release freshness check is waived
# for this exact dated snapshot, as documented by Debian. Signatures stay on.
SOURCE_REPAIR = r'''/^[[:space:]]*deb(-src)?[[:space:]].*[[:space:]]bullseye-security([[:space:]]|$)/ {
 /https?:\/\/(deb|security)\.debian\.org\/debian-security\/?[[:space:]]/ {
  s#https?://(deb|security)\.debian\.org/debian-security/?[[:space:]]#''' + SNAPSHOT + r''' #
  /check-valid-until=/ {
   s/check-valid-until=[^][:space:]]+/check-valid-until=no/g
   b
  }
  /^[[:space:]]*deb(-src)?[[:space:]]+\[/ {
   s/^([[:space:]]*deb(-src)?[[:space:]]+)\[/\1[check-valid-until=no /
   b
  }
  s/^([[:space:]]*deb(-src)?[[:space:]]+)/\1[check-valid-until=no] /
 }
}'''

COMMAND = '''if command -v apt-get >/dev/null 2>&1 && [ -f /etc/debian_version ]; then
  set -e
  for source in /etc/apt/sources.list /etc/apt/sources.list.d/*.list; do
    [ -f "$source" ] || continue
    sed -i -E ''' + shlex.quote(SOURCE_REPAIR) + ''' "$source"
  done
  DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::Retries=0 -o APT::Update::Error-Mode=any update
else
  printf 'UTS_PACKAGE_METADATA_NOT_APPLICABLE\\n'
fi'''


async def refresh_package_metadata(environment):
    with environment.with_default_user('root'):
        result = await environment.exec(COMMAND, timeout_sec=180)
    if result.return_code != 0:
        raise RuntimeError('Package metadata refresh failed before agent execution')
    return {'policy': 'bullseye-security-snapshot-and-index-refresh-v2', 'packages_installed': False,
            'snapshot_for_bullseye_security': SNAPSHOT,
            'status': 'not_applicable' if 'UTS_PACKAGE_METADATA_NOT_APPLICABLE' in (result.stdout or '') else 'refreshed'}
