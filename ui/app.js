window.setStatus = (message) => {
    const statusLabel = document.getElementById("status-label");
    const statusDot = document.querySelector(".status-dot");
    if (statusLabel) {
        statusLabel.textContent = message;
        
        // Dynamically style the status dot depending on the status message
        if (statusDot) {
            const lowerMsg = message.toLowerCase();
            if (lowerMsg.includes("selecting") || lowerMsg.includes("scan") || lowerMsg.includes("y:") || lowerMsg.includes("open")) {
                // Active/Processing state (Amber)
                statusDot.style.color = "#f59e0b";
                statusDot.style.backgroundColor = "#f59e0b";
            } else if (lowerMsg.includes("closed") || lowerMsg.includes("stop")) {
                // Idle state (Neutral/Gray)
                statusDot.style.color = "#9ca3af";
                statusDot.style.backgroundColor = "#9ca3af";
            } else {
                // Good / Active / Ready (Green)
                statusDot.style.color = "#10b981";
                statusDot.style.backgroundColor = "#10b981";
            }
        }
    }
};

window.addEventListener("pywebviewready", async () => {
    await refreshConfigs();
    await loadStartupConfig();
    bindSettingsSync();
    updateCastingMode();
});
function switchTab(tabId) {
    // Hide all tabs
    document.querySelectorAll(".tab-content")
        .forEach(tab => {
            tab.classList.remove("active");
        });
    // Remove active button state
    document.querySelectorAll(".tab-button")
        .forEach(button => {
            button.classList.remove("active");
        });
    // Show selected tab
    document.getElementById(tabId)
        .classList.add("active");
    // Highlight selected button
    event.target.classList.add("active");
}
async function startMacro() {

    // Save current UI settings first
    const configName =
        document.getElementById(
            "config-select"
        ).value;

    const settings = getSettings();

    await pywebview.api.save_config(
        configName,
        settings
    );

    // Sync runtime variables to Python
    await syncSettings();

    // Start macro
    let result =
        await pywebview.api.start_macro();

    console.log(result);
}
function updateCastingMode() {
    const castingMode =
        document.getElementById("casting_mode").value;
    const perfectCard =
        document.getElementById("perfect-cast-card");
    if (castingMode === "perfect") {
        perfectCard.style.display = "block";
    } else {
        perfectCard.style.display = "none";
    }
}
// =========================
// TAB SWITCHING
// =========================
function switchTab(tabId) {
    document.querySelectorAll(".tab-content").forEach(tab => {
        tab.classList.remove("active");
    });
    document.querySelectorAll(".tab-button").forEach(btn => {
        btn.classList.remove("active");
    });
    document.getElementById(tabId).classList.add("active");
    event.target.classList.add("active");
}
// =========================
// PERFECT CAST CARD
// =========================
function updateCastingMode() {
    const mode = document.getElementById("casting_mode").value;
    const perfectCard = document.getElementById("perfect-cast-card");
    if (mode === "perfect") {
        perfectCard.style.display = "block";
    } else {
        perfectCard.style.display = "none";
    }
}
// Save settings
function getSettings() {
    const settings = {};
    // Get all input elements
    document.querySelectorAll("input, select").forEach(element => {
        if (element.id) {
            if (element.type === "checkbox") {
                settings[element.id] = element.checked ? "on" : "off";
            } else {
                settings[element.id] = element.value;
            }
        }
    });
    return settings;
}
function applySettings(settings) {
    // Apply all settings to form elements
    document.querySelectorAll("input, select").forEach(element => {
        if (element.id && settings.hasOwnProperty(element.id)) {
            if (element.type === "checkbox") {
                element.checked =
                    settings[element.id] === true ||
                    settings[element.id] === "on";
            } else {
                setElementValue(element, settings[element.id]);
            }
        }
    });
    updateCastingMode();
}
function setElementValue(element, value) {
    if (element.tagName !== "SELECT") {
        element.value = value;
        return;
    }
    const match = Array.from(element.options)
        .find(option =>
            option.value.toLowerCase() === String(value).toLowerCase()
        );
    element.value = match ? match.value : value;
}
async function syncSettings() {
    await pywebview.api.update_settings(
        getSettings()
    );
}
function bindSettingsSync() {
    document.querySelectorAll("input, select").forEach(element => {
        if (element.id && element.id !== "config-select") {
            element.addEventListener("change", syncSettings);
            element.addEventListener("input", syncSettings);
        }
    });
    document.getElementById("config-select")
        .addEventListener("change", loadConfig);
}
async function saveConfig() {
    const configName =
        document.getElementById(
            "config-select"
        ).value;
    const settings = getSettings();
    const result =
        await pywebview.api.save_config(
            configName,
            settings
        );
    if (result.success) {
        alert("Config saved.");
    } else {
        alert(result.error);
    }
}
async function loadConfig() {
    const configName =
        document.getElementById(
            "config-select"
        ).value;
    const result =
        await pywebview.api.load_config(
            configName
        );
    if (result.success) {
        applySettings(
            result.settings
        );
        await syncSettings();
    } else {
        alert(result.error);
    }
}
async function loadStartupConfig() {
    const result =
        await pywebview.api.get_startup_config();
    if (result.success) {
        const select =
            document.getElementById(
                "config-select"
            );
        select.value = result.config_name;
        applySettings(
            result.settings
        );
        await syncSettings();
    } else {
        await syncSettings();
    }
}
async function refreshConfigs() {
    const configs =
        await pywebview.api.list_configs();
    const select =
        document.getElementById(
            "config-select"
        );
    select.innerHTML = "";
    configs.forEach(config => {
        const option =
            document.createElement("option");
        option.value = config;
        option.textContent = config;
        select.appendChild(option);
    });
}
async function newConfig() {
    const name =
        prompt("Config name:");
    if (!name) return;
    await pywebview.api.save_config(
        name,
        getSettings()
    );
    refreshConfigs();
    document.getElementById(
        "config-select"
    ).value = name;
}
async function deleteConfig() {
    const configName =
        document.getElementById(
            "config-select"
        ).value;
    if (!configName) return;
    await pywebview.api.delete_config(
        configName
    );
    refreshConfigs();
}
async function testLogging() {
    await pywebview.api.test_logging();
}