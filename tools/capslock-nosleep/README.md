# capslock-nosleep

スリープ抑止を **2 系統に分けて** 自動で出し入れする常駐デーモン。

1. **フタを閉じてもスリープしない（画面だけは消える）** ← **CapsLock が ON の間だけ**
   （手動トグル。キーの LED がそのまま「今スリープしない状態か」の目印）
2. **アイドルスリープしない** ← **Antigravity IDE が起動中の間だけ**
   （フタが開いていればエージェントの作業が止まらない。**フタを閉じれば普通に寝る**）

> 2026-08-26 変更: 以前は Antigravity 起動中も `disablesleep 1`（＝フタを閉じても寝ない）に
> していたが、「フタ閉じの可否は CapsLock だけで決める」に整理し、Antigravity 側は
> `caffeinate -i`（アイドル抑止のみ）に切り替えた。

## 仕組み

root の LaunchDaemon が 1 秒ごとに CapsLock、5 秒ごとに Antigravity の起動有無を見て、
状態が変わったときだけ次を実行する。

| 条件                  | 実行されるコマンド              | 挙動                                       |
| --------------------- | ------------------------------- | ------------------------------------------ |
| CapsLock ON           | `pmset -a disablesleep 1`       | フタを閉じてもスリープしない                 |
| CapsLock ON かつフタ閉 | `pmset displaysleepnow`（15 秒ごとに撃ち直し） | 画面だけ消す                  |
| CapsLock OFF          | `pmset -a disablesleep 0`       | 通常（フタ閉じでスリープ）                   |
| Antigravity 起動中     | `caffeinate -i` を子プロセスで保持 | アイドルスリープしない（フタ閉じには効かない） |
| Antigravity 終了       | その `caffeinate` を terminate  | 通常のアイドルスリープに戻る                 |

2 系統は独立しているので、片方だけ成立していても正しく振る舞う。
スリープ抑止の手段が `disablesleep` 1 つしかなかった頃と違い、**条件を足すときは
「フタ閉じの話」なら既存の CapsLock 判定に OR、「動かし続けたい話」なら `IdleGuard`
側に足す**こと。新規デーモンは作らない（`disablesleep` の取り合いで壊れる）。

CapsLock の読み取りは IOKit の `IOHIDGetModifierLockState`（IOHIDSystem の param
connect）。macOS 標準の `/usr/bin/python3` + ctypes だけで動くので、Homebrew や
外部モジュールに依存しない。

Antigravity の判定は **`ps -axo comm=` に本体パス
`/Applications/Antigravity IDE.app/Contents/MacOS/Electron` が出るか**で見る。
`pgrep -f` はこの Electron の argv を拾えず（`pgrep -f "MacOS/Electron"` が空になる）
使えないので注意。ヘルパープロセスではなく本体だけを見ているので、
アップデータや `Antigravity` の語を含む別コマンドでは誤検知しない。

> Command Line Tools 同梱の clang / swiftc が古く（clang 12）、macOS 26 SDK を
> コンパイルできないため C / Swift ではなく Python + ctypes にしている。

## ファイル

| 置き場所                                                    | 内容                       |
| ----------------------------------------------------------- | -------------------------- |
| `~/Tools/capslock-nosleep/`                                  | ソース（ここが原本）        |
| `/usr/local/bin/capslock-nosleep`                            | インストールされた本体      |
| `/Library/LaunchDaemons/com.local.capslock-nosleep.plist`| 常駐設定（再起動後も自動起動）|
| `/var/log/capslock-nosleep.log`                              | ログ                       |

## 操作

```bash
# インストール / 再インストール（ソースを直したらこれ）
sudo ~/Tools/capslock-nosleep/install.sh

# sudo のパスワードを打てない場面（Claude Code 等）からの再インストール
SRC="$HOME/Tools/capslock-nosleep/capslock-nosleep.py"
osascript -e "do shell script \"/usr/bin/install -m 755 -o root -g wheel $SRC /usr/local/bin/capslock-nosleep && /bin/launchctl kickstart -k system/com.local.capslock-nosleep\" with administrator privileges"

# 完全に削除して通常のスリープ挙動に戻す
sudo ~/Tools/capslock-nosleep/uninstall.sh

# 一時停止 / 再開
sudo launchctl bootout system/com.local.capslock-nosleep
sudo launchctl bootstrap system /Library/LaunchDaemons/com.local.capslock-nosleep.plist

# 今の状態を確認
pmset -g | grep SleepDisabled          # 1 ならフタを閉じても寝ない（＝CapsLock ON）
pmset -g assertions | grep caffeinate  # 出ていればアイドル抑止中（＝Antigravity 起動中）
tail -f /var/log/capslock-nosleep.log
```

## 注意

- **CapsLock を点けたまま鞄に入れない。** フタを閉じても動き続けるため発熱・電池切れになる。
  持ち歩く前に CapsLock の LED が消えていることを確認する。
  Antigravity は起動したままでもフタを閉じれば寝るので、こちらは気にしなくてよい。
- Antigravity を起動しっぱなしにする使い方だと、フタを開けている限りずっとアイドル抑止が
  かかる（画面は `displaysleep` の設定どおり消えるが、本体は寝ない）。「エージェントが
  作業している間だけ」に絞りたい場合は判定を CPU 使用率などに変える必要がある。
- 「Caps Lock キーで英字入力に切り替える」がオンの日本語入力環境では、軽く押すと入力切替に
  なりロック状態が変わらないことがある。その場合は**長押し**するか、キーボード設定を見直す。
- **`disablesleep 1` はフタのイベントを丸ごと無視するので、放っておくとフタを閉じても
  バックライトが点いたまま**になる（2026-08-26 に実測。閉じている間ずっと点灯していた）。
  そのため CapsLock ON の間だけ `AppleClamshellState` を 1 秒ごとに見て、閉じたら
  `pmset displaysleepnow` を撃つ。15 秒ごとに撃ち直すのは、何かが画面を点け直しても
  また消すため。
- **消灯したかの確認に `ioreg` のバックライト値（`BrightnessMicroAmps` / `rawBrightness`）を
  使ってはいけない。** これは「設定中の明るさ」で、消灯しても値が変わらない。
  `pmset -g log | grep "Display is turned"` で見ること。
- 画面が消えると**即ロック**（`sysadminctl -screenLock status` が `immediate`）なので、
  フタを開けるとパスワードを聞かれる。嫌なら システム設定 > ロック画面 で猶予を入れる。
- ディスプレイスリープの**アイドル時間**（`displaysleep 10 分`）は別設定なので触っていない。
- デーモンが強制終了しても、次回起動時に現在の CapsLock 状態へ同期し直すので設定は残らない。
  停止時は `disablesleep 0` に戻し、保持していた `caffeinate` も落とす。
