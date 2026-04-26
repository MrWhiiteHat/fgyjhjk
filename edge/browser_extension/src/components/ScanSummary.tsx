import React from "react";

import { ScanSummary as ScanSummaryType } from "@/lib/types";

interface ScanSummaryProps {
  summary: ScanSummaryType;
}

export function ScanSummary({ summary }: ScanSummaryProps): React.JSX.Element {
  return (
    <div className="scan-summary">
      <p>Scanned: {summary.scanned}</p>
      <p>FAKE: {summary.fakeCount}</p>
      <p>REAL: {summary.realCount}</p>
      <p>UNKNOWN: {summary.unknownCount}</p>
    </div>
  );
}
