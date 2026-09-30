// fox-kit 設定画面：いまやること1つだけを大きく出し、押したら裏でこのMacが作業する
(function () {
  const T = new URLSearchParams(location.search).get("t");
  const $ = (s, el) => (el || document).querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  let S = null;              // サーバーの状態
  let view = null;           // いま描いている段（入力中に描き直さないため）
  let local = {};            // 段の中の途中経過（画面だけのもの）
  const B = () => (S?.answers?.level || "beginner") === "beginner";
  const t = (b, e) => (B() ? b : e);

  async function api(path, body) {
    const r = await fetch(path + (path.includes("?") ? "&" : "?") + "t=" + T, body ? {
      method: "POST", headers: { "Content-Type": "application/json", "X-Token": T }, body: JSON.stringify(body)
    } : {});
    return r.json();
  }
  const act = (step, body) => api("/api/act/" + step, body || {});
  const shot = (name, cap) => `<figure class="shot" data-shot="${name}"><img src="/static/img/${name}.png" alt="${esc(cap)}" onerror="this.closest('figure').remove()"><figcaption>${esc(cap)}</figcaption></figure>`;
  const k = (en, ja) => `<span class="k">${esc(en)}${ja ? `<i>（${esc(ja)}）</i>` : ""}</span>`;
  const job = (name) => S?.jobs?.[name];
  const md = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/^#{1,4}\s*(.+)$/gm, "<b>$1</b>").replace(/^[-・]\s+/gm, "・");

  // ---------------------------------------------------------------- 各段
  const V = {
    level: () => ({
      title: "はじめに1つだけ教えてください",
      lead: "答えに合わせて、この先の案内と、入れたあとのAIの話し方を変えます。",
      html: `<button class="choice" data-lv="beginner" style="width:100%;text-align:left"><b>はじめて・よくわからない</b><small>むずかしい言葉を使わずに案内します（おすすめ）</small></button>
             <button class="choice" data-lv="expert" style="width:100%;text-align:left"><b>AIやパソコンの設定に慣れている</b><small>短く、専門用語のまま案内します</small></button>`,
      bind: (el) => el.querySelectorAll("[data-lv]").forEach((b) => (b.onclick = async () => { await act("level", { level: b.dataset.lv }); refresh(true); })),
    }),
    names: () => {
      const a = S.answers;
      return {
        title: t("あなたとAIの名前を決めましょう", "基本情報"),
        lead: t("AIはこの名前で名乗り、あなたの秘書として動きます。", "CLAUDE.md の人格に入ります（あとから AI に頼めば書き換え可）"),
        html: `<label class="f">このMacを使う人のお名前</label><input class="t" id="owner" placeholder="例：山田さん" value="${esc(a.owner)}">
               <label class="f">AIの名前</label><input class="t" id="agent" placeholder="例：ヤマダAI" value="${esc(a.agent || "")}">
               <label class="f">このMacの呼び方 <span class="hint">（空欄でも大丈夫）</span></label><input class="t" id="machine" placeholder="例：事務所のMac" value="${esc(a.machine)}">
               <label class="f">このMacで主にすること <span class="hint">（空欄でも大丈夫）</span></label><input class="t" id="role" placeholder="例：経理の仕事" value="${esc(a.role)}">
               <div class="note"><b>あとから変えられますか？</b>
                 <ul><li><b>どれも変えられます。</b>あとで AI に「私の呼び方を〇〇に変えて」「あなたの名前を〇〇に変えて」と頼むだけです。</li>
                 <li>ただし<b>AIの名前</b>を変えても、Slack・Discord に出るAIの表示名と、資料フォルダの名前は元のままです（そこも変えたいときは AI に頼めば手順を案内します）。迷ったら、今のうちに決めておくのがおすすめです。</li></ul></div>
               <div class="err" id="err"></div><div class="row"><button class="btn" id="go">この名前で進む</button></div>`,
        bind: (el) => ($("#go", el).onclick = async () => {
          const r = await act("names", { owner: $("#owner").value, agent: $("#agent").value, machine: $("#machine").value, role: $("#role").value });
          if (!r.ok) return ($("#err").textContent = r.error);
          refresh(true);
        }),
      };
    },
    claude: () => autoStep("claude", t("AIの本体を入れています", "Claude Code を導入"), t("数分かかります。この画面はそのままで大丈夫です。", "claude.ai/install.sh")),
    login: () => ({
      title: t("AIのアカウントにログインします", "Claude にログイン"),
      lead: t("AIを動かすための契約（Claude）にログインします。会社のMacなら、会社で契約したアカウントを使ってください。", "claude auth login（コード貼り付け方式）"),
      html: `<ol class="do">
               <li>下の ${k("ログイン画面を開く")} を押す（新しいタブが開きます）</li>
               <li>開いた画面でアカウントを選び、${k("Authorize", "許可する")} を押す</li>
               <li>画面に出た長いコード（英数字）の下の ${k("コードをコピー")} を押す</li>
               <li>この画面に戻って、下の欄に貼り付けて ${k("送る")}。うまくいけば自動で次へ進みます</li>
             </ol>
             <div class="note"><ul>
               <li>コードの画面に「Claude Code に貼り付けてください」と出ますが、<b>この画面の欄に貼れば大丈夫です</b>（Claude Code は、いま入れたAIの本体の名前です）。</li>
               <li>「Claude Code に接続するには Pro または Max が必要です」と出たら、無料のままでは使えません。その画面から申し込み（Pro は月20ドルほど）、終わったらこの画面に戻って、もう一度 ${k("ログイン画面を開く")} を押してください。</li></ul></div>
             ${shot("login-1", "ログインの画面（アカウントを選んで「許可する」）")}
             ${shot("login-2", "コードが表示された画面（右のボタンでコピー）")}
             <div class="row"><button class="btn" id="open">ログイン画面を開く</button></div>
             <label class="f">表示されたコード</label><input class="t" id="code" placeholder="ここに貼り付け" autocomplete="off">
             <div class="err" id="err"></div>
             <div class="row"><button class="btn" id="send">送る</button></div>`,
      bind: (el) => {
        $("#open", el).onclick = async () => {
          const w = window.open("about:blank", "_blank");
          $("#err").textContent = "";
          const r = await act("login", {});
          if (r.ok && r.url) { w ? (w.location = r.url) : window.open(r.url, "_blank"); }
          else { w && w.close(); $("#err").textContent = "ログイン画面を用意できませんでした：" + (r.error || ""); }
        };
        $("#send", el).onclick = async () => {
          $("#send").disabled = true; $("#err").innerHTML = '<span class="spin"></span>確かめています…';
          const r = await act("login", { code: $("#code").value });
          $("#send").disabled = false;
          r.ok ? refresh(true) : ($("#err").textContent = r.error);
        };
        act("login", { check: true }).then((r) => r.ok && refresh(true));   // 前にログイン済みなら黙って次へ
      },
    }),
    build: () => autoStep("build", t("あなた専用に組み立てています", "組み立て（install.sh）"), t("仕事の作法・資料のチェック役・話し方の設定などを入れています（1分ほど）。", "人格・作法・スキル・settings・hooks・点検")),
    mac: () => ({
      title: t("パソコンの設定", "Mac 設定（電源・Chrome・Antigravity）"),
      lead: t("このMacの使い方に合わせて、眠る・眠らないの設定をします。途中でMacのパスワードを聞かれます。", "pmset / capslock-nosleep / Chrome（既定ブラウザ）/ Antigravity IDE"),
      html: job("mac")?.state === "running" ? running("mac", t("設定しています。パスワードの画面が出たら入れてください。「いつも使うブラウザを変えますか？」と出たら「“Google Chrome”を使用」を押してください。", "実行中（既定ブラウザの確認ダイアログあり）")) : `
             <label class="choice"><input type="radio" name="use" value="office" checked><b>事務所などに置いて、AIにいつでも働いてもらう</b><small>電源につないでいる間は眠らない・停電のあと自動で起動（おすすめ）</small></label>
             <label class="choice"><input type="radio" name="use" value="mobile"><b>持ち歩いて、使うときだけ動けばよい</b><small>作業中だけ眠らない仕組みを入れます（CapsLockのランプが点いている間）</small></label>
             <label class="choice"><input type="checkbox" id="lid"><b>ふたを閉じたまま置いておく</b><small>ノートのMacを閉じたまま使う場合だけ。電源につなぎ、熱がこもらない場所に置いてください</small></label>
             <label class="choice"><input type="checkbox" id="chrome" checked><b>Chrome を入れて、いつも使うブラウザにする</b><small>AIがブラウザを操作する機能は Chrome で動きます。途中で「いつも使うブラウザを変えますか？」と出たら「“Google Chrome”を使用」を押してください</small></label>
             <label class="choice"><input type="checkbox" id="ag" checked><b>Antigravity（AIと画面で一緒に作業する編集ソフト）も入れる</b><small>中で Claude Code も使えます。画面は日本語にします</small></label>
             ${shot("mac-password", "この画面が出たら、Macのパスワードを入れて「OK」")}
             ${failNote("mac")}
             <div class="row"><button class="btn" id="go">この内容で設定する</button><button class="btn sub" id="skip">あとでやる</button></div>`,
      bind: (el) => {
        const go = $("#go", el); if (!go) return;
        go.onclick = async () => {
          await act("mac", { use: $("input[name=use]:checked").value, lid: $("#lid").checked, chrome: $("#chrome").checked, antigravity: $("#ag").checked });
          refresh(true);
        };
        $("#skip", el).onclick = async () => { await act("skip", { target: "mac" }); refresh(true); };
      },
    }),
    packs: () => {
      const g = S.data.gemini;
      const reg = g && !g.skipped, pj = job("packs")?.state;
      const status = pj === "error" ? failNote("packs")
        : pj === "ok" || S.steps.find((x) => x.id === "packs")?.done
          ? `<p class="okmsg">✓ スキルと道具はそろいました</p>${reg ? "" : `<p><b>あとは下の鍵だけです。</b>「登録」か「あとでやる」を押すと次へ進みます。</p>`}`
          : running("packs", t("入れています…この画面はそのままで大丈夫です。途中でMacのパスワードを聞かれることがあります。", "実行中"));
      return {
        title: t("スキルと道具をそろえています", "packs"),
        lead: t("SEO・動画・ノート・画像づくり・意味で探す・ブラウザ操作などを入れます（はじめてだと20分ほど）。待っている間に、下の「画像づくりの鍵」を済ませておくと早く終わります。",
                "brew / plugins / upstream skills / MCP"),
        html: `${status}
               <div class="sub-card"><b>画像づくり・意味で探す のための鍵（Google の Gemini）</b> ${reg ? '<span class="okmsg">✓ 登録できました</span>' : g?.skipped ? '<span class="hint">あとでやる（いまは未登録）</span>' : '<span class="who you">まだです</span>'}
               ${reg || g?.skipped ? "" : `<ol class="do">
                 <li>${k("鍵を作る画面を開く")} を押す</li>
                 <li>Google アカウントでログイン（会社で使うなら会社のアカウント）</li>
                 <li>${k("Create API key", "APIキーを作成")} → できた長い文字列の横のコピーを押す（前に作った鍵が一覧にあれば、それを開いてコピーしても大丈夫）</li>
                 <li>下の欄に貼って ${k("登録")}</li></ol>
                 ${shot("gemini-1", "Google AI Studio の鍵の画面")}
                 <div class="row"><a class="btn sub" href="https://aistudio.google.com/apikey" target="_blank">鍵を作る画面を開く</a></div>
                 <input class="t" id="gkey" placeholder="ここに貼り付け（AIza で始まる）" autocomplete="off"><div class="err" id="gerr"></div>
                 <div class="row"><button class="btn" id="greg">登録</button><button class="btn sub" id="gskip">あとでやる</button></div>
                 <p class="hint">「あとでやる」にしても、あとで AI に「画像づくりの鍵を登録したい」と言えば、鍵を入れる小さな窓が開きます。</p>`}</div>`,
        bind: (el) => {
          if (!job("packs")) act("packs");
          const reg = $("#greg", el);
          if (reg) {
            reg.onclick = async () => { const r = await act("gemini", { key: $("#gkey").value }); r.ok ? refresh(true) : ($("#gerr").textContent = r.error); };
            $("#gskip", el).onclick = async () => { await act("skip", { target: "gemini" }); refresh(true); };
          }
          const retry = $("#retry", el); if (retry) retry.onclick = async () => { await act("packs"); refresh(true); };
        },
      };
    },
    storage: () => ({
      title: t("資料の保存先を決めます", "保存先"),
      lead: t("AIが作ったもの・受け取ったものを置く場所です。Google ドライブにすると、Macが壊れても残り、スマホからも見られます。", "storage.py apply（FOX型11フォルダ・目次・記憶の移動）"),
      html: `<div id="places"><span class="spin"></span>このMacの保存先を調べています…</div>
             <div class="sub-card"><b>フォルダの形</b>
               <label class="choice"><input type="radio" name="layout" value="fox" checked><b>しっかり整理する形（おすすめ）</b><small>案件・議事録・記録・手順・テンプレート・タスク・メモ・AIの記憶・目標・保管庫の11フォルダ</small></label>
               <label class="choice"><input type="radio" name="layout" value="simple"><b>簡単な形</b><small>5フォルダだけ。まずは小さく始めたい方に</small></label>
               <label class="choice"><input type="checkbox" id="idx" checked><b>作業が終わるたびに目次を自動で作り直す</b><small>AIは目次を見て、関係のある所だけを読みに行きます（速く正確）</small></label></div>
             <div class="err" id="err"></div><div class="row"><button class="btn" id="go">ここに決める</button></div>`,
      bind: async (el) => {
        const r = await act("storage", { detect: true });
        const list = (r.folders || []);
        const hasG = list.some((f) => f.kind.startsWith("Google"));
        $("#places", el).innerHTML = list.map((f, i) => `<label class="choice"><input type="radio" name="root" value="${esc(f.path)}" ${i === 0 ? "checked" : ""}><b>${esc(f.kind)}</b><small>${esc(f.account || "")}${f.kind.includes("このMac") ? "　※Macが壊れると消えます" : ""}</small></label>`).join("")
          + (list.some((f) => f.name) ? `<p class="hint">AI専用の共有ドライブを新しく作りたいときは、<a href="https://drive.google.com/drive/shared-drives" target="_blank">Google ドライブの共有ドライブの画面</a>で「＋新規」→ 名前（例：${esc(S.answers.agent || "AI")}）→「作成」を押してから、下の ${k("もう一度調べる")} を押してください。</p><div class="row"><button class="btn sub" id="again">もう一度調べる</button></div>` : "")
          + (hasG ? "" : `<div class="sub-card"><b>Google ドライブを使うなら（おすすめ）</b><ol class="do"><li>${k("Google ドライブのアプリを入れる")} を押す（Macのパスワードを聞かれます）</li><li>開いたアプリで<b>会社の Google アカウント</b>でログイン</li><li>ログインできたら ${k("もう一度調べる")}</li></ol>${shot("drive-1", "Google ドライブのアプリのログイン画面")}
             <div class="row"><button class="btn sub" id="drive">Google ドライブのアプリを入れる</button><button class="btn sub" id="again">もう一度調べる</button></div>${running("drive", "")}</div>`);
        const d = $("#drive", el); if (d) d.onclick = async () => { await act("storage", { install_drive: true }); refresh(true); };
        el.querySelectorAll("#again").forEach((ag) => (ag.onclick = () => { view = null; refresh(true); }));
        $("#go", el).onclick = async () => {
          const root = $("input[name=root]:checked")?.value;
          $("#err").innerHTML = '<span class="spin"></span>作っています…';
          const x = await act("storage", { root, layout: $("input[name=layout]:checked").value, auto_index: $("#idx").checked });
          x.ok ? refresh(true) : ($("#err").textContent = x.error);
        };
      },
    }),
    channel: () => channelView(),
    talk: () => ({
      title: t("AIと最初のお話", "初期設定の聞き取り（fox-setup）"),
      lead: t("AIがあなたの仕事について、1つずつ質問します（全部で7つ・10〜15分）。AIが「初期設定が終わりました」と言ったら、下の「ここで終える」を押してください。", "claude -p --resume（この画面のチャット）。fox-setup が完了を告げたら終える"),
      html: `<div class="chat" id="chat"></div><div class="err" id="err"></div>
             <textarea class="t" id="msg" rows="2" placeholder="ここに入力して「送る」（Shift＋Enterで改行）"></textarea>
             <div class="row"><button class="btn" id="send">送る</button><button class="btn sub" id="fin">ここで終える</button></div>
             <div id="finNote" class="note" hidden><b>✓ 初期設定が終わりました。</b>下の「ここで終える」を押してください。この先は Slack・Discord のチャンネルで話しかければ続きができます。</div>
             <p class="hint">途中でやめても大丈夫です。続きは、あとで AI に「初期設定の続きをして」と言えば、終わったところから再開します。</p>`,
      bind: (el) => {
        local.chat = local.chat || [];
        const draw = () => { $("#chat").innerHTML = local.chat.map((m) => `<div class="msg ${m.who}">${m.who === "ai" ? md(m.text) : esc(m.text)}</div>`).join(""); $("#chat").scrollTop = 1e9; };
        const send = async (text) => {
          if (text) local.chat.push({ who: "me", text });
          local.chat.push({ who: "ai", text: "…考えています" }); draw();
          $("#send").disabled = true;
          const r = await act("talk", { message: text || "" });
          local.chat.pop(); $("#send").disabled = false;
          r.ok ? local.chat.push({ who: "ai", text: r.reply }) : ($("#err").textContent = r.error);
          draw(); finCheck();
        };
        const finCheck = () => {
          const last = [...local.chat].reverse().find((m) => m.who === "ai")?.text || "";
          if (/初期設定(が|は)?(すべて|全部)?(終わり|完了し)/.test(last)) {
            $("#finNote").hidden = false; $("#fin").className = "btn"; $("#send").className = "btn sub";
          }
        };
        draw(); finCheck();
        if (!local.chat.length) send("");
        $("#send", el).onclick = () => { const v = $("#msg").value.trim(); if (!v) return; $("#msg").value = ""; send(v); };
        $("#msg", el).onkeydown = (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); $("#send").click(); } };
        $("#fin", el).onclick = async () => { await act("talk", { finish: true }); refresh(true); };
      },
    }),
    done: () => ({
      title: t("おつかれさまでした。すべて完了です", "完了"),
      lead: t(`これで ${S.answers.agent || "AI"} があなたの秘書として動けます。`, "セットアップ完了"),
      html: (() => {
        const ch = S.data.channel || {}, where = ch.platform === "slack" ? "Slack" : ch.platform === "discord" ? "Discord" : "";
        const base = S.data.storage?.base || "", folder = base.split("/").pop();
        const drive = base.includes("/共有ドライブ/") ? "Google ドライブの共有ドライブ" : base.includes("GoogleDrive-") ? "Google ドライブ" : "このMac";
        const g = S.data.gemini;
        return `<div class="sub-card"><b>これからの使い方</b>
               <ul class="done-list">
               ${where ? `<li><b>用事も、困ったことも、ぜんぶ ${where} のチャンネルで ${esc(S.answers.agent || "AI")} に話しかけてください。</b>スマホからでもOKです。<div class="row"><a class="btn" href="${esc(ch.link)}" target="_blank">${where} のチャンネルを開く</a></div></li>
               <li>話しかけ方の例：「〇〇の資料を作って」「この請求書を確認して」「調子を見て」「設定を変えたい」「新しい版に更新して」</li>`
                 : `<li>いまは Slack・Discord につないでいません。つなぎたくなったら、担当者に連絡してください。</li>`}
               ${base ? `<li>資料は ${drive} の「${esc(folder)}」フォルダに整理して置きます。<div class="row"><button class="btn sub" id="openBase">フォルダを開く</button></div></li>` : ""}
               ${g && !g.skipped ? "" : `<li>あとでできること：画像づくりの鍵の登録（${where || "AI"} に「画像づくりの鍵を登録したい」と言うだけ）</li>`}
               </ul></div>
             <details class="sub-card"${B() ? "" : " open"}><summary><b>パソコンに慣れている方へ：Antigravity から指示する</b></summary>
               <p>このMacの前で作業するときは、<b>Antigravity</b>（AIと一緒に作業する編集ソフト）から話しかけるのがいちばん速くて便利です。ファイルを見ながら直してもらえて、${esc(S.answers.agent || "AI")} と同じ設定・記憶で動きます。</p>
               <ol class="do"><li>Dock か「アプリケーション」から ${k("Antigravity")} を開く（はじめはGoogleアカウントでログイン）</li>
                 <li>上のメニューの「ファイル」→「フォルダーを開く」で、ホーム（家のマーク・${esc((S.home || "").split("/").pop())}）を選ぶ</li>
                 <li>右上か左はしの Claude のマーク（✳）を押すと、会話の欄が開きます。そこに頼みごとを書く</li></ol>
               <p class="hint">入っていない・使い方を詳しく知りたいときは、${where || "AI"} で「Antigravity の使い方を教えて」と聞いてください。</p></details>
             <p class="hint">この画面は閉じて大丈夫です。</p>`;
      })(),
      bind: (el) => { const o = $("#openBase", el); if (o) o.onclick = () => act("storage", { open_base: true }); },
    }),
  };

  function running(name, msg) {
    const j = job(name);
    if (!j) return "";
    const lg = B() ? "" : `<pre class="log">${esc(j.tail)}</pre>`;
    if (j.state === "running") return `<p><span class="spin"></span>${esc(msg)}</p>${lg}`;
    if (j.state === "ok") return `<p class="okmsg">✓ 終わりました</p>`;
    return failNote(name);
  }
  function failNote(name) {
    const j = job(name);
    if (!j || j.state !== "error") return "";
    return `<div class="err">うまくいきませんでした。もう一度押してみてください。続くときは、この画面を開いたまま担当者に連絡してください。</div><pre class="log">${esc(j.tail)}</pre><div class="row"><button class="btn sub" id="retry">もう一度</button></div>`;
  }
  function autoStep(name, title, lead) {
    return {
      title, lead,
      html: running(name, t("進めています…", "実行中")) || `<p><span class="spin"></span>${t("始めています…", "開始")}</p>`,
      bind: (el) => {
        if (!job(name)) act(name);
        const r = $("#retry", el); if (r) r.onclick = async () => { await act(name); refresh(true); };
      },
    };
  }

  // ---------------------------------------------------------------- Discord / Slack
  function channelView() {
    const d = S.data.channel || {};
    const p = d.platform;
    if (!p) return {
      title: t("スマホからAIと話せるようにします", "連絡手段"),
      lead: t("ふだん使っているチャットアプリにAIを呼びます。つなぐと、スマホからでも話しかけられます。", "fox-bridge"),
      html: `<button class="choice" data-p="discord" style="width:100%;text-align:left"><b>Discord（無料・スマホでも使いやすい。おすすめ）</b><small>AI専用の部屋を作ります（10分ほど）</small></button>
             <button class="choice" data-p="slack" style="width:100%;text-align:left"><b>Slack（会社で既に使っているなら）</b><small>会社のワークスペースにAI用のチャンネルを作ります</small></button>
             <button class="choice" data-p="none" style="width:100%;text-align:left"><b>いまはつながない</b><small>あとから <code>fox-kit connect</code> でつなげます</small></button>`,
      bind: (el) => el.querySelectorAll("[data-p]").forEach((b) => (b.onclick = async () => { await act("channel", { do: "choose", platform: b.dataset.p }); refresh(true); })),
    };
    if (p === "discord") {
      if (!d.bot) return {
        title: t("Discord：AIの分身（ボット）を作る", "Discord Bot 作成"),
        lead: t("英語の画面が出てきます。押すボタンは（ ）に日本語の意味を書いています。", "Developer Portal"),
        html: `<div class="sub-card"><b>まだ AI の部屋（サーバー）が無ければ先に作る</b><ol class="do"><li>${k("Discord を開く")} を押す（アカウントが無ければ作成）</li><li>画面の左はしの ${k("＋", "サーバーを追加")} →「オリジナルの作成」→「自分と友達のため」→ 名前を入れて「新規作成」</li></ol>
               ${shot("discord-server", "左はしの「＋」からサーバーを作る")}<div class="row"><a class="btn sub" href="https://discord.com/channels/@me" target="_blank">Discord を開く</a></div></div>
               <ol class="do">
                 <li>${k("開発者の画面を開く")} を押す</li>
                 <li>右上の ${k("New Application", "新しいアプリ")} → 名前に「${esc(S.answers.agent || "AI")}」→ 同意にチェック → ${k("Create", "作成")}</li>
                 <li>左の一覧の ${k("Bot")} を押す</li>
                 <li>${k("Reset Token", "鍵を作り直す")} → ${k("Yes, do it!", "はい")}（パスワードを聞かれたら入れる）</li>
                 <li>出てきた長い文字列の ${k("Copy", "コピー")} → 下の欄に貼り付けて ${k("確かめる")}</li>
               </ol>
               ${shot("discord-app", "「New Application」で名前を入れて作成")}
               ${shot("discord-token", "「Bot」の画面の「Reset Token」→「Copy」")}
               <div class="row"><a class="btn sub" href="https://discord.com/developers/applications" target="_blank">開発者の画面を開く</a></div>
               <input class="t" id="tok" placeholder="ここに貼り付け（画面には隠れて表示されます）" type="password" autocomplete="off"><div class="err" id="err"></div>
               <div class="row"><button class="btn" id="go">確かめる</button><button class="btn sub" id="back">Slack にする／やめる</button></div>`,
        bind: (el) => {
          $("#go", el).onclick = async () => { $("#err").innerHTML = '<span class="spin"></span>確かめています…'; const r = await act("channel", { do: "token", token: $("#tok").value }); if (r.ok) { local.invite = r.invite; refresh(true); } else $("#err").textContent = r.error; };
          $("#back", el).onclick = async () => { await act("channel", { do: "choose", platform: "" }); refresh(true); };
        },
      };
      if (!d.guild) return {
        title: t("Discord：ボットをサーバーに招待する", "招待"),
        lead: t(`ボット「${d.bot}」とつながりました。次は、AIの部屋に招待します。`, `bot: ${d.bot}`),
        html: `${d.mc ? "" : `<div class="sub-card"><b>先にこれだけ</b>：さっきの Bot の画面を下へスクロールし ${k("MESSAGE CONTENT INTENT", "文章を読む許可")} をオン → ${k("Save Changes", "保存")}${shot("discord-intent", "「MESSAGE CONTENT INTENT」をオンにして保存")}</div>`}
               <ol class="do"><li>${k("招待の画面を開く")} を押す</li><li>「サーバーに追加」の欄から、AIの部屋を選ぶ</li><li>${k("はい")} → ${k("認証")}（人間かどうかの確認が出たら答える）</li><li>この画面に戻って ${k("招待しました")}</li></ol>
               ${shot("discord-invite", "招待の画面でサーバーを選んで「認証」")}
               <div class="row"><a class="btn sub" id="inv" target="_blank">招待の画面を開く</a></div><div class="err" id="err"></div>
               <div class="row"><button class="btn" id="go">招待しました</button></div>`,
        bind: (el) => {
          const inv = $("#inv", el); inv.href = local.invite || `https://discord.com/oauth2/authorize?client_id=${d.app_id}&scope=bot&permissions=117840`;
          $("#go", el).onclick = async () => { $("#err").innerHTML = '<span class="spin"></span>確かめています…'; const r = await act("channel", { do: "joined" }); r.ok ? refresh(true) : ($("#err").textContent = r.error); };
        },
      };
    }
    if (p === "slack" && !d.team) return {
      title: t("Slack：AIの分身（アプリ）を作る", "Slack App（マニフェスト）"),
      lead: t("英語の画面が出てきます。設定はもう入った状態で開くので、押していくだけです。会社の Slack では管理者の許可が要ることがあります。", "manifest 入りの作成リンク → Install → xoxb"),
      html: `<ol class="do">
               <li><b>先に、このブラウザで Slack にログイン</b>しておきます：${k("Slack を開く")} を押して、会社のワークスペースが開けばOK（開けたらこの画面に戻る）</li>
               <li>${k("アプリを作る画面を開く")} を押す</li>
               <li>「Pick a workspace」でAIを入れるワークスペースを選ぶ → ${k("Next", "次へ")} → ${k("Create", "作成")}（選べるものが無いときは 1 のログインがまだです）</li>
               <li>${k("Install to Workspace", "ワークスペースに入れる")} → ${k("許可する")}（押しても進まないときは、少し待ってからもう一度）</li>
               <li>入れ終わると英語の設定画面になります。左の一覧の ${k("OAuth & Permissions", "許可の設定")} を押し、<b>少し下へスクロール</b>した「OAuth Tokens」の ${k("Bot User OAuth Token")}（xoxb- で始まる）の ${k("Copy")}</li>
               <li>下の欄に貼り付けて ${k("確かめる")}</li></ol>
             ${shot("slack-create", "ワークスペースを選んで作成")}
             ${shot("slack-token", "「OAuth & Permissions」の Bot User OAuth Token をコピー")}
             <div class="row"><a class="btn sub" href="https://app.slack.com/" target="_blank">Slack を開く</a><button class="btn sub" id="man">アプリを作る画面を開く</button></div>
             <input class="t" id="tok" placeholder="xoxb- で始まる文字列を貼り付け" type="password" autocomplete="off"><div class="err" id="err"></div>
             <div class="row"><button class="btn" id="go">確かめる</button><button class="btn sub" id="back">Discord にする／やめる</button></div>`,
      bind: (el) => {
        $("#man", el).onclick = async () => { const w = window.open("about:blank", "_blank"); const r = await act("channel", { do: "manifest" }); w.location = r.url; };
        $("#go", el).onclick = async () => { $("#err").innerHTML = '<span class="spin"></span>確かめています…'; const r = await act("channel", { do: "token", token: $("#tok").value }); r.ok ? refresh(true) : ($("#err").textContent = r.error); };
        $("#back", el).onclick = async () => { await act("channel", { do: "choose", platform: "" }); refresh(true); };
      },
    };
    return {
      title: t("つながったか試します", "往復テスト"),
      lead: t("AIのチャンネルで「はじめまして」と送ってください。AIが返事をしたら完了です。", "常駐（launchd com.fox-bridge）起動済み"),
      html: `<ol class="do"><li>${k("チャンネルを開く")} を押す</li>${p === "slack" ? `<li>下に ${k("チャンネルに参加する")} と出ていたら押す（参加しないと送れません）</li>` : ""}<li>AIの案内の下に「はじめまして」と送る</li><li>返事が来たら、この画面が自動で次へ進みます</li></ol>
             ${shot("channel-test", "チャンネルで「はじめまして」と送ると返事が来る")}
             <div class="row"><a class="btn" href="${esc(d.link)}" target="_blank">チャンネルを開く</a></div>
             <p><span class="spin"></span>${t("返事を待っています…", "応答待ち")}</p>`,
      bind: () => { local.poll = setInterval(async () => { const r = await act("channel", { do: "check" }); if (r.ok) { clearInterval(local.poll); refresh(true); } }, 4000); },
    };
  }

  // ---------------------------------------------------------------- 描画
  function draw(force) {
    const cur = S.current;
    const steps = S.steps.filter((s) => s.id !== "done");
    const n = steps.filter((s) => s.done).length;
    $("#progText").textContent = cur === "done" ? "すべて完了しました" : `全${steps.length}ステップの ${n + 1}番目：${steps.find((s) => s.id === cur)?.title || ""}`;
    $("#progBar").style.width = Math.round((n / steps.length) * 100) + "%";
    $("#steps").innerHTML = S.steps.map((s, i) => `<div class="st ${s.done ? "done" : s.id === cur ? "now" : ""}"><i>${s.done ? "✓" : s.id === "done" ? "★" : i + 1}</i>${esc(s.title)}</div>`).join("");
    const sig = cur + "|" + JSON.stringify(S.jobs[cur] ? S.jobs[cur].state : "") + "|" + JSON.stringify(S.data[cur] || {}) + "|" + (cur === "packs" ? JSON.stringify(S.data.gemini || {}) : "");
    if (!force && view === sig) {           // 同じ段なら、動いている作業の表示だけ更新（入力中を消さない）
      document.querySelectorAll("pre.log").forEach((pre) => { const j = S.jobs[cur]; if (j) pre.textContent = j.tail; });
      return;
    }
    if (local.poll) { clearInterval(local.poll); local.poll = null; }
    view = sig;
    const def = (V[cur] || V.done)();
    const who = cur === "done" ? "" : S.steps.find((s) => s.id === cur)?.who;
    $("#main").innerHTML = `<div class="card"><div class="kicker">いまやること${who ? `<span class="who ${who}">${who === "you" ? "あなたの操作" : "自動で進みます"}</span>` : ""}</div><h1>${esc(def.title)}</h1><p class="lead">${esc(def.lead)}</p><div id="body">${def.html}</div></div>`;
    def.bind($("#body"));
  }
  async function refresh(force) {
    try { S = await api("/api/state"); draw(force); } catch (e) { $("#progText").textContent = "このMacとの通信が切れました。ターミナルでもう一度1行を貼ってください。"; }
  }
  refresh(true);
  setInterval(() => refresh(false), 2000);
})();
