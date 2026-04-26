import React, { useEffect, useState } from "react";

import { PopupResultCard } from "@/components/PopupResultCard";
import { ScanControls } from "@/components/ScanControls";
import { ScanSummary } from "@/components/ScanSummary";
import { summarizeResults } from "@/lib/helpers";
import { RuntimeMessage, ScanResult } from "@/lib/types";

export function PopupApp(): React.JSX.Element {
  const [results, setResults] = useState<ScanResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    chrome.runtime.sendMessage({ action: "GET_LAST_RESULTS" } as RuntimeMessage, (response) => {
      if (response?.ok) {
        setResults(response.results || []);
      }
    });
  }, []);

  const triggerScan = () => {
    setLoading(true);
    setError("");
    chrome.runtime.sendMessage({ action: "SCAN_PAGE" } as RuntimeMessage, (response) => {
      setLoading(false);
      if (!response?.ok) {
        setError(response?.error || "Page scan failed");
        return;
      }
      setResults(response.results || []);
    });
  };

  const summary = summarizeResults(results);

  return (
    <div className="popup-root">
      <h1>RealFake Detector</h1>
      <ScanControls loading={loading} onScan={triggerScan} />
      {error ? <p className="error-text">{error}</p> : null}
      <ScanSummary summary={summary} />
      <div className="result-list">
        {results.map((item) => (
          <PopupResultCard key={item.candidateId} result={item} />
        ))}
      </div>
    </div>
  );
}
