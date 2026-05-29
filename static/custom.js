// Rename the POTATO "Codebook" button to "IAB Taxonomy"
document.addEventListener('DOMContentLoaded', function () {
  var btn = document.querySelector('.codebook-btn');
  if (!btn) return;
  btn.childNodes.forEach(function (node) {
    if (node.nodeType === Node.TEXT_NODE) {
      node.textContent = ' IAB Taxonomy';
    }
  });
  btn.title = 'Open IAB Ad Product Taxonomy';
});
