'use strict';

let canvas, ctx, img;
let focusedCitations = [];
let currentPageNum = 1;
let resizeListenerAdded = false;

function syncCanvas() {
  canvas.width  = img.offsetWidth;
  canvas.height = img.offsetHeight;
  drawAll();
}

function drawAll() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  focusedCitations
    .filter(c => c.page === currentPageNum)
    .forEach(c => {
      const x = (c.x0 / 1000) * canvas.width;
      const y = (c.y0 / 1000) * canvas.height;
      const w = ((c.x1 - c.x0) / 1000) * canvas.width;
      const h = ((c.y1 - c.y0) / 1000) * canvas.height;

      ctx.fillStyle   = 'rgba(255, 200, 0, 0.4)';
      ctx.strokeStyle = '#e6a817';
      ctx.lineWidth   = 2;
      ctx.fillRect(x, y, w, h);
      ctx.strokeRect(x, y, w, h);
    });
}

function onImageLoad() {
  canvas = document.getElementById('bbox-canvas');
  ctx    = canvas.getContext('2d');
  img    = document.getElementById('page-image');

  const layout = document.querySelector('[data-page-num]');
  currentPageNum = layout ? parseInt(layout.dataset.pageNum, 10) : 1;

  syncCanvas();
  if (!resizeListenerAdded) {
    window.addEventListener('resize', syncCanvas);
    resizeListenerAdded = true;
  }
}

// Returns the page number currently displayed.
window.getCurrentPageNum = function () { return currentPageNum; };

// Show specific bboxes persistently and scroll to the first one on this page.
window.showCitations = function (bboxes) {
  focusedCitations = bboxes;
  if (canvas) syncCanvas();

  const onPage = bboxes.filter(c => c.page === currentPageNum);
  if (!onPage.length || !img) return;

  const panel = img.closest('.page-panel');
  if (panel) {
    const imgRect   = img.getBoundingClientRect();
    const panelRect = panel.getBoundingClientRect();
    const relTop    = imgRect.top - panelRect.top + panel.scrollTop;
    const bboxY     = (onPage[0].y0 / 1000) * img.offsetHeight;
    panel.scrollTo({ top: Math.max(0, relTop + bboxY - 80), behavior: 'smooth' });
  }
};
