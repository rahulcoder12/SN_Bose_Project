// Wait for the HTML to fully render before executing ANY JavaScript
document.addEventListener('DOMContentLoaded', () => {
    
    // 1. Initialize the tracker specifically for calibration
    const tracker = new BehaviorTracker("sk_live_51Mabcde12345");
    tracker.isCalibrationMode = true; 

    // 2. Mouse Target Logic
    let clickCount = 0;
    const maxClicks = 10;
    
    const targetBtn = document.getElementById('moving-target');
    const progressTxt = document.getElementById('click-progress');
    const completeBtn = document.getElementById('complete-btn');
    const typingInput = document.getElementById('typing-input');

    targetBtn.addEventListener('click', () => {
        clickCount++;
        progressTxt.innerText = `Targets hit: ${clickCount} / ${maxClicks}`;
        
        if (clickCount >= maxClicks) {
            targetBtn.style.display = 'none';
            progressTxt.innerText = "Mouse calibration complete!";
            progressTxt.style.color = "#00C851";
            checkCompletion();
        } else {
            // Move button randomly
            const areaWidth = document.getElementById('target-area').clientWidth - 80;
            const areaHeight = 160;
            const newLeft = Math.floor(Math.random() * areaWidth);
            const newTop = Math.floor(Math.random() * areaHeight);
            targetBtn.style.left = `${newLeft}px`;
            targetBtn.style.top = `${newTop}px`;
        }
    });

    typingInput.addEventListener('input', checkCompletion);

    function checkCompletion() {
        if (clickCount >= maxClicks && typingInput.value.length > 50) {
            completeBtn.disabled = false;
        }
    }

    completeBtn.addEventListener('click', async () => {
        completeBtn.innerText = "Profile Generating...";
        tracker.flush(); // Send final data chunks
        
        try {
            await fetch('http://localhost:8000/api/v1/calibrate/complete', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'x-api-key': tracker.apiKey 
                },
                body: JSON.stringify({ session_id: tracker.sessionId })
            });

            chrome.storage.local.set({ isCalibrated: true }, () => {
                alert("Calibration Complete! Your unique biometric baseline has been secured. The extension will now monitor your sessions.");
                window.close(); // Close the onboarding tab
            });

        } catch (error) {
            console.error("Failed to compile baseline:", error);
            completeBtn.innerText = "Error. Try Again.";
        }
    });
});