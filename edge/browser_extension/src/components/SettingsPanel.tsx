import React from "react";

import { ExtensionSettings } from "@/lib/types";

interface SettingsPanelProps {
  settings: ExtensionSettings;
  onChange: (settings: ExtensionSettings) => void;
  onSave: () => void;
}

export function SettingsPanel({ settings, onChange, onSave }: SettingsPanelProps): React.JSX.Element {
  return (
    <div className="settings-panel">
      <label>
        Inference Mode
        <select
          value={settings.inferenceMode}
          onChange={(event) => onChange({ ...settings, inferenceMode: event.target.value as ExtensionSettings["inferenceMode"] })}
        >
          <option value="local">Local</option>
          <option value="backend">Backend</option>
          <option value="auto">Auto</option>
        </select>
      </label>

      <label>
        Backend Base URL
        <input
          type="text"
          value={settings.backendBaseUrl}
          onChange={(event) => onChange({ ...settings, backendBaseUrl: event.target.value })}
        />
      </label>

      <label>
        Scan Limit
        <input
          type="number"
          min={1}
          max={100}
          value={settings.scanLimit}
          onChange={(event) => onChange({ ...settings, scanLimit: Number(event.target.value) || 40 })}
        />
      </label>

      <label>
        <input
          type="checkbox"
          checked={settings.autoScanEnabled}
          onChange={(event) => onChange({ ...settings, autoScanEnabled: event.target.checked })}
        />
        Auto Scan on Page Load
      </label>

      <label>
        <input
          type="checkbox"
          checked={settings.overlayEnabled}
          onChange={(event) => onChange({ ...settings, overlayEnabled: event.target.checked })}
        />
        Show Overlay Badges
      </label>

      <button type="button" onClick={onSave}>Save Settings</button>
    </div>
  );
}
