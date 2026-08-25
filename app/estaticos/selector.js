/* ===========================================================================
   selector.js - Lo poco que hace falta que ocurra sin recargar la pagina.

   Este es el UNICO JavaScript del proyecto, y hace solo dos cosas:

     1. Llevar la cuenta de las comidas cubiertas segun marcas y desmarcas.
     2. Esconder y ensenar tarjetas al usar los filtros.

   ---------------------------------------------------------------------------
   POR QUE NO CALCULA EL PRECIO
   ---------------------------------------------------------------------------
   Seria lo primero que uno pensaria en poner aqui, y esta a proposito fuera.

   El precio de verdad depende del COSTE MARGINAL: si dos recetas llevan
   cebolla, la segunda no paga cebolla. Para saber eso hay que conocer todos
   los envases de todas las recetas marcadas y ver cuales se comparten, y ese
   calculo vive en el servidor (cesta.py).

   Se podria ensenar aqui una suma aproximada, pero seria un numero que NO
   cuadraria con el de la pantalla siguiente. Y ese error exacto (dos cifras
   distintas para la misma cosa) ya nos costo un rediseno en la primera version
   de la app: cuando el usuario suma y no le sale, deja de fiarse de todos los
   demas numeros de la pagina.

   Asi que el precio se recalcula en el servidor con el boton "Actualizar", y
   aqui solo se ensena lo que se puede calcular EXACTO: las comidas, que son
   raciones dividido entre personas y no dependen de nada mas.
   =========================================================================== */

(function () {
  "use strict";

  var barra = document.getElementById("barra-seleccion");
  if (!barra) return;

  // dataset lee los atributos data-* del HTML. Vienen como texto, de ahi el
  // parseInt: sin el, "2" + 2 daria "22" en vez de 4.
  var personas = parseInt(barra.dataset.personas, 10) || 1;
  var necesarias = parseInt(barra.dataset.necesarias, 10) || 0;

  var contador = document.getElementById("contador-comidas");
  var avisoComidas = document.getElementById("aviso-comidas");
  var tarjetas = Array.prototype.slice.call(
    document.querySelectorAll(".tarjeta-elegir")
  );

  // --- 1. El contador de comidas -------------------------------------------

  function recalcularComidas() {
    var raciones = 0;

    tarjetas.forEach(function (tarjeta) {
      var casilla = tarjeta.querySelector(".casilla-receta");
      var selector = tarjeta.querySelector(".selector-veces");

      // La clase "elegida" es lo que colorea la tarjeta. Se actualiza aqui en
      // vez de con CSS :checked porque el input no es hermano de la tarjeta.
      tarjeta.classList.toggle("elegida", casilla.checked);

      if (!casilla.checked) return;
      var porCocinada = parseInt(casilla.dataset.raciones, 10) || 0;
      var veces = parseInt(selector.value, 10) || 1;
      raciones += porCocinada * veces;
    });

    // Division entera: 7 raciones para 2 personas dan 3 comidas, no 3,5.
    var comidas = Math.floor(raciones / personas);
    contador.textContent = comidas;

    if (comidas < necesarias) {
      avisoComidas.textContent = "faltan " + (necesarias - comidas);
      avisoComidas.className = "ayuda texto-error";
    } else if (comidas > necesarias) {
      avisoComidas.textContent = "sobran " + (comidas - necesarias);
      avisoComidas.className = "ayuda";
    } else {
      avisoComidas.textContent = "justo";
      avisoComidas.className = "ayuda texto-ok";
    }
  }

  // --- 2. Los filtros -------------------------------------------------------

  var filtroDificultad = document.getElementById("filtro-dificultad");
  var filtroTiempo = document.getElementById("filtro-tiempo");
  var filtroMarcadas = document.getElementById("filtro-marcadas");
  var cuentaVisibles = document.getElementById("cuenta-visibles");
  var sinResultados = document.getElementById("sin-resultados");

  function aplicarFiltros() {
    var dificultad = filtroDificultad.value;
    var tiempo = parseInt(filtroTiempo.value, 10) || 0;
    var soloMarcadas = filtroMarcadas.checked;
    var visibles = 0;

    tarjetas.forEach(function (tarjeta) {
      var casilla = tarjeta.querySelector(".casilla-receta");
      var minutos = parseInt(tarjeta.dataset.minutos, 10) || 0;

      var pasa =
        (!dificultad || tarjeta.dataset.dificultad === dificultad) &&
        (!tiempo || minutos <= tiempo) &&
        (!soloMarcadas || casilla.checked);

      // IMPORTANTE: se esconde con la clase "oculta" (display:none), no se
      // borra del documento. Un input escondido SIGUE enviandose al pulsar
      // el boton, asi que las recetas marcadas que estan filtradas no se
      // pierden. Si las borraramos del HTML, filtrar por "menos de 25 min"
      // te vaciaria media seleccion sin avisar.
      tarjeta.classList.toggle("oculta", !pasa);
      if (pasa) visibles++;
    });

    cuentaVisibles.textContent = visibles;
    sinResultados.hidden = visibles > 0;
  }

  // --- Conectar todo --------------------------------------------------------

  tarjetas.forEach(function (tarjeta) {
    tarjeta.querySelector(".casilla-receta").addEventListener("change", function () {
      recalcularComidas();
      if (filtroMarcadas.checked) aplicarFiltros();
    });
    tarjeta.querySelector(".selector-veces").addEventListener("change", recalcularComidas);
    // Sin esto, pulsar el desplegable de "cocinarla N veces" marcaria tambien
    // la casilla, porque todo esta dentro de una etiqueta <label>.
    tarjeta.querySelector(".selector-veces").addEventListener("click", function (evento) {
      evento.preventDefault();
      evento.stopPropagation();
    });
  });

  [filtroDificultad, filtroTiempo, filtroMarcadas].forEach(function (control) {
    control.addEventListener("change", aplicarFiltros);
  });
  // Los filtros estan dentro del formulario; sin esto, pulsar Enter en uno
  // enviaria el formulario entero.
  document.getElementById("formulario-seleccion").addEventListener("keydown", function (e) {
    if (e.key === "Enter" && e.target.tagName === "SELECT") e.preventDefault();
  });

  recalcularComidas();
})();
