// sidepanel.js — Full logic for RepoMind side panel

const API_BASE = 'http://localhost:8000';

// ── STATE ──────────────────────────────────────────────
let state = {
  repoContext: null,
  isIndexed: false,
  isLoading: false,
  messages: [],
  currentPatch: null,
};

// ── DOM REFS ───────────────────────────────────────────
const repoBadge    = document.getElementById('repoBadge');
const statusDot    = document.getElementById('statusDot');
const statusText   = document.getElementById('statusText');
const indexBtn     = document.getElementById('indexBtn');
const chatMessages = document.getElementById('chatMessages');
const chatEmpty    = document.getElementById('chatEmpty');
const chatInput    = document.getElementById('chatInput');
const sendBtn      = document.getElementById('sendBtn');
const explainTarget = document.getElementById('explainTarget');
const explainResult = document.getElementById('explainResult');
const issuesList   = document.getElementById('issuesList');
const patchContent = document.getElementById('patchContent');
const patchInput   = document.getElementById('patchInput');
const generatePatchBtn = document.getElementById('generatePatchBtn');
const pushPRBtn    = document.getElementById('pushPRBtn');

// ── TABS ───────────────────────────────────────────────
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('panel-' + tab.dataset.tab).classList.add('active');
  });
});

// ── CONTEXT FROM BACKGROUND ───────────────────────────
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === 'CONTEXT_UPDATED') applyContext(msg.data);
});

// Load context from storage on open
chrome.storage.session.get('repoContext', ({ repoContext }) => {
  if (repoContext) applyContext(repoContext);
});

function applyContext(ctx) {
  state.repoContext = ctx;
  if (ctx.fullName) {
    repoBadge.textContent = ctx.fullName;
    repoBadge.classList.add('active');
    indexBtn.disabled = false;
    setStatus('idle', `${ctx.fullName} detected`);

    // Update explain panel target
    if (ctx.isPR) {
      explainTarget.textContent = `PR #${ctx.prNumber} — ${ctx.fullName}`;
    } else if (ctx.isFile) {
      explainTarget.textContent = ctx.filePath || ctx.fullName;
    } else {
      explainTarget.textContent = ctx.fullName;
    }
  }
}

// ── STATUS ─────────────────────────────────────────────
function setStatus(type, text) {
  statusDot.className = 'status-dot ' + type;
  statusText.textContent = text;
}

// ── API HELPERS ────────────────────────────────────────
async function apiPost(endpoint, body) {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
  return res.json();
}

async function apiGet(endpoint) {
  const res = await fetch(`${API_BASE}${endpoint}`);
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

// ── INDEXING ───────────────────────────────────────────
indexBtn.addEventListener('click', async () => {
  if (!state.repoContext?.fullName) return;
  const [owner, repo] = state.repoContext.fullName.split('/');

  indexBtn.disabled = true;
  setStatus('loading', 'Indexing repo…');

  try {
    const data = await apiPost('/index', { owner, repo });
    state.isIndexed = true;
    setStatus('online', `Indexed — ${data.chunks ?? '?'} chunks`);
    showToast(`✅ Indexed ${data.chunks ?? ''} code chunks`, 'success');
  } catch (err) {
    setStatus('error', 'Index failed');
    showToast('❌ Failed to index: ' + err.message, 'error');
  } finally {
    indexBtn.disabled = false;
  }
});

// ── CHAT ───────────────────────────────────────────────
chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// Auto-resize textarea
chatInput.addEventListener('input', () => {
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(chatInput.scrollHeight, 100) + 'px';
});

sendBtn.addEventListener('click', sendMessage);

async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text || state.isLoading) return;
  if (!state.repoContext?.fullName) {
    showToast('⚠️ Navigate to a GitHub repo first', 'error');
    return;
  }

  // Hide empty state
  if (chatEmpty) chatEmpty.style.display = 'none';

  appendMessage('user', text);
  chatInput.value = '';
  chatInput.style.height = 'auto';

  state.isLoading = true;
  sendBtn.disabled = true;
  const typingEl = appendTyping();

  try {
    const data = await apiPost('/ask', {
      repo: state.repoContext.fullName,
      question: text,
    });
    typingEl.remove();
    appendMessage('assistant', data.answer, data.citations);
  } catch (err) {
    typingEl.remove();
    appendMessage('assistant', `⚠️ Error: ${err.message}`);
  } finally {
    state.isLoading = false;
    sendBtn.disabled = false;
  }
}

