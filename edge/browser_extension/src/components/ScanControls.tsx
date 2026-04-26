import React from "react";

interface ScanControlsProps {
  loading: boolean;
  onScan: () => void;
}

export function ScanControls({ loading, onScan }: ScanControlsProps): React.JSX.Element {
  return (
    <div className="scan-controls">
      <button type="button" onClick={onScan} disabled={loading}>
        {loading ? "Scanning..." : "Scan Current Page"}
      </button>
    </div>
  );
}
