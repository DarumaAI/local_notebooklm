'use strict';

const _navLayout = document.querySelector('[data-doc-id]');
const NAV_DOC_ID = _navLayout ? _navLayout.dataset.docId : null;

if (!NAV_DOC_ID) {
  throw new Error('nav.js loaded outside document viewer');
}

function updatePageNav(pageNum, totalPages) {
  const nav = document.querySelector('.page-nav');
  if (!nav) return;
  nav.innerHTML = '';

  if (pageNum > 1) {
    const a = document.createElement('a');
    a.href = `/documents/${NAV_DOC_ID}/view?page_num=${pageNum - 1}`;
    a.className = 'btn-secondary';
    a.textContent = '← Prev';
    nav.appendChild(a);
  }

  const span = document.createElement('span');
  span.textContent = `Page ${pageNum} / ${totalPages || '?'}`;
  nav.appendChild(span);

  if (totalPages && pageNum < totalPages) {
    const a = document.createElement('a');
    a.href = `/documents/${NAV_DOC_ID}/view?page_num=${pageNum + 1}`;
    a.className = 'btn-secondary';
    a.textContent = 'Next →';
    nav.appendChild(a);
  }
}

async function switchPage(pageNum) {
  const resp = await fetch(`/documents/${NAV_DOC_ID}/page-data?page_num=${pageNum}`);
  if (!resp.ok) return;
  const data = await resp.json();

  // Update elements-data before src change so onImageLoad reads the new data.
  const dataEl = document.getElementById('elements-data');
  if (dataEl) dataEl.textContent = JSON.stringify(data.elements);

  // Update data-page-num so bbox.js reads the right page on re-init.
  const layout = document.querySelector('[data-page-num]');
  if (layout) layout.dataset.pageNum = data.page_num;

  // Swap image src and wait for it to load so callers see updated page state.
  const img = document.getElementById('page-image');
  if (img && data.image_url) {
    await new Promise(resolve => {
      img.addEventListener('load', resolve, { once: true });
      img.src = data.image_url;
    });
  }

  // Keep URL in sync.
  history.pushState({ pageNum: data.page_num }, '', `/documents/${NAV_DOC_ID}/view?page_num=${data.page_num}`);

  // Update active thumbnail.
  document.querySelectorAll('.thumb-link').forEach(a => {
    const url = new URL(a.href, window.location.origin);
    a.classList.toggle('active', parseInt(url.searchParams.get('page_num'), 10) === data.page_num);
  });

  updatePageNav(data.page_num, data.total_pages);
}

// Intercept thumbnail and Prev/Next clicks — prevents full reloads.
document.addEventListener('click', e => {
  const link = e.target.closest('.thumb-link, .page-nav a');
  if (!link) return;

  const url = new URL(link.href, window.location.origin);
  const pageNum = parseInt(url.searchParams.get('page_num'), 10);
  if (isNaN(pageNum)) return;

  e.preventDefault();
  switchPage(pageNum);
});

// Handle browser back/forward.
window.addEventListener('popstate', e => {
  if (e.state && e.state.pageNum) switchPage(e.state.pageNum);
});

window.switchPage = switchPage;
