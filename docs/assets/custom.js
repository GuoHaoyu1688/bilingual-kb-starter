
(function () {
  function bindFilter(id, selector) {
    const input = document.getElementById(id);
    if (!input || input.dataset.bound) return;
    input.dataset.bound = "true";
    input.addEventListener("input", function () {
      const needle = input.value.toLocaleLowerCase();
      document.querySelectorAll(selector).forEach(function (entry) {
        entry.hidden = !entry.textContent.toLocaleLowerCase().includes(needle);
      });
    });
  }
  function initialize() {
    bindFilter("glossary-filter", ".glossary-entry");
    bindFilter("timeline-filter", ".timeline-entry");
  }
  if (typeof document$ !== "undefined") document$.subscribe(initialize);
  document.addEventListener("DOMContentLoaded", initialize);
  initialize();
}());
