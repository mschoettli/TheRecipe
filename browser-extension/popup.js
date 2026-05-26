const appUrlInput = document.querySelector("#app-url");
const saveButton = document.querySelector("#save-button");
const statusText = document.querySelector("#status");

chrome.storage.sync.get({ appUrl: "http://localhost:8000" }, (items) => {
  appUrlInput.value = items.appUrl;
});

appUrlInput.addEventListener("change", () => {
  chrome.storage.sync.set({ appUrl: appUrlInput.value.replace(/\/$/, "") });
});

saveButton.addEventListener("click", async () => {
  statusText.textContent = "Saving...";
  saveButton.disabled = true;

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const appUrl = appUrlInput.value.replace(/\/$/, "");
    await chrome.storage.sync.set({ appUrl });

    const response = await fetch(`${appUrl}/imports/from-url`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: tab.url })
    });

    if (!response.ok) {
      throw new Error(`Import failed with HTTP ${response.status}`);
    }

    const result = await response.json();
    await chrome.tabs.create({ url: result.draft_url });
    statusText.textContent = "Draft opened.";
  } catch (error) {
    statusText.textContent = error.message;
  } finally {
    saveButton.disabled = false;
  }
});
