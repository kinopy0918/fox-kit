// はじめて／慣れている の切り替え（この端末にだけ覚える）と、コピーボタン
(function () {
  var KEY = "fox-guide-level";
  function set(lv) {
    document.body.classList.toggle("expert", lv === "expert");
    document.querySelectorAll(".lv button").forEach(function (b) { b.classList.toggle("on", b.dataset.lv === lv); });
    try { localStorage.setItem(KEY, lv); } catch (e) {}
  }
  var lv = "beginner";
  try { lv = localStorage.getItem(KEY) || "beginner"; } catch (e) {}
  // Mac / Windows（はじめは開いている端末から推測し、押したらこの端末に覚える）
  var OSKEY = "fox-guide-os";
  function setOs(os) {
    document.body.classList.toggle("os-win", os === "win");
    document.querySelectorAll(".os button").forEach(function (b) { b.classList.toggle("on", b.dataset.os === os); });
    try { localStorage.setItem(OSKEY, os); } catch (e) {}
  }
  var os = /Windows/i.test(navigator.userAgent) ? "win" : "mac";
  try { os = localStorage.getItem(OSKEY) || os; } catch (e) {}

  // アイコン（線画・Lucide の形を元にした最小限）。<i class="ic" data-i="clock"></i> を絵に置き換える
  var IC = {
    clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    laptop: '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M2 20h20"/>',
    card: '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/>',
    key: '<circle cx="7.5" cy="15.5" r="4.5"/><path d="m10.7 12.3 9.8-9.8M17 6l3 3M14 9l2 2"/>',
    lock: '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    terminal: '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m6 9 3 3-3 3M12 15h5"/>',
    paste: '<rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>',
    tap: '<path d="M9 11V5a2 2 0 0 1 4 0v6M13 10a2 2 0 0 1 4 0v1a2 2 0 0 1 4 0v4a7 7 0 0 1-7 7h-1a7 7 0 0 1-6-3.4L4 15a2 2 0 0 1 3.4-2L9 15"/>',
    chat: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    phone: '<rect x="6" y="2" width="12" height="20" rx="2"/><path d="M11 18h2"/>',
    folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h5"/>',
    brain: '<path d="M12 5a3 3 0 0 0-5.6-1.5A3 3 0 0 0 4 8a3 3 0 0 0 0 6 3 3 0 0 0 3 4 3 3 0 0 0 5 1zM12 5a3 3 0 0 1 5.6-1.5A3 3 0 0 1 20 8a3 3 0 0 1 0 6 3 3 0 0 1-3 4 3 3 0 0 1-5 1z"/>',
    shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
    check: '<circle cx="12" cy="12" r="10"/><path d="m8 12 3 3 5-6"/>',
    alert: '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
    retry: '<path d="M3 12a9 9 0 0 1 15-6.7L21 8M21 3v5h-5M21 12a9 9 0 0 1-15 6.7L3 16M3 21v-5h5"/>',
    power: '<path d="M12 2v10M18.4 6.6a9 9 0 1 1-12.8 0"/>',
    wifi: '<path d="M5 12.6a10 10 0 0 1 14 0M8.5 16.1a5 5 0 0 1 7 0M2 8.8a15 15 0 0 1 20 0M12 20h.01"/>',
    yen: '<path d="m6 3 6 8 6-8M12 11v10M7 13h10M7 17h10"/>',
    out: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
    help: '<circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3M12 17h.01"/>',
    sparkle: '<path d="M12 3l1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2z"/>',
    mail: '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-10 6L2 7"/>',
    search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    upd: '<path d="M12 3v12M7 10l5 5 5-5M4 21h16"/>'
  };
  function icons() {
    document.querySelectorAll("i.ic[data-i]").forEach(function (el) {
      var d = IC[el.dataset.i]; if (!d) return;
      el.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + d + '</svg>';
    });
  }
  // 鍵つきのページは、本文を差し込んだあとに gate.js が foxInit() を呼ぶ
  window.foxInit = function () {
    if (/iPhone|iPad|Android/i.test(navigator.userAgent)) document.body.classList.add("phone");   // 入れる作業はパソコンで、の注意を出す
    icons();
    var how = "term"; try { how = localStorage.getItem("fox-how") || how; } catch (e) {}
    function setHow(h) { document.body.classList.toggle("how-claude", h === "claude");
      document.querySelectorAll(".how button").forEach(function (b) { b.classList.toggle("on", b.dataset.how === h); });
      try { localStorage.setItem("fox-how", h); } catch (e) {} }
    setHow(how);
    document.querySelectorAll(".how button").forEach(function (b) { b.onclick = function () { setHow(b.dataset.how);
      var t = document.querySelector("h2 .for-term"); if (t) t.closest("h2").scrollIntoView({ behavior: "smooth", block: "start" }); }; });
    set(lv);
    setOs(os);
    document.querySelectorAll(".os button").forEach(function (b) { b.onclick = function () { setOs(b.dataset.os); }; });
    document.querySelectorAll(".lv button").forEach(function (b) { b.onclick = function () { set(b.dataset.lv); }; });
    document.querySelectorAll(".cmd").forEach(function (el) {
      var btn = document.createElement("button"); btn.textContent = "コピー";
      btn.onclick = function () {
        var t = el.childNodes[0].textContent.trim();
        navigator.clipboard.writeText(t).then(function () { btn.textContent = "コピーしました"; setTimeout(function () { btn.textContent = "コピー"; }, 1500); });
      };
      el.appendChild(btn);
    });
  };
  document.addEventListener("DOMContentLoaded", function () { if (!document.getElementById("fx")) window.foxInit(); });
})();
