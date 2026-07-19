const APP_VERSION = "4.42";
const BETA_VERSION = "0";
const DEVELOPER = "Catman2608";
let currentConfig = null;
const validHexColor = /^#([0-9A-F]{3}|[0-9A-F]{6})$/i;

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
    updateAccentColor();
    bindColorPreviewInputs();
    updateColorPreviews();
});

// Top Bar
function updateTopbarInfo() {
    const configSelect = document.getElementById("disabled");
    const macroModeSelect = document.getElementById("automation_mode");
    
    const configNameEl = document.getElementById("topbar-config-name");
    const macroModeEl = document.getElementById("topbar-macro-mode");
    
    if (configNameEl && configSelect) {
        configNameEl.textContent = configSelect.value || "Default";
    }
    if (macroModeEl && macroModeSelect) {
        const val = macroModeSelect.value;
        macroModeEl.textContent = val ? val.charAt(0).toUpperCase() + val.slice(1) : "None";
    }
}

async function toggleMacroFromTopbar() {
    const btn = document.getElementById("topbar-start-btn");
    if (btn) {
        if (btn.classList.contains("start")) {
            btn.className = "topbar-btn stop";
            btn.innerHTML = `<span class="btn-icon">■</span> Stop Macro`;
            await startMacro();
        } else {
            btn.className = "topbar-btn start";
            btn.innerHTML = `<span class="btn-icon">▶</span> Start Macro`;
            await pywebview.api.stop_macro();
        }
    }
}

// Tab Switcher
function switchTab(tabId) {
    document.querySelectorAll(".tab-content").forEach(tab => {
        tab.classList.remove("active");
    });
    document.querySelectorAll(".tab-button").forEach(btn => {
        btn.classList.remove("active");
    });
    document.getElementById(tabId).classList.add("active");
    event.target.classList.add("active");

    // Update breadcrumb
    const breadcrumbTitle = document.getElementById("active-tab-title");
    if (breadcrumbTitle) {
        const titleMap = {
            basic: "Basic",
            automation: "Automation",
            utilities: "Utilities"
        };
        breadcrumbTitle.textContent = titleMap[tabId] || "Settings";
    }
}

function updateCastingMode() {
    const mode = document.getElementById("casting_mode").value;
    const perfectCard = document.getElementById("perfect-cast-card");
    if (mode === "perfect") {
        perfectCard.style.display = "block";
    } else {
        perfectCard.style.display = "none";
    }
}

