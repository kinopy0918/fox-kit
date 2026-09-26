#!/bin/bash
# テザリングから戻って遅い/繋がらない時の一発リセット
echo "Wi-Fiを切ります..."
networksetup -setairportpower en0 off
sleep 8   # ルータ側のリース/近隣キャッシュが切れるのを待つ（短いと意味がない）
echo "Wi-Fiを入れ直します..."
networksetup -setairportpower en0 on
sleep 6
echo
echo "--- 結果 ---"
ifconfig en0 | awk '/inet /{print "  IPアドレス: "$2}'
netstat -rn -f inet | awk '/^default/{print "  出口: "$4" (en0ならOK)"; exit}'
curl -s -o /dev/null -w "  ページ取得: %{time_total}秒 (1秒以上なら まだ変)\n" --max-time 20 https://www.google.com || echo "  ページ取得: 失敗"
