// Muestra u oculta los campos que dependen de la respuesta a otro campo.
// Uso en la plantilla:  <div data-depende-de="instrumento" data-valores="otro,dos_o_mas">…</div>
(function () {
  function valorDe(controles) {
    for (var i = 0; i < controles.length; i++) {
      var c = controles[i];
      if (c.type !== "radio") return c.value;
      if (c.checked) return c.value;
    }
    return "";
  }

  document.querySelectorAll("[data-depende-de]").forEach(function (bloque) {
    var controles = document.querySelectorAll('[name="' + bloque.dataset.dependeDe + '"]');
    var valores = bloque.dataset.valores.split(",");
    function actualizar() {
      bloque.hidden = valores.indexOf(valorDe(controles)) === -1;
    }
    controles.forEach(function (c) {
      c.addEventListener("change", actualizar);
    });
    actualizar();
  });
})();
