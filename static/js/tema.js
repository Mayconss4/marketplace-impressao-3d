// Alternância entre tema claro e escuro (Bootstrap 5.3 data-bs-theme), lembrada no navegador.
(function () {
  var botao = document.getElementById("alternar-tema");
  if (!botao) return;
  var icone = botao.querySelector("[data-icone-tema]");

  function aplicar(tema) {
    document.documentElement.setAttribute("data-bs-theme", tema);
    if (icone) icone.className = tema === "dark" ? "bi bi-sun" : "bi bi-moon-stars";
    botao.setAttribute("title", tema === "dark" ? "Usar tema claro" : "Usar tema escuro");
  }

  aplicar(document.documentElement.getAttribute("data-bs-theme") || "light");
  botao.addEventListener("click", function () {
    var novo = document.documentElement.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
    try { localStorage.setItem("tema", novo); } catch (e) {}
    aplicar(novo);
  });
})();
