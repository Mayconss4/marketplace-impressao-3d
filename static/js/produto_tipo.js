// Mostra apenas o inline compatível com o tipo do produto (variações x arquivos digitais).
// A regra também é validada no servidor; este script só melhora a usabilidade.
window.addEventListener("load", function () {
  var seletor = document.getElementById("id_tipo");
  if (!seletor) return;
  function grupo(prefixo) {
    return document.getElementById(prefixo + "-group");
  }
  function atualizar() {
    var variacoes = grupo("variacoes");
    var arquivos = grupo("arquivos");
    if (variacoes) variacoes.style.display = seletor.value === "fisico" ? "" : "none";
    if (arquivos) arquivos.style.display = seletor.value === "digital" ? "" : "none";
  }
  seletor.addEventListener("change", atualizar);
  atualizar();
});