function getSettings() {
    const settings = {};
    // Get all input elements
    document.querySelectorAll("input, select").forEach(element => {
        if (!element.id || element.id === "disabled") return;
        if (element.type === "checkbox") {
            settings[element.id] = element.checked ? "on" : "off";
        } else {
            settings[element.id] = element.value;
        }
    });
    return settings;
}
function applySettings(settings) {
    // Apply all settings to form elements
    document.querySelectorAll("input, select").forEach(element => {
        if (!element.id || element.id === "disabled") return;
        if (settings.hasOwnProperty(element.id)) {
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
    updateAccentColor();
    updateColorPreviews();
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
    updateTopbarInfo();
}
function bindSettingsSync() {
    document.querySelectorAll("input, select").forEach(element => {
        if (!element.id) return;
        // Skip config dropdown
        if (element.id === "disabled") return;
        element.addEventListener("change", syncSettings);
        element.addEventListener("input", syncSettings);
        // Add theme update listeners for color inputs
        if (element.id === "left_color" || element.id === "right_color" || element.id === "arrow_color") {
            element.addEventListener("change", updateAccentColor);
            element.addEventListener("input", updateAccentColor);
        }
    });
    bindColorPreviewInputs();
}
async function switchConfig(newConfigName) {
    try {
        if (!newConfigName) return;
        // Prevent duplicate reload
        if (newConfigName === currentConfig) {
            return;
        }
        // Auto-save current config
        if (currentConfig) {
            await saveConfig(currentConfig);
        }
        // Load new config
        await loadConfig(newConfigName);
    } catch (err) {
        console.error(err);
        setStatus("Failed to switch config");
    }
}
async function saveConfig(configName = null) {
    if (!configName) {
        configName =
            document.getElementById(
                "disabled"
            ).value;
    }
    if (!configName) {
        setStatus("No config selected");
        return;
    }
    const settings = getSettings();
    const result =
        await pywebview.api.save_config(
            configName,
            settings
        );
    if (result.success) {
        window.setStatus(`Saved: ${configName}`);
    } else {
        window.setStatus(`Error: "${result.error}"`);
    }
}
async function loadConfig(configName = null) {
    if (!configName) {
        configName =
            document.getElementById(
                "disabled"
            ).value;
    }
    if (!configName) {
        setStatus("No config selected");
        return;
    }
    const result =
        await pywebview.api.load_config(
            configName
        );
    if (result.success) {
        applySettings(
            result.settings
        );
        await syncSettings();
        currentConfig = configName;
        // Sync dropdown UI
        document.getElementById(
            "disabled"
        ).value = configName;
        setStatus(`Loaded: ${configName}`);
    } else {
        window.setStatus(
            `Error: "${result.error}"`
        );
    }
}
async function loadStartupConfig() {
    const result =
        await pywebview.api.get_startup_config();
    if (result.success) {
        const select =
            document.getElementById(
                "disabled"
            );
        currentConfig = result.config_name;
        applySettings(
            result.settings
        );
        if (select) {
            select.value = currentConfig;
        }
        await syncSettings();
        setStatus(`Loaded: ${currentConfig}`);
    } else {
        await syncSettings();
    }
}
async function refreshConfigs() {
    const configs =
        await pywebview.api.list_configs();
    const select =
        document.getElementById(
            "disabled"
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
    await refreshConfigs();
    document.getElementById(
        "disabled"
    ).value = name;
    currentConfig = name;
    setStatus(`Created: ${name}`);
}
async function deleteConfig() {
    const configName =
        document.getElementById(
            "disabled"
        ).value;
    if (!configName) return;
    const confirmed =
        confirm(
            `Delete "${configName}"?\n\nThis cannot be undone.`
        );
    if (!confirmed) return;
    const result =
        await pywebview.api.delete_config(
            configName
        );
    if (result.success) {
        await refreshConfigs();
        const select =
            document.getElementById(
                "disabled"
            );
        if (select.options.length > 0) {
            select.selectedIndex = 0;
            await loadConfig(
                select.value
            );
        }
        setStatus(
            `Deleted: ${configName}`
        );
    } else {
        setStatus(
            `Delete failed`
        );
    }
}
async function resetSettings() {
    const configName =
        document.getElementById(
            "disabled"
        ).value;
    if (!configName) return;
    const confirmed =
        confirm(
            `Reset ALL settings for "${configName}"?\n\nColors will be preserved.`
        );
    if (!confirmed) return;
    const result =
        await pywebview.api.reset_settings(
            configName
        );
    if (result.success) {
        await loadConfig(configName);
        setStatus(
            `Settings reset`
        );
    } else {
        setStatus(
            `Reset failed`
        );
    }
}
async function resetColors() {
    const configName =
        document.getElementById(
            "disabled"
        ).value;
    if (!configName) return;
    const confirmed =
        confirm(
            `Reset colors for "${configName}"?`
        );
    if (!confirmed) return;
    const result =
        await pywebview.api.reset_colors(
            configName
        );
    if (result.success) {
        await loadConfig(configName);
        setStatus(
            `Colors reset`
        );
    } else {
        setStatus(
            `Reset failed`
        );
    }
}
async function resetAreas() {
    const configName =
        document.getElementById(
            "disabled"
        ).value;

    if (!configName) return;

    const confirmed =
        confirm(
            `Reset areas for "${configName}"?`
        );

    if (!confirmed) return;

    const result =
        await pywebview.api.reset_areas();

    if (result.success) {
        await loadConfig(configName);
        setStatus("Bar areas reset to default");
    } else {
        setStatus("Bar areas failed to reset; delete last_config.json.");
    }
}
async function exportConfig() {
    try {
        const settings = getSettings();

        const result = await pywebview.api.export_config(
            settings
        );

        if (result.success) {
            setStatus(`Exported: ${result.path}`);
        } else {
            setStatus(`Export failed: ${result.error}`);
        }
    } catch (err) {
        console.error(err);
        setStatus("Export failed");
    }
}

async function importConfig() {
    try {
        const input = document.createElement("input");
        input.type = "file";
        input.accept = ".json,application/json";

        input.onchange = async (event) => {
            const file = event.target.files?.[0];
            if (!file) return;

            try {
                const text = await file.text();
                const settings = JSON.parse(text);

                applySettings(settings);
                await syncSettings();
                await saveConfig();

                setStatus(`Imported: ${file.name}`);
            } catch (err) {
                console.error(err);
                setStatus("Invalid config file");
            }
        };

        input.click();
    } catch (err) {
        console.error(err);
        setStatus("Import failed");
    }
}

async function openConfigsFolder() {
    await pywebview.api.open_base_folder();
}
async function testLogging() {
    await pywebview.api.test_logging();
}
async function startEyedropper() {
    await pywebview.api.start_eyedropper();
}
async function takeScreenshot() {
    setStatus("Error saving debug screenshots");
    await pywebview.api.take_debug_screenshot();
}
async function openLink(link) {
    if (!link) {
        setStatus(
            `No link provided`
        );
        return;
    }
    const result = await pywebview.api.open_link(link);
    if (!result || result.success) {
        setStatus(
            `Opened link`
        );
    } else {
        setStatus(
            `Could not open link`
        );
    }
}
function openAboutTab() {
    document
        .getElementById(
            "about-modal-overlay"
        )
        .classList.add("active");
}
function closeAboutTab() {
    document
        .getElementById(
            "about-modal-overlay"
        )
        .classList.remove("active");
}
function openSupportTab() {
    document
        .getElementById(
            "support-modal-overlay"
        )
        .classList.add("active");
}
function closeSupportTab() {
    document
        .getElementById(
            "support-modal-overlay"
        )
        .classList.remove("active");
}
function openConfigManager() {
    document
        .getElementById(
            "config-modal-overlay"
        )
        .classList.add("active");
}
function closeConfigManager() {
    document
        .getElementById(
            "config-modal-overlay"
        )
        .classList.remove("active");
}
document.addEventListener("click", (e) => {
    const overlay =
        document.getElementById(
            "config-modal-overlay"
        );
    if (e.target === overlay) {
        closeConfigManager();
    }
});

function normalizeHexColor(hex) {
    hex = String(hex || "").trim();
    if (!validHexColor.test(hex)) {
        return "";
    }
    if (hex.length === 4) {
        hex = "#" + hex
            .slice(1)
            .split("")
            .map(char => char + char)
            .join("");
    }
    return hex;
}

function updateColorPreview(input) {
    const value = normalizeHexColor(input.value);
    if (value) {
        input.style.border = `2px solid ${value}`;
        input.style.boxShadow = `0 0 10px ${value}88`;
    } else {
        input.style.border = "2px solid rgba(255,255,255,0.08)";
        input.style.boxShadow = "none";
    }
}

function getColorPreviewInputs() {
    return document.querySelectorAll(
        '.simple-box input[type="text"][id$="_color"]'
    );
}

function updateColorPreviews() {
    getColorPreviewInputs().forEach(updateColorPreview);
}

function bindColorPreviewInputs() {
    getColorPreviewInputs().forEach(input => {
        if (input.dataset.colorPreviewBound === "true") {
            return;
        }
        input.dataset.colorPreviewBound = "true";
        input.addEventListener("input", () => {
            updateColorPreview(input);
            updateAccentColor();
        });
        input.addEventListener("change", () => {
            updateColorPreview(input);
            updateAccentColor();
        });
        input.addEventListener("focus", () => updateColorPreview(input));
        updateColorPreview(input);
    });
}

function hexBrightness(hex) {
    hex = normalizeHexColor(hex);
    if (!hex) {
        return 0;
    }
    const r = parseInt(hex.substr(1,2), 16);
    const g = parseInt(hex.substr(3,2), 16);
    const b = parseInt(hex.substr(5,2), 16);
    return (
        0.2126 * r +
        0.7152 * g +
        0.0722 * b
    );
}

function updateAccentColor() {
    const leftElement = document.getElementById("left_color");
    const rightElement = document.getElementById("right_color");
    const fishElement = document.getElementById("fish_color");
    
    // Safely get values
    const left = leftElement ? leftElement.value.trim() : "";
    const right = rightElement ? rightElement.value.trim() : "";
    const fish = fishElement ? fishElement.value.trim() : "";
    
    // Normalize colors
    const normalizedLeft = normalizeHexColor(left);
    const normalizedRight = normalizeHexColor(right);
    const normalizedFish = normalizeHexColor(fish);
    
    // Helper: is a color too neutral (white/gray/black)?
    function isTooNeutral(hex) {
        if (!hex) return true;
        const brightness = hexBrightness(hex);
        const { r, g, b } = hexToRgb(hex);
        const max = Math.max(r, g, b);
        const min = Math.min(r, g, b);
        const isGray = (max - min) < 30;
        const isWhite = brightness > 235;
        const isBlack = brightness < 15;
        return isWhite || isBlack || isGray;
    }
    
    const leftValid = !isTooNeutral(normalizedLeft);
    const rightValid = !isTooNeutral(normalizedRight);
    const fishValid = !isTooNeutral(normalizedFish);
    
    let leftGradient = "#ffffff";
    let rightGradient = "#ffffff";
    let accentColor = "#ffffff"; // Always a valid hex color
    let isGradient = false;
    
    if (leftValid && rightValid) {
        // Both sides valid → gradient
        leftGradient = normalizedLeft;
        rightGradient = normalizedRight;
        accentColor = normalizedLeft; // Use left color for accent
        isGradient = true;
    } else if (leftValid) {
        // Only left valid → static
        leftGradient = normalizedLeft;
        rightGradient = normalizedLeft;
        accentColor = normalizedLeft;
    } else if (rightValid) {
        // Only right valid → static
        leftGradient = normalizedRight;
        rightGradient = normalizedRight;
        accentColor = normalizedRight;
    } else if (fishValid) {
        // Fallback to fish
        leftGradient = normalizedFish;
        rightGradient = normalizedFish;
        accentColor = normalizedFish;
    } else {
        // Ultimate fallback
        leftGradient = "#ffffff";
        rightGradient = "#ffffff";
        accentColor = "#ffffff";
    }
    
    // Apply CSS variables
    document.documentElement.style.setProperty("--left-gradient", leftGradient);
    document.documentElement.style.setProperty("--right-gradient", rightGradient);
    document.documentElement.style.setProperty("--accent-color", accentColor);
    
    // Glow version – use left color if gradient, otherwise the static color
    const glowBase = isGradient ? normalizedLeft : accentColor;
    const r = parseInt(glowBase.substr(1,2), 16);
    const g = parseInt(glowBase.substr(3,2), 16);
    const b = parseInt(glowBase.substr(5,2), 16);
    document.documentElement.style.setProperty(
        "--accent-glow",
        `rgba(${r}, ${g}, ${b}, 0.4)`
    );
    
    // Update button text contrast
    updateButtonContrast();
}

function hexToRgb(hex) {
    hex = hex.replace("#", "");
    if (hex.length === 3) {
        hex = hex.split("").map(c => c + c).join("");
    }
    const num = parseInt(hex, 16);
    return {
        r: (num >> 16) & 255,
        g: (num >> 8) & 255,
        b: num & 255
    };
}
function getBrightness(hex) {
    const { r, g, b } = hexToRgb(hex);
    return (r * 299 + g * 587 + b * 114) / 1000;
}
function updateButtonContrast() {
    const left =
        getComputedStyle(document.documentElement)
        .getPropertyValue("--left-gradient")
        .trim();
    const right =
        getComputedStyle(document.documentElement)
        .getPropertyValue("--right-gradient")
        .trim();
    const leftBrightness = getBrightness(normalizeHexColor(left) || "#3b82f6");
    const rightBrightness = getBrightness(normalizeHexColor(right) || "#8b5cf6");
    const average = (leftBrightness + rightBrightness) / 2;
    const textColor =
        average > 170
            ? "#111827"
            : "white";
    document.documentElement.style.setProperty(
        "--button-text",
        textColor
    );
}
document.addEventListener("DOMContentLoaded", () => {
    bindColorPreviewInputs();
    updateAccentColor();
    updateButtonContrast();
});

async function startMacro() {
    // Save current UI settings first
    const configName =
        document.getElementById(
            "disabled"
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