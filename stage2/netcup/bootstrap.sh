#!/bin/bash
# Bootstrap the user's dedicated Debian server; never run on a shared cluster.
set -euo pipefail
umask 077
test "$(id -u)" = 0
test "$(dpkg --print-architecture)" = amd64
. /etc/os-release
test "$ID" = debian
test "$VERSION_CODENAME" = trixie
asset_dir=$(cd -- "$(dirname -- "$0")" && pwd)
test -s /root/.ssh/authorized_keys
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl git tmux jq python3-venv
install -m 0755 -d /etc/apt/keyrings
curl --fail --silent --show-error --proto '=https' --tlsv1.2 \
  https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
chmod 0644 /etc/apt/keyrings/docker.asc
install -m 0644 "$asset_dir/docker.sources" /etc/apt/sources.list.d/uts-docker.sources
apt-get update
apt-get install -y --no-install-recommends docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
install -m 0700 -d /opt/uts-capstone
python3 -m venv /opt/uts-bootstrap
/opt/uts-bootstrap/bin/pip install --disable-pip-version-check 'uv==0.12.3'
/opt/uts-bootstrap/bin/uv python install 3.12
install -m 0600 "$asset_dir/00-uts-key-only.conf" /etc/ssh/sshd_config.d/00-uts-key-only.conf
/usr/sbin/sshd -t
systemctl reload ssh
docker version --format '{{json .Server}}'
docker compose version
/usr/sbin/sshd -T | grep -E '^(passwordauthentication|kbdinteractiveauthentication|permitrootlogin|pubkeyauthentication) '
