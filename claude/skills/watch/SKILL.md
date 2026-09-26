---
name: watch
description: 動画URL（TikTok/YouTube/Instagram/X等）またはローカル動画ファイルを実際に「見る」。yt-dlpで取得し、シーン変化でフレームを抜き、字幕/音声書き起こしと合わせて中身を読む。「この動画見て」「要約して」「この動画の構成を分析して」「タイムスタンプ出して」「不具合の録画を見て」や、動画URLだけを貼られたときに使う。
---

# watch — 動画を実際に見る

持ち主が**動画URLを貼っただけ**のときも、これを発動する（手で文字起こしを貼らせない）。

## 手順

1. 取得＋フレーム抽出:

```bash
~/.claude/skills/watch/watch.sh "<URL または /path/video.mp4>" /tmp/watch-<名前>
```

標準出力に `OUTDIR` / `DURATION_SEC` / `FRAMES` / `SUBTITLE` が返る。

2. **フレームを Read ツールで実際に見る。** `<OUTDIR>/f_*.jpg` を順に読む。
   - 縦型SNS動画（TikTok/Reels/Shorts）は**焼き込み字幕がフレームに写る**ので、これだけで発話が読めることが多い
   - 全部読まず、まず4〜6枚を等間隔で読み、必要な箇所だけ追加で読む（トークン節約）
3. `SUBTITLE` にパスがあれば `.srt` も読む（タイムスタンプ付き発話が取れる）
4. 字幕が `none` で、焼き込み字幕も無い場合のみ音声を書き起こす:

```bash
ffmpeg -v error -i <OUTDIR>/video.mp4 -ar 16000 -ac 1 -c:a pcm_s16le <OUTDIR>/a.wav
whisper-cli -m ~/.cache/whisper/ggml-small.bin -l auto -oj -of <OUTDIR>/tr <OUTDIR>/a.wav
```

モデルが無ければ:
`curl -L -o ~/.cache/whisper/ggml-small.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin`

## 出す形

Discord経由なので[[reply-brevity]]に従う。結論1行目・15行以内。

- **主張の検証を頼まれたら、動画が言っていることを鵜呑みにしない。** 固有名詞・数値・「公式」の主張は
  WebSearch や実物（GitHub・API）で裏を取ってから可否を書く
- タイムスタンプを出すときは `mm:ss` 形式。フレーム番号 `f_NNNN` は秒数（`-frame_pts` は
  シーン検出時のみ有効なので、正確な秒が要るなら `.srt` かフレーム位置比率から概算する）
- 引用したフレームを見せたいときは `[[IMG:<OUTDIR>/f_NNNN.jpg]]`

## 注意

- TikTokは字幕APIを返さない（`There are no subtitles`が正常）。焼き込み字幕をフレームで読む
- yt-dlpが `Unable to extract` を出したら**まず更新**: `pip3 install -U --break-system-packages yt-dlp`
- 認証が要る動画（限定公開・有料）は取りに行かない
- 出力は `/tmp` に置く。長尺（30分超）はフレーム上限60枚に自動で間引かれる
