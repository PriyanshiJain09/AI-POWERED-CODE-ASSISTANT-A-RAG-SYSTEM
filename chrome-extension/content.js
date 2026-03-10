// content.js - Injected into every GitHub page

const extractRepoContext = () => {
  const path = window.location.pathname.split('/').filter(Boolean);
  const url = window.location.href;

  const context = {
    owner: path[0] || null,
    repo: path[1] || null,
    fullName: path[0] && path[1] ? `${path[0]}/${path[1]}` : null,
    isPR: path[2] === 'pull',
    isFile: path[2] === 'blob',
    isTree: path[2] === 'tree',
    prNumber: path[2] === 'pull' ? path[3] : null,
    filePath: path[2] === 'blob' ? path.slice(4).join('/') : null,
    branch: path[2] === 'blob' || path[2] === 'tree' ? path[3] : null,
    url,
    pageTitle: document.title
  };

  return context;
};

// Send context on load
const sendContext = () => {
  const context = extractRepoContext();
  if (context.owner && context.repo) {
    chrome.runtime.sendMessage({ type: 'REPO_CONTEXT', data: context });
  }
};

sendContext();

// Re-send on GitHub's SPA navigation
let lastUrl = location.href;
const observer = new MutationObserver(() => {
  if (location.href !== lastUrl) {
    lastUrl = location.href;
    setTimeout(sendContext, 500); // wait for DOM to settle
  }
});
observer.observe(document.body, { childList: true, subtree: true });
