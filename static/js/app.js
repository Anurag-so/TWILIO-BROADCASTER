/* ==========================================================================
   🎮 INTERACTIVE FRONTEND CONTROLLER - APP.JS
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
    // 1. Initial State Load
    switchTab("dashboard");
    loadContacts();
    loadSettings();
    
    // Start Chat Log Real-time Polling (Every 2 seconds)
    setInterval(pollChatLogs, 2000);

    // 2. Add Tab Event Listeners
    document.querySelectorAll(".menu-item").forEach(item => {
        item.addEventListener("click", (e) => {
            e.preventDefault();
            const tabId = item.getAttribute("data-tab");
            switchTab(tabId);
        });
    });

    // 3. Contact Form Submission
    document.getElementById("add-contact-form").addEventListener("submit", handleAddContact);

    // 4. Broadcast Form Submission
    document.getElementById("broadcast-form").addEventListener("submit", handleLaunchBroadcast);

    // 5. Settings Form Submission
    document.getElementById("settings-form").addEventListener("submit", handleSaveSettings);

    // 6. Clear Logs Action
    document.getElementById("btn-clear-logs").addEventListener("click", handleClearLogs);
});

// ==========================================================================
// 🧭 TAB NAVIGATION CONTROLLER
// ==========================================================================

function switchTab(tabId) {
    // Select Active Menu Link
    document.querySelectorAll(".menu-item").forEach(item => {
        item.classList.remove("active");
        if (item.getAttribute("data-tab") === tabId) {
            item.classList.add("active");
        }
    });

    // Select Active Content Panel
    document.querySelectorAll(".tab-panel").forEach(panel => {
        panel.classList.remove("active");
    });
    const activePanel = document.getElementById(`tab-${tabId}`);
    if (activePanel) activePanel.classList.add("active");

    // Dynamic Title & Subtitles updates
    const title = document.getElementById("tab-title");
    const subtitle = document.getElementById("tab-subtitle");
    
    const meta = {
        dashboard: { title: "Overview Dashboard", subtitle: "All systems active. Real-time broadcast and contacts monitor." },
        contacts: { title: "Contacts Desk", subtitle: "Manage your subscriber directory, custom groupings, and tags." },
        broadcasting: { title: "Broadcasting Panel", subtitle: "Compose custom templates and instantly broadcast via Twilio or WhatsApp." },
        chat: { title: "Live AI Chat logs", subtitle: "Real-time monitor tracking your WhatsApp incoming texts & AI replies." },
        settings: { title: "System Configurations", subtitle: "Review and manage your Twilio, Green-API, and OpenRouter API credentials." }
    };

    if (meta[tabId]) {
        title.innerText = meta[tabId].title;
        subtitle.innerText = meta[tabId].subtitle;
    }
}

// ==========================================================================
// 📋 CONTACTS MANAGEMENT (GET / POST)
// ==========================================================================

async function loadContacts() {
    try {
        const response = await fetch("/api/contacts");
        const contacts = await response.json();
        
        // 1. Update stats counter
        document.getElementById("stat-total-contacts").innerText = contacts.length;

        // 2. Populate Full table
        const fullBody = document.getElementById("full-contacts-body");
        fullBody.innerHTML = "";
        
        // 3. Populate Quick Dashboard table (last 4 contacts)
        const quickBody = document.getElementById("quick-contacts-body");
        quickBody.innerHTML = "";

        if (contacts.length === 0) {
            const emptyRow = `<tr><td colspan="3" class="text-secondary text-center">No contacts in database.</td></tr>`;
            fullBody.innerHTML = emptyRow;
            quickBody.innerHTML = emptyRow;
            return;
        }

        contacts.forEach((p, idx) => {
            const tagsSpan = p.tags.map(t => `<span class="badge-tag">${t}</span>`).join("");
            const row = `
                <tr>
                    <td><strong>${p.name}</strong></td>
                    <td class="text-secondary">${p.phone}</td>
                    <td>${tagsSpan}</td>
                </tr>
            `;
            
            fullBody.insertAdjacentHTML("beforeend", row);
            if (idx < 4) {
                quickBody.insertAdjacentHTML("beforeend", row);
            }
        });

        // 4. Update Broadcast Tag Select choices
        updateTagSelect(contacts);

    } catch (e) {
        console.error("Failed to load contacts:", e);
    }
}

function updateTagSelect(contacts) {
    const select = document.getElementById("broadcast-tag");
    // Extract unique tags (corrected to use toLowerCase()!)
    const tagsSet = new Set();
    contacts.forEach(p => p.tags.forEach(t => tagsSet.add(t.trim().toLowerCase())));
    
    select.innerHTML = `<option value="">-- Choose Tag --</option>`;
    Array.from(tagsSet).sort().forEach(tag => {
        select.insertAdjacentHTML("beforeend", `<option value="${tag}">${tag.toUpperCase()}</option>`);
    });
}

async function handleAddContact(e) {
    e.preventDefault();
    const name = document.getElementById("contact-name").value.trim();
    const phone = document.getElementById("contact-phone").value.trim();
    const tagsInput = document.getElementById("contact-tags").value.trim();
    // Corrected to use toLowerCase()!
    const tags = tagsInput.split(",").map(t => t.trim().toLowerCase()).filter(t => t);

    if (!phone.startsWith("+")) {
        alert("Phone number must start with '+' and contain your country code!");
        return;
    }

    try {
        const response = await fetch("/api/contacts", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, phone, tags })
        });
        
        if (response.ok) {
            // Reset fields & Reload table
            document.getElementById("add-contact-form").reset();
            loadContacts();
        } else {
            alert("Failed to add contact.");
        }
    } catch (e) {
        console.error(e);
    }
}

// ==========================================================================
// 📣 BROADCAST INITIATOR (POST / PROGRESS)
// ==========================================================================

async function handleLaunchBroadcast(e) {
    e.preventDefault();
    const tag = document.getElementById("broadcast-tag").value;
    const method = document.querySelector('input[name="broadcast-method"]:checked').value;
    const message = document.getElementById("broadcast-message").value.trim();

    // Trigger visual progress indicator
    const progBox = document.getElementById("progress-box");
    const progBar = document.getElementById("progress-bar");
    const progStatus = document.getElementById("progress-status");
    const progPercent = document.getElementById("progress-percent");

    progBox.classList.remove("hidden");
    progBar.style.width = "0%";
    progPercent.innerText = "0%";
    progStatus.innerText = "Analyzing target queue...";

    // Mock progress animations before API finishes
    let progress = 10;
    const interval = setInterval(() => {
        if (progress < 85) {
            progress += Math.floor(Math.random() * 8) + 1;
            progBar.style.width = `${progress}%`;
            progPercent.innerText = `${progress}%`;
            progStatus.innerText = `Broadcasting messaging queue (${progress}% complete)...`;
        }
    }, 300);

    try {
        const response = await fetch("/api/broadcast", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tag, method, message })
        });

        clearInterval(interval);
        const data = await response.json();

        if (response.ok && data.success) {
            // Complete success animations
            progBar.style.width = "100%";
            progPercent.innerText = "100%";
            progStatus.innerText = `Broadcast complete! Successfully sent to ${data.sent_count} contact(s).`;
            
            // Reload stats sent count
            document.getElementById("stat-total-sent").innerText = data.sent_count;
            
            // Clear textarea inputs
            document.getElementById("broadcast-message").value = "";
        } else {
            progBar.style.width = "100%";
            progBar.style.backgroundColor = "red";
            progStatus.innerText = `Fail: ${data.message || 'Unknown network error'}`;
        }
    } catch (e) {
        clearInterval(interval);
        progBar.style.width = "100%";
        progBar.style.backgroundColor = "red";
        progStatus.innerText = "Error: Failed to reach local backend server.";
        console.error(e);
    }
}

// ==========================================================================
// 💬 REAL-TIME CHAT LOG MONITOR (POLLING)
// ==========================================================================

let lastLogCount = 0;

async function pollChatLogs() {
    try {
        const response = await fetch("/api/chat-logs");
        const logs = await response.json();

        // Only redraw if a new message was captured
        if (logs.length === lastLogCount) return;
        lastLogCount = logs.length;

        const chatBody = document.getElementById("chat-messages-body");
        chatBody.innerHTML = "";

        if (logs.length === 0) {
            chatBody.innerHTML = `
                <div class="chat-placeholder">
                    <i class="fa-solid fa-comments text-purple"></i>
                    <p>No real-time chats captured yet.</p>
                    <p class="text-xs text-secondary">Incoming messages from linked WhatsApp and Qwen3 responses will appear here instantly!</p>
                </div>
            `;
            return;
        }

        logs.forEach(log => {
            const row = `
                <div class="chat-bubble ${log.type}">
                    <span class="bubble-meta">${log.sender} • ${log.time}</span>
                    <span class="bubble-body">${escapeHTML(log.message)}</span>
                </div>
            `;
            chatBody.insertAdjacentHTML("beforeend", row);
        });

        // Auto-Scroll to the bottom of the chat window
        chatBody.scrollTop = chatBody.scrollHeight;

    } catch (e) {
        console.error("Failed to poll chat logs:", e);
    }
}

async function handleClearLogs() {
    if (!confirm("Are you sure you want to clear the AI Chat history logs?")) return;
    try {
        const response = await fetch("/api/chat-logs", { method: "DELETE" });
        if (response.ok) {
            lastLogCount = 0;
            pollChatLogs();
        }
    } catch (e) {
        console.error(e);
    }
}

function escapeHTML(str) {
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

// ==========================================================================
// ⚙️ SYSTEM SETTINGS CONTROLLER (GET / POST)
// ==========================================================================

async function loadSettings() {
    try {
        const response = await fetch("/api/settings");
        const data = await response.json();

        // Populate form fields
        document.getElementById("set-green-id").value = data.GREEN_API_ID_INSTANCE || "";
        document.getElementById("set-green-token").value = data.GREEN_API_TOKEN_INSTANCE || "";
        document.getElementById("set-twilio-sid").value = data.TWILIO_ACCOUNT_SID || "";
        document.getElementById("set-twilio-token").value = data.TWILIO_AUTH_TOKEN || "";
        document.getElementById("set-twilio-phone").value = data.TWILIO_PHONE_NUMBER || "";
        document.getElementById("set-openrouter-key").value = data.OPENROUTER_API_KEY || "";
        document.getElementById("set-openrouter-model").value = data.OPENROUTER_MODEL || "qwen/qwen3-32b";

        // Update status indicators
        updateStatusIndicator("green", data.GREEN_API_ID_INSTANCE && data.GREEN_API_TOKEN_INSTANCE);
        updateStatusIndicator("twilio", data.TWILIO_ACCOUNT_SID && data.TWILIO_AUTH_TOKEN && data.TWILIO_PHONE_NUMBER);
        updateStatusIndicator("openrouter", data.OPENROUTER_API_KEY);

        // Update Model name stat card
        document.getElementById("stat-ai-model").innerText = data.OPENROUTER_MODEL ? data.OPENROUTER_MODEL.split("/")[1] : "Qwen3";

    } catch (e) {
        console.error("Failed to load settings:", e);
    }
}

function updateStatusIndicator(serviceId, active) {
    const el = document.getElementById(`status-${serviceId}`);
    if (active) {
        el.className = "badge badge-green";
        el.innerText = "Linked";
    } else {
        el.className = "badge badge-outline";
        el.innerText = "Configure";
        el.style.borderColor = "rgba(255,255,255,0.1)";
        el.style.color = "var(--text-secondary)";
    }
}

async function handleSaveSettings(e) {
    e.preventDefault();
    
    const settings = {
        GREEN_API_ID_INSTANCE: document.getElementById("set-green-id").value.trim(),
        GREEN_API_TOKEN_INSTANCE: document.getElementById("set-green-token").value.trim(),
        TWILIO_ACCOUNT_SID: document.getElementById("set-twilio-sid").value.trim(),
        TWILIO_AUTH_TOKEN: document.getElementById("set-twilio-token").value.trim(),
        TWILIO_PHONE_NUMBER: document.getElementById("set-twilio-phone").value.trim(),
        OPENROUTER_API_KEY: document.getElementById("set-openrouter-key").value.trim(),
        OPENROUTER_MODEL: document.getElementById("set-openrouter-model").value.trim()
    };

    try {
        const response = await fetch("/api/settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(settings)
        });

        if (response.ok) {
            alert("💾 Settings saved successfully! Server is reloading settings.");
            loadSettings();
            switchTab("dashboard");
        } else {
            alert("❌ Failed to save credentials.");
        }
    } catch (e) {
        console.error(e);
    }
}