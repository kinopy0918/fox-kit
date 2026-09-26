# fox-bridge — AI と Discord / Slack をつなぐ

- **つなぐ**：`つなぐ.command` をダブルクリック（または `python3 connect.py`）。画面の案内どおりに進めると、
  ボット作成 → 鍵の登録（Macのキーチェーン）→ 招待 → チャンネル作成 → 常駐（launchd `com.fox-bridge`）→ 往復テスト まで終わる。
- **状態を見る**：`python3 connect.py --status` ／ **止める**：`python3 connect.py --stop`
- **しくみ**：決めたチャンネルを数秒おきに見に行き、人の書き込みを `claude -p` に渡して返事を書く（チャンネルごとに会話を続ける）。
  常時接続を使わないので、Slack の接続用トークン（手作業でしか作れない）が要らない。
- 返事に `[[FILE:/絶対パス]]`・`[[IMG:/絶対パス]]` と書くと、そのファイルを添付して送る。
- 記録：`~/Library/Logs/fox-bridge.log`。設定：`~/.config/fox-bridge/config.json`（秘密は入れない）。
- Mac がスリープしている間は返事をしない。常に返事をさせたい端末では、電源につないでスリープしない設定にする。
