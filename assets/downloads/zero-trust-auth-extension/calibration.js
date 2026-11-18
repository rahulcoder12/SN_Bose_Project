// Wait for the HTML to fully render before executing ANY JavaScript
document.addEventListener('DOMContentLoaded', () => {
    
    // 1. Initialize the tracker specifically for calibration
    const tracker = new BehaviorTracker("sk_live_51Mabcde12345");
    tracker.isCalibrationMode = true; 

    // 2. Mouse Target Logic
    let clickCount = 0;
    const maxClicks = 10;
    
    const targetBtn = document.getElementById('moving-target');
    const clickProgressTxt = document.getElementById('click-progress');
    const completeBtn = document.getElementById('complete-btn');
    const typingInput = document.getElementById('typing-input');

    targetBtn.addEventListener('click', () => {
        clickCount++;
        clickProgressTxt.innerText = `Targets hit: ${clickCount} / ${maxClicks}`;
        
        if (clickCount >= maxClicks) {
            targetBtn.style.display = 'none';
            clickProgressTxt.innerText = "Target calibration complete!";
            clickProgressTxt.style.color = "#00C851";
            checkCompletion();
        } else {
            const areaWidth = document.getElementById('target-area').clientWidth - 80;
            const areaHeight = 160;
            const newLeft = Math.floor(Math.random() * areaWidth);
            const newTop = Math.floor(Math.random() * areaHeight);
            targetBtn.style.left = `${newLeft}px`;
            targetBtn.style.top = `${newTop}px`;
        }
    });

    // Task 3: Scroll Logic
    const scrollBox = document.getElementById('scroll-box');
    const acceptBtn = document.getElementById('accept-scroll');
    const scrollProgress = document.getElementById('scroll-progress');
    let scrollAccepted = false;

    scrollBox.addEventListener('scroll', () => {
        // Check if user scrolled near the bottom
        if (scrollBox.scrollTop + scrollBox.clientHeight >= scrollBox.scrollHeight - 10) {
            acceptBtn.disabled = false;
        }
    });

    acceptBtn.addEventListener('click', () => {
        scrollAccepted = true;
        acceptBtn.innerText = "Accepted";
        acceptBtn.disabled = true;
        acceptBtn.style.background = "#ccc";
        scrollProgress.style.display = "block";
        checkCompletion();
    });

    typingInput.addEventListener('input', checkCompletion);

    function checkCompletion() {
        if (clickCount >= maxClicks && typingInput.value.length > 50 && scrollAccepted) {
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

            // Save calibration session ID — monitoring sessions use this to load the right AI model
            chrome.storage.local.set({
                isCalibrated:         true,
                calibrationSessionId: tracker.sessionId
            }, () => {
                alert("Calibration Complete! Your unique biometric baseline has been secured. The extension will now monitor your sessions.");
                window.close(); // Close the onboarding tab
            });

        } catch (error) {
            console.error("Failed to compile baseline:", error);
            completeBtn.innerText = "Error. Try Again.";
        }
    });
});