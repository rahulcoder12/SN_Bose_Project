// --- BACKGROUND SERVICE WORKER ---
// This bypasses strict website CORS and CSP policies

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