// --- EXTENSION ONBOARDING HOOK ---
chrome.runtime.onInstalled.addListener((details) => {
    // NEW: Trigger on both 'install' and 'update' while we are building this!
    if (details.reason === "install" || details.reason === "update") {
        console.log("📦 Extension Installed or Updated. Initializing Registration...");
        
        // Lock the tracker by default
        chrome.storage.local.set({ isCalibrated: false });
        
        // Phase 1 of Onboarding: Open Registration Page
        chrome.tabs.create({ url: chrome.runtime.getURL("register.html") });
    }
});

// --- DASHBOARD SHORTCUT (ICON CLICK) ---
// --- DASHBOARD SHORTCUT (ICON CLICK) ---
chrome.action.onClicked.addListener((tab) => {
    console.log("🖱️ Extension Icon Clicked. Opening Dashboard...");
    // Point to the new Web App Login Page
    chrome.tabs.create({ url: "http://localhost:8000/login.html" }); 
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    
    if (message.action === "FLUSH_TELEMETRY") {
        console.log("📡 Background Worker sending telemetry for session:", message.payload.session_id);

        fetch('http://localhost:8000/api/v1/ingest', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'x-api-key': message.apiKey 
            },
            body: JSON.stringify(message.payload)
        })
        .then(response => response.json())
        .then(data => {
            // Send the server's verdict back to the webpage
            sendResponse({ status: "success", data: data });
        })
        .catch(error => {
            console.error("Background fetch failed:", error);
            sendResponse({ status: "error", error: error.message });
        });

        // Return true to indicate we will send a response asynchronously
        return true; 
    }
});