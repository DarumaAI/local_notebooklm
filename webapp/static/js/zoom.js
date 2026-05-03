'use strict';

const ZOOM_STEP = 0.25;
const ZOOM_MIN  = 0.5;
const ZOOM_MAX  = 4.0;

let zoomLevel = 1.0;
let baseWidth  = null; // img.offsetWidth at zoom=1 (CSS-controlled fit)

function _applyZoom() {
  const img = document.getElementById('page-image');
  if (!img) return;

  if (zoomLevel === 1.0) {
    img.style.width    = '';
    img.style.maxWidth  = '';
    img.style.maxHeight = '';
    baseWidth = null;
  } else {
    if (baseWidth === null) baseWidth = img.offsetWidth;
    img.style.maxWidth  = 'none';
    img.style.maxHeight = 'none';
    img.style.width     = (baseWidth * zoomLevel) + 'px';
  }

  requestAnimationFrame(() => {
    if (typeof syncCanvas === 'function') syncCanvas();
    const el = document.getElementById('zoom-level');
    if (el) el.textContent = Math.round(zoomLevel * 100) + '%';
  });
}

window.zoomIn = function () {
  zoomLevel = Math.min(ZOOM_MAX, +(zoomLevel + ZOOM_STEP).toFixed(2));
  _applyZoom();
};

window.zoomOut = function () {
  zoomLevel = Math.max(ZOOM_MIN, +(zoomLevel - ZOOM_STEP).toFixed(2));
  _applyZoom();
};

window.zoomReset = function () {
  zoomLevel = 1.0;
  _applyZoom();
};

document.addEventListener('DOMContentLoaded', () => {
  const panel = document.querySelector('.page-panel');
  if (!panel) return;

  // Ctrl/Cmd + scroll wheel
  panel.addEventListener('wheel', (e) => {
    if (!e.ctrlKey && !e.metaKey) return;
    e.preventDefault();
    if (e.deltaY < 0) window.zoomIn(); else window.zoomOut();
  }, { passive: false });

  // Keyboard: Ctrl/Cmd +/- and 0
  document.addEventListener('keydown', (e) => {
    if (!e.ctrlKey && !e.metaKey) return;
    if (e.key === '=' || e.key === '+') { e.preventDefault(); window.zoomIn(); }
    else if (e.key === '-')             { e.preventDefault(); window.zoomOut(); }
    else if (e.key === '0')             { e.preventDefault(); window.zoomReset(); }
  });
});
