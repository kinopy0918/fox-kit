// 手順書の鍵：パスワードから鍵を作って本文を復号し、ページに差し込む（site_build.mjs と対）
(function () {
  var K = "fox-guide-key";
  try { if (localStorage.getItem(K) || sessionStorage.getItem(K)) document.documentElement.classList.add("chk"); } catch (e) {}
  var b64 = function (s) { return Uint8Array.from(atob(s), function (c) { return c.charCodeAt(0); }); };
  var to64 = function (u) { return btoa(String.fromCharCode.apply(null, new Uint8Array(u))); };
  async function open(key, fx) {
    var plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv: b64(fx.i) }, key, b64(fx.c));
    var d = JSON.parse(new TextDecoder().decode(plain));
    document.title = d.title;
    document.body.innerHTML = d.body;
    if (window.foxInit) window.foxInit();
  }
  async function derive(pw, fx) {
    var base = await crypto.subtle.importKey("raw", new TextEncoder().encode(pw), "PBKDF2", false, ["deriveKey"]);
    return crypto.subtle.deriveKey({ name: "PBKDF2", salt: b64(fx.s), iterations: fx.n, hash: "SHA-256" }, base,
      { name: "AES-GCM", length: 256 }, true, ["decrypt"]);
  }
  document.addEventListener("DOMContentLoaded", async function () {
    var el = document.getElementById("fx"); if (!el) return;
    var fx = JSON.parse(el.textContent);
    var saved = null;
    try { saved = localStorage.getItem(K) || sessionStorage.getItem(K); } catch (e) {}
    if (saved) {
      try { var k = await crypto.subtle.importKey("raw", b64(saved), "AES-GCM", true, ["decrypt"]); await open(k, fx); return; }
      catch (e) { try { localStorage.removeItem(K); sessionStorage.removeItem(K); } catch (e2) {} }
    }
    document.documentElement.classList.remove("chk");
    var f = document.getElementById("gate"), err = document.getElementById("err"), go = document.getElementById("go");
    f.onsubmit = async function (ev) {
      ev.preventDefault();
      var pw = document.getElementById("pw").value.trim();
      if (!pw) { err.textContent = "パスワードを入れてください"; return; }
      go.disabled = true; err.textContent = ""; go.textContent = "確かめています…";
      var keep = document.getElementById("keep").checked;   // 本文を差し込むと消えるので先に読む
      try {
        var key = await derive(pw, fx);
        await open(key, fx);
        var raw = to64(await crypto.subtle.exportKey("raw", key));
        try { if (keep) localStorage.setItem(K, raw); } catch (e) {}
        try { sessionStorage.setItem(K, raw); } catch (e) {}
      } catch (e) {
        go.disabled = false; go.textContent = "開く";
        err.textContent = "パスワードが違います（大文字・小文字に注意）";
      }
    };
  });
})();
