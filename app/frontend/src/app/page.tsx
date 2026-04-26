"use client";

import { useEffect, useState } from "react";

import { DashboardAnalytics } from "@/components/DashboardAnalytics";
import { ErrorAlert } from "@/components/ErrorAlert";
import { Loader } from "@/components/Loader";
import { MetricsTable } from "@/components/MetricsTable";
import { RecentScans } from "@/components/RecentScans";
import { getHealth, getModelInfo, getReady } from "@/lib/api";
import { useScanHistory } from "@/hooks/useScanHistory";
import { HealthData, ModelInfoData } from "@/lib/types";
import { toFriendlyError } from "@/lib/helpers";

export default function DashboardPage(): React.JSX.Element {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthData | null>(null);
  const [model, setModel] = useState<ModelInfoData | null>(null);
  const [ready, setReady] = useState<boolean>(false);
  const history = useScanHistory();

  useEffect(() => {
    const controller = new AbortController();
    const run = async () => {
      setLoading(true);
      setError(null);
      try {
        const [healthRes, readyRes, modelRes] = await Promise.all([getHealth(), getReady(), getModelInfo()]);
        setHealth(healthRes.data);
        setReady(Boolean(readyRes.data.ready));
        setModel(modelRes.data);
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(toFriendlyError(err));
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    };

    void run();
    return () => {
      controller.abort();
    };
  }, []);

  return (
    <section className="pageStack">
      <header className="heroCard">
        <h1>Detection Dashboard</h1>
        <p>
          Use this console to run image/video inference, generate explainability artifacts, and inspect report outputs.
        </p>
        <p className={ready ? "statusText statusReady" : "statusText statusNotReady"}>
          {ready ? "Backend readiness: READY" : "Backend readiness: NOT READY"}
        </p>
      </header>

      {loading ? <Loader text="Loading backend status..." /> : null}
      <ErrorAlert message={error} />

      <DashboardAnalytics
        totalScans={history.analytics.totalScans}
        fakeRate={history.analytics.fakeRate}
        avgConfidence={history.analytics.avgConfidence}
      />

      <div className="grid2">
        <MetricsTable
          title="Service Health"
          values={{
            status: health?.app_status ?? "unknown",
            model_loaded: health?.model_loaded ?? false,
            device: health?.device ?? "unknown",
            uptime_seconds: health?.uptime_seconds ?? 0,
            version: health?.version ?? "n/a"
          }}
        />

        <MetricsTable
          title="Model Metadata"
          values={{
            model_name: model?.model_name ?? "unknown",
            model_type: model?.model_type ?? "unknown",
            threshold: model?.threshold ?? "n/a",
            explainability_enabled: model?.explainability_enabled ?? false,
            artifact_path: model?.artifact_path ?? "n/a"
          }}
        />
      </div>

      <RecentScans items={history.items} onClear={history.clear} />
    </section>
  );
}
