#!/bin/bash
# CapsLock ON でフタ閉じスリープを無効化する常駐デーモンをインストールする。
# 使い方: sudo ~/Tools/capslock-nosleep/install.sh
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.local.capslock-nosleep"
BIN="/usr/local/bin/capslock-nosleep"
PLIST="/Library/LaunchDaemons/${LABEL}.plist"

if [ "$(id -u)" -ne 0 ]; then
  echo "root で実行してください: sudo $0" >&2
  exit 1
fi

# 既存があれば止める
launchctl bootout "system/${LABEL}" 2>/dev/null || true

install -d -m 755 /usr/local/bin
install -m 755 -o root -g wheel "${SRC}/capslock-nosleep.py" "${BIN}"
install -m 644 -o root -g wheel "${SRC}/${LABEL}.plist" "${PLIST}"

launchctl bootstrap system "${PLIST}"
launchctl enable "system/${LABEL}"

echo "installed: ${BIN}"
echo "loaded   : ${PLIST}"
launchctl print "system/${LABEL}" | grep -E "state|pid" | head -3 || true
