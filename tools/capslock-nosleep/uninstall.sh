#!/bin/bash
# 常駐デーモンを止めて削除し、スリープ設定を通常に戻す。
# 使い方: sudo ~/Tools/capslock-nosleep/uninstall.sh
set -uo pipefail

LABEL="com.local.capslock-nosleep"
BIN="/usr/local/bin/capslock-nosleep"
PLIST="/Library/LaunchDaemons/${LABEL}.plist"

if [ "$(id -u)" -ne 0 ]; then
  echo "root で実行してください: sudo $0" >&2
  exit 1
fi

launchctl bootout "system/${LABEL}" 2>/dev/null || true
rm -f "${PLIST}" "${BIN}"
/usr/bin/pmset -a disablesleep 0

echo "uninstalled. disablesleep を 0 に戻しました。"
