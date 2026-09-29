#!/bin/zsh
# sudo が Mac のパスワードを聞くときに、ふつうの入力画面（ダイアログ）を出す
/usr/bin/osascript -e 'text returned of (display dialog "AI秘書の設定を進めるために、このMacのパスワード（ログインのときのもの）を入れてください。" default answer "" with hidden answer with title "fox-kit" with icon caution buttons {"やめる", "OK"} default button "OK")'
