/* Conferma prima di unire.
 *
 * Il testo arriva da un attributo e non da un onclick in linea: contiene un
 * apostrofo ("L'operazione"), che dentro il JavaScript scritto nell'attributo
 * chiudeva la stringa e rendeva il gestore non compilabile. Risultato: la
 * domanda non compariva mai e l'unione partiva al primo tocco.
 */
(function () {
    "use strict";
    document.addEventListener("click", function (event) {
        var target = event.target;
        if (!target || !target.dataset || !target.dataset.mergeConfirm) { return; }
        if (!window.confirm(target.dataset.mergeConfirm)) {
            event.preventDefault();
            event.stopPropagation();
        }
    }, true);
})();
