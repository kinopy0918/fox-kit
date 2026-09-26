#!/bin/bash
# 「遅い/繋がらない」が起きた"その瞬間"に実行して原因を確定するスナップショット
OUT=~/Tools/netdiag/snap_$(date +%Y%m%d_%H%M%S).txt
{
echo "########## $(date) ##########"
echo "--- Wi-Fi 接続先 / チャンネル / 電波 ---"
system_profiler SPAirPortDataType 2>/dev/null | sed -n '/Current Network/,/Other Local/p'
echo "--- 有効サービス順序（上が優先） ---"
networksetup -listnetworkserviceorder | grep -E "^\([0-9]"
echo "--- IPアドレス（169.254.x なら DHCP 失敗）---"
ifconfig | grep -E "^[a-z0-9]+:|inet " | grep -v 127.0.0.1
echo "--- デフォルトルート（en0以外ならサービス順序が原因）---"
netstat -rn -f inet | grep ^default
netstat -rn -f inet6 | grep ^default
echo "--- DNS（第1候補が死んでいるかを実測）---"
scutil --dns | sed -n '/resolver #1/,/^$/p'
for ns in $(scutil --dns | awk '/resolver #1/,/^$/' | awk '/nameserver/{print $3}'); do
  printf "  %-45s " "$ns"
  dig @"$ns" www.apple.com +time=2 +tries=1 2>/dev/null | awk '/Query time/{print $4" ms"}' || echo "TIMEOUT"
done
echo "--- 疎通 ---"
GW=$(netstat -rn -f inet | awk '/^default/{print $2; exit}')
echo "gw($GW):"; ping -c 3 -t 2 "$GW" 2>&1 | tail -2
echo "v4 1.1.1.1:"; ping -c 3 -t 2 1.1.1.1 2>&1 | tail -2
echo "v6:"; ping6 -c 3 2606:4700:4700::1111 2>&1 | tail -2
echo "--- 名前解決＋HTTPSの実時間（ここが遅ければDNS/IPv6が犯人）---"
curl -4 -s -o /dev/null -w "  ipv4 dns=%{time_namelookup}s conn=%{time_connect}s total=%{time_total}s\n" --max-time 15 https://www.google.com
curl -6 -s -o /dev/null -w "  ipv6 dns=%{time_namelookup}s conn=%{time_connect}s total=%{time_total}s\n" --max-time 15 https://www.google.com
curl    -s -o /dev/null -w "  auto dns=%{time_namelookup}s conn=%{time_connect}s total=%{time_total}s\n" --max-time 15 https://www.google.com
} 2>&1 | tee "$OUT"
echo; echo "保存: $OUT"
