// background.js - Service worker for Chrome Extension

chrome.action.onClicked.addListener((tab) => {
  chrome.sidePanel.open({ tabId: tab.id });
});

// Open side panel automatically on GitHub pages
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url?.includes('github.com')) {
    chrome.sidePanel.setOptions({
      tabId,
      path: 'sidepanel.html',
      enabled: true
    });
  }
});

// Listen for messages from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'REPO_CONTEXT') {
    // Store context and forward to sidepanel
    chrome.storage.session.set({ repoContext: message.data });
    // Broadcast to sidepanel
    chrome.runtime.sendMessage({ type: 'CONTEXT_UPDATED', data: message.data })
      .catch(() => {}); // sidepanel may not be open yet
  }
  sendResponse({ ok: true });
});
