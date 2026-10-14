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
  document.addEventListener("DOMContentLoaded", function () {
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
  });
})();