function appendMessage(role, text, citations = []) {
  const msg = document.createElement('div');
  msg.className = `message ${role}`;

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.innerHTML = formatMessage(text);

  if (citations.length > 0) {
    const citeDiv = document.createElement('div');
    citeDiv.className = 'citations';
    citations.forEach(c => {
      const tag = document.createElement('span');
      tag.className = 'citation-tag';
      tag.textContent = '📎 ' + c.split('/').pop();
      tag.title = c;
      citeDiv.appendChild(tag);
    });
    bubble.appendChild(citeDiv);
  }

  const time = document.createElement('span');
  time.className = 'msg-time';
  time.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  msg.appendChild(bubble);
  msg.appendChild(time);
  chatMessages.appendChild(msg);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return msg;
}

function appendTyping() {
  const msg = document.createElement('div');
  msg.className = 'message assistant';
  msg.innerHTML = `
    <div class="typing-indicator">
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
    </div>`;
  chatMessages.appendChild(msg);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return msg;
}

function formatMessage(text) {
  // Very basic markdown: code blocks, inline code, newlines
  return text
    .replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) =>
      `<pre><code>${escapeHtml(code.trim())}</code></pre>`)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>');
}

function escapeHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function fillInput(text) {
  chatInput.value = text;
  chatInput.focus();
  if (chatEmpty) chatEmpty.style.display = 'none';
}

// ── EXPLAIN ────────────────────────────────────────────
document.getElementById('explainFileBtn').addEventListener('click', async () => {
  if (!state.repoContext?.fullName) return showToast('⚠️ No repo detected', 'error');
  explainResult.innerHTML = loadingHTML('Analyzing file…');
  try {
    const data = await apiPost('/explain-file', {
      repo: state.repoContext.fullName,
      file_path: state.repoContext.filePath || '',
    });
    explainResult.innerHTML = resultHTML('File Explanation', data.explanation);
  } catch (e) {
    explainResult.innerHTML = errorHTML(e.message);
  }
});

document.getElementById('explainPRBtn').addEventListener('click', async () => {
  if (!state.repoContext?.isPR) return showToast('⚠️ Navigate to a PR page first', 'error');
  explainResult.innerHTML = loadingHTML('Reading PR diff…');
  try {
    const data = await apiPost('/explain-pr', {
      repo: state.repoContext.fullName,
      pr_number: parseInt(state.repoContext.prNumber),
    });
    explainResult.innerHTML = resultHTML('PR Explanation', data.explanation);
  } catch (e) {
    explainResult.innerHTML = errorHTML(e.message);
  }
});

// ── ISSUES ─────────────────────────────────────────────
document.getElementById('runLinterBtn').addEventListener('click', () => runScan('lint'));
document.getElementById('runSemgrepBtn').addEventListener('click', () => runScan('semgrep'));

async function runScan(type) {
  if (!state.repoContext?.fullName) return showToast('⚠️ No repo detected', 'error');
  issuesList.innerHTML = `<div class="loading-row"><div class="spinner"></div> Running ${type} scan…</div>`;

  try {
    const data = await apiPost('/detect-issues', {
      repo: state.repoContext.fullName,
      file_path: state.repoContext.filePath || '',
      scan_type: type,
    });
    renderIssues(data.issues || []);
  } catch (e) {
    issuesList.innerHTML = errorHTML(e.message);
  }
}

function renderIssues(issues) {
  if (issues.length === 0) {
    issuesList.innerHTML = `
      <div class="empty-state">
        <div class="big-icon">✅</div>
        <h3>No issues found</h3>
        <p>Clean scan — no problems detected.</p>
      </div>`;
    return;
  }

  issuesList.innerHTML = '';
  issues.forEach(issue => {
    const card = document.createElement('div');
    card.className = `issue-card ${issue.severity || 'info'}`;
    card.innerHTML = `
      <div class="issue-header">
        <span class="issue-severity ${issue.severity}">${issue.severity || 'info'}</span>
        <span class="issue-file">${issue.file || ''}${issue.line ? ':' + issue.line : ''}</span>
      </div>
      <div class="issue-msg">${escapeHtml(issue.message)}</div>
      ${issue.rule ? `<div class="issue-rule">${issue.rule}</div>` : ''}
      <button class="fix-btn" onclick="autoFix('${escapeHtml(JSON.stringify(issue))}')">✨ Auto-fix</button>
    `;
    issuesList.appendChild(card);
  });
}

