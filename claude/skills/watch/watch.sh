#!/bin/bash
# watch.sh <video-url-or-path> [outdir]
# 動画をDLし、シーン変化でフレーム抽出＋字幕を取得する。出力先を stdout に返す。
set -uo pipefail
nframes(){ set -- "$OUT"/f_*.jpg; [ -e "$1" ] && echo $# || echo 0; }
URL="$1"
OUT="${2:-/tmp/watch-$(date +%s)}"
mkdir -p "$OUT"

if [[ -f "$URL" ]]; then
  cp "$URL" "$OUT/video.mp4"
else
  yt-dlp -q --no-warnings \
    --write-auto-subs --write-subs --sub-langs "ja,en,en-US,ja-JP" --convert-subs srt \
    -f "bv*[height<=720]+ba/b[height<=720]/b" --merge-output-format mp4 \
    -o "$OUT/video.%(ext)s" "$URL" 2>&1 | tail -3 || true
  yt-dlp -q --no-warnings --skip-download --print "%(title)s|%(duration)s|%(uploader)s" "$URL" > "$OUT/meta.txt" 2>/dev/null || true
fi

V=""; for c in "$OUT"/video.mp4 "$OUT"/video.webm "$OUT"/video.mkv "$OUT"/video.mov; do [ -f "$c" ] && { V="$c"; break; }; done
[[ -z "$V" ]] && { echo "ERROR: ダウンロード失敗 $URL"; exit 1; }

DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$V" 2>/dev/null | cut -d. -f1); DUR=${DUR:-0}
# シーン変化でフレーム抽出。長尺は間引く（上限60枚）
THRESH=0.3; [[ "$DUR" -gt 600 ]] && THRESH=0.5
ffmpeg -v error -i "$V" -vf "select='gt(scene,$THRESH)',scale=768:-1,showinfo" -vsync vfr -frame_pts 1 "$OUT/f_%04d.jpg" 2>"$OUT/frames.log" || true
N=$(nframes)
# シーン検出が0件（静止画的な動画）なら等間隔で
if [[ "$N" -lt 4 ]]; then
  rm -f "$OUT"/f_*.jpg
  FPS=$(python3 -c "print(max(0.1, min(1, 24/max(1,$DUR))))")
  ffmpeg -v error -i "$V" -vf "fps=$FPS,scale=768:-1" "$OUT/f_%04d.jpg" 2>/dev/null || true
  N=$(nframes)
fi
# 60枚超なら間引く
if [[ "$N" -gt 60 ]]; then
  i=0; STEP=$(( N / 60 + 1 ))
  for f in "$OUT"/f_*.jpg; do i=$((i+1)); [[ $((i % STEP)) -ne 0 ]] && rm -f "$f"; done
  N=$(nframes)
fi

SUB=""; for c in "$OUT"/*.srt; do [ -f "$c" ] && { SUB="$c"; break; }; done
echo "OUTDIR=$OUT"
echo "VIDEO=$V"
echo "DURATION_SEC=$DUR"
echo "FRAMES=$N"
[[ -f "$OUT/meta.txt" ]] && echo "META=$(cat "$OUT/meta.txt")"
if [[ -n "$SUB" ]]; then echo "SUBTITLE=$SUB"; else echo "SUBTITLE=none (音声は未書き起こし)"; fi
