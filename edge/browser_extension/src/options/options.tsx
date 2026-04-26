import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

import { DEFAULT_SETTINGS } from "@/lib/constants";
import { ExtensionSettings } from "@/lib/types";
import { SettingsPanel } from "@/components/SettingsPanel";

function OptionsApp(): React.JSX.Element {
  const [settings, setSettings] = useState<ExtensionSettings>(DEFAULT_SETTINGS);
  const [status, setStatus] = useState("");

  useEffect(() => {
    chrome.runtime.sendMessage({ action: "GET_SETTINGS" }, (response) => {
      if (response?.ok) {
        setSettings(response.settings || DEFAULT_SETTINGS);
      }
    });
  }, []);

  const save = (next: ExtensionSettings) => {
    chrome.runtime.sendMessage({ action: "SET_SETTINGS", payload: next }, (response) => {
      if (response?.ok) {
        setSettings(next);
        setStatus("Settings saved");
      } else {
        setStatus(response?.error || "Unable to save settings");
      }
    });
  };

  return (
    <div className="options-root">
      <h1>Extension Settings</h1>
      <SettingsPanel settings={settings} onChange={setSettings} onSave={() => save(settings)} />
      {status ? <p>{status}</p> : null}
    </div>
  );
}

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error("Options root not found");
}
createRoot(rootEl).render(
  <React.StrictMode>
    <OptionsApp />
  </React.StrictMode>
);