function autoFix(issueJson) {
  const issue = JSON.parse(issueJson);
  // Switch to patch tab and pre-fill
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelector('[data-tab="patch"]').classList.add('active');
  document.getElementById('panel-patch').classList.add('active');
  patchInput.value = `Fix the ${issue.severity} issue: ${issue.message} in ${issue.file || 'the codebase'} (rule: ${issue.rule || 'N/A'})`;
}

// ── PATCH ──────────────────────────────────────────────
generatePatchBtn.addEventListener('click', async () => {
  const description = patchInput.value.trim();
  if (!description) return showToast('⚠️ Describe the change first', 'error');
  if (!state.repoContext?.fullName) return showToast('⚠️ No repo detected', 'error');

  patchContent.innerHTML = loadingHTML('Generating patch…');
  generatePatchBtn.disabled = true;
  pushPRBtn.style.display = 'none';

  try {
    const data = await apiPost('/generate-patch', {
      repo: state.repoContext.fullName,
      issue_description: description,
    });
    state.currentPatch = data.patch;
    renderPatch(data);
    pushPRBtn.style.display = 'block';
  } catch (e) {
    patchContent.innerHTML = errorHTML(e.message);
  } finally {
    generatePatchBtn.disabled = false;
  }
});

function renderPatch(data) {
  patchContent.innerHTML = '';

  if (data.files) {
    data.files.forEach(f => {
      const diffEl = document.createElement('div');
      diffEl.className = 'diff-view';
      diffEl.innerHTML = `
        <div class="diff-header">
          <span class="diff-filename">${f.filename}</span>
          <span style="font-size:10px; color:var(--muted)">+${f.additions} / -${f.deletions}</span>
        </div>
        <div class="diff-content">${renderDiff(f.patch)}</div>
      `;
      patchContent.appendChild(diffEl);
    });
  } else {
    patchContent.innerHTML = resultHTML('Generated Patch', data.patch || 'No patch generated');
  }
}

function renderDiff(diffText) {
  if (!diffText) return '<span class="diff-line-ctx">No diff available</span>';
  return diffText.split('\n').map(line => {
    if (line.startsWith('+') && !line.startsWith('+++'))
      return `<span class="diff-line-add">${escapeHtml(line)}</span>`;
    if (line.startsWith('-') && !line.startsWith('---'))
      return `<span class="diff-line-del">${escapeHtml(line)}</span>`;
    return `<span class="diff-line-ctx">${escapeHtml(line)}</span>`;
  }).join('');
}

pushPRBtn.addEventListener('click', async () => {
  if (!state.currentPatch) return;
  const title = patchInput.value.trim().slice(0, 72) || 'AI-generated fix';

  pushPRBtn.disabled = true;
  pushPRBtn.textContent = '⏳ Pushing PR…';

  try {
    const data = await apiPost('/push-pr', {
      repo: state.repoContext.fullName,
      patch: state.currentPatch,
      title,
    });
    showToast('🎉 PR created!', 'success');
    if (data.pr_url) {
      const link = document.createElement('a');
      link.href = data.pr_url;
      link.target = '_blank';
      link.style.cssText = 'display:block; text-align:center; padding:8px; color:var(--accent); font-size:12px; margin-top:8px;';
      link.textContent = '🔗 View PR on GitHub →';
      patchContent.appendChild(link);
    }
  } catch (e) {
    showToast('❌ Push failed: ' + e.message, 'error');
  } finally {
    pushPRBtn.disabled = false;
    pushPRBtn.textContent = '🚀 Push as PR';
  }
});

// ── HELPERS ────────────────────────────────────────────
function loadingHTML(msg) {
  return `<div class="loading-row"><div class="spinner"></div> ${msg}</div>`;
}

function resultHTML(title, content) {
  return `
    <div class="result-box">
      <h4>${title}</h4>
      <div>${formatMessage(content)}</div>
    </div>`;
}

function errorHTML(msg) {
  return `
    <div class="result-box" style="border-color:var(--danger)">
      <h4 style="color:var(--danger)">Error</h4>
      <div>${escapeHtml(msg)}</div>
    </div>`;
}

let toastTimer;
function showToast(msg, type = '') {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.className = `toast show ${type}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 3000);
}
