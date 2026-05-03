'use strict';

const _layout = document.querySelector('[data-doc-id]');
const DOC_ID = _layout ? _layout.dataset.docId : null;

const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatMessages = document.getElementById('chat-messages');

const history = [];  // [{role: "user|ai", content: "..."}]

if (!chatForm || !DOC_ID) {
  throw new Error('chat.js loaded outside document viewer');
}

// Parse a citations string like "1-3, 5, 17" into a flat array of ints.
function parseIds(str) {
  const ids = [];
  for (const part of str.split(',')) {
    const t = part.trim();
    if (t.includes('-')) {
      const [a, b] = t.split('-', 2);
      for (let i = parseInt(a, 10); i <= parseInt(b, 10); i++) ids.push(i);
    } else {
      const n = parseInt(t, 10);
      if (!isNaN(n)) ids.push(n);
    }
  }
  return ids;
}

// Show bboxes for a clicked citation badge, switching page if needed.
function jumpTo(bboxes) {
  const currentPage = window.getCurrentPageNum ? window.getCurrentPageNum() : 1;
  const onPage = bboxes.filter(c => c.page === currentPage);

  if (onPage.length > 0) {
    window.showCitations && window.showCitations(bboxes);
  } else if (bboxes.length > 0) {
    const target = bboxes[0];
    if (window.switchPage) {
      window.switchPage(target.page).then(() => {
        window.showCitations && window.showCitations(bboxes);
      });
    }
  }
}

// Render an AI answer into a DOM node.
// <citations>…</citations> tags become clickable superscript badges.
function renderAnswer(text, citationsById) {
  const container = document.createElement('div');
  const parts = text.split(/(<citations>[\s\S]*?<\/citations>)/g);
  let n = 0;

  parts.forEach(part => {
    const m = part.match(/^<citations>([\s\S]*?)<\/citations>$/);
    if (m) {
      const ids = parseIds(m[1]);
      ids.forEach(id => {
        n++;
        const citation = citationsById.get(id);

        const sup = document.createElement('sup');
        sup.className = 'chat-citation-badge';
        sup.textContent = n;
        sup.title = citation ? `Paragraph ${id} (page ${citation.page})` : `Paragraph ${id}`;

        if (citation) {
          sup.addEventListener('click', () => jumpTo([citation]));
        }

        container.appendChild(sup);
      });
    } else if (part) {
      container.appendChild(document.createTextNode(part));
    }
  });

  return container;
}

function appendBubble(content, role) {
  const empty = chatMessages.querySelector('.empty-state');
  if (empty) empty.remove();

  const bubble = document.createElement('div');
  bubble.className = `chat-bubble chat-bubble-${role}`;

  if (typeof content === 'string') {
    bubble.textContent = content;
  } else {
    bubble.appendChild(content);
  }

  chatMessages.appendChild(bubble);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return bubble;
}

async function sendQuestion(question) {
  appendBubble(question, 'user');
  const loadingBubble = appendBubble('Thinking…', 'loading');

  try {
    const resp = await fetch(`/documents/${DOC_ID}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, history }),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(err.detail || resp.statusText);
    }

    const data = await resp.json();
    loadingBubble.remove();

    // Update the conversation history
    history.push({ role: "user", content: question });
    history.push({ role: "ai", content: data.answer });

    // Build a lookup map: paragraph_id → CitationOut
    const citationsById = new Map(data.citations.map(c => [c.paragraph_id, c]));

    appendBubble(renderAnswer(data.answer, citationsById), 'ai');
  } catch (err) {
    loadingBubble.className = 'chat-bubble chat-bubble-ai';
    loadingBubble.textContent = `Error: ${err.message}`;
  }
}

chatForm.addEventListener('submit', e => {
  e.preventDefault();
  const q = chatInput.value.trim();
  if (!q) return;
  chatInput.value = '';
  sendQuestion(q);
});

chatInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    chatForm.dispatchEvent(new Event('submit'));
  }
});
