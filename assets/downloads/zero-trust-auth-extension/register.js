document.addEventListener('DOMContentLoaded', () => {
    
    const formView = document.getElementById('register-form');
    const revealView = document.getElementById('password-reveal');
    
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const errorMsg = document.getElementById('error-msg');
    
    let finalPassword = "";

    // 1. Password Generator Function
    const generatePassword = () => {
        const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
        let pwd = "";
        for (let i = 0; i < 12; i++) {
            pwd += chars.charAt(Math.floor(Math.random() * chars.length));
        }
        return pwd;
    };

    // 2. Handle the "Register" Button Click (Now asynchronous!)
    document.getElementById('register-btn').addEventListener('click', async () => {
        const username = usernameInput.value.trim().toLowerCase();
        const customPassword = passwordInput.value.trim();
        
        // Reset Error Message
        errorMsg.style.display = "none";

        if (!username) {
            errorMsg.innerText = "⚠️ Username cannot be empty.";
            errorMsg.style.display = "block";
            return;
        }

        // Determine the password to send to the backend
        finalPassword = customPassword ? customPassword : generatePassword();

        // 3. API Database Validation Check
        try {
            document.getElementById('register-btn').innerText = "Verifying...";
            
            const response = await fetch('http://localhost:8000/api/v1/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    username: username, 
                    password: finalPassword 
                })
            });

            if (!response.ok) {
                // The database or request validator rejected the registration
                const errorData = await response.json();
                let message = "Registration failed.";

                if (typeof errorData.detail === "string") {
                    message = errorData.detail;
                } else if (Array.isArray(errorData.detail) && errorData.detail.length) {
                    message = errorData.detail
                        .map((item) => item.msg || "Invalid registration value")
                        .join(" ");
                }

                errorMsg.innerText = "⚠️ " + message;
                errorMsg.style.display = "block";
                document.getElementById('register-btn').innerText = "Register Account";
                return; // Stop the function here
            }

            // 4. Success! The backend saved the user.
            if (customPassword) {
                // If they typed their own password, jump straight to calibration
                saveAndProceed(username, finalPassword);
            } else {
                // Show the generated password reveal screen
                document.getElementById('generated-password').innerText = finalPassword;
                formView.style.display = "none";
                revealView.style.display = "block";
            }

        } catch (error) {
            errorMsg.innerText = "⚠️ Network error. Ensure the server is running.";
            errorMsg.style.display = "block";
            document.getElementById('register-btn').innerText = "Register Account";
        }
    });

    // 3. Handle the "Continue" Button Click 
    document.getElementById('continue-btn').addEventListener('click', () => {
        const username = usernameInput.value.trim().toLowerCase();
        saveAndProceed(username, finalPassword);
    });

    // 4. Save local session data and proceed
    function saveAndProceed(user, pass) {
        chrome.storage.local.set({ 
            registeredUsername: user,
            recoveryPassword: pass,
            passwordCreatedAt: Date.now()
        }, () => {
            window.location.href = "calibration.html";
        });
    }
});