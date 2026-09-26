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
  document.addEventListener("DOMContentLoaded", function () {
    set(lv);
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
