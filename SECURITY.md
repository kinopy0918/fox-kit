# 安全について

## このキットが入れる設定

- **確認ダイアログを出さない**（`permissions.defaultMode: bypassPermissions`）。AIはファイル操作やコマンドを、いちいち聞かずに実行します。
- 代わりに、次の3つは必ず人に確認する作法を入れています（`~/.claude/fox-kit/rules/craft.md`）。
  1. お金が動く操作（契約・課金・支払い・広告）
  2. 社外に出る・取り消せない操作（送信・投稿・申請・削除・公開範囲を広げる）
  3. 持ち主しか知らない事実や経営判断
- デスクトップ・ダウンロード・ホーム直下への書き捨てを止める見張り（`~/.claude/hooks/guard-output-location.py`）。

## 秘密の扱い

- Discord / Slack の鍵は **Macのキーチェーン** に保存します（ファイルには書きません）。
- パスワード・鍵・個人情報を、記憶・ファイル・チャットに書かない作法を入れています。
- インストーラが覚える答え（`~/.config/fox-kit/state.env`）には、名前と進み具合しか入りません。

## 届けていないもの

このキットは、あなたの会話・記憶・ファイルをどこにも送りません（Claude 本体の通信を除く）。

## 問題を見つけたら

公開の Issue には書かず、GitHub の **Security** タブ →「Report a vulnerability（脆弱性を報告）」から知らせてください。報告は非公開で届きます。
https://github.com/kinopy0918/fox-kit/security/advisories/new
