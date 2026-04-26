import React from "react";

import { ScanResult } from "@/lib/types";

interface PopupResultCardProps {
  result: ScanResult;
}

export function PopupResultCard({ result }: PopupResultCardProps): React.JSX.Element {
  return (
    <div className="result-card">
      <p className="result-src" title={result.src}>{result.src}</p>
      <p>
        Label: <strong>{result.predictedLabel}</strong>
      </p>
      <p>Confidence: {(result.predictedProbability * 100).toFixed(2)}%</p>
      <p>Source: {result.modelSource}</p>
      {result.error ? <p className="error-text">{result.error}</p> : null}
    </div>
  );
}
