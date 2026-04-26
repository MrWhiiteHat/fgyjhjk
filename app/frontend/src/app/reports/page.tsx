"use client";

import { FormEvent, useEffect, useState } from "react";

import { ErrorAlert } from "@/components/ErrorAlert";
import { Loader } from "@/components/Loader";
import { ReportDownloadCard } from "@/components/ReportDownloadCard";
import { useToast } from "@/components/ToastProvider";
import { UploadCard } from "@/components/UploadCard";
import { useReports } from "@/hooks/useReports";
import { validateReportId } from "@/lib/validators";

export default function ReportsPage(): React.JSX.Element {
  const [reportId, setReportId] = useState("");
  const [reportFormat, setReportFormat] = useState<"json" | "txt" | "csv">("json");
  const [formError, setFormError] = useState<string | null>(null);

  const reports = useReports();
  const { pushToast } = useToast();

  useEffect(() => {
    if (reports.error) {
      pushToast(reports.error, "error");
    }
  }, [pushToast, reports.error]);

  useEffect(() => {
    if (reports.data) {
      pushToast("Report metadata fetched", "success");
    }
  }, [pushToast, reports.data]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);

    const valid = validateReportId(reportId);
    if (!valid.valid) {
      setFormError(valid.message);
      return;
    }

    await reports.run(reportId.trim(), reportFormat);
  };

  return (
    <section className="pageStack">
      <UploadCard
        title="Report Retrieval"
        description="Fetch report artifact metadata and download paths by report ID."
        constraintsText="Report ID must be a valid value emitted by prediction responses"
      >
        <form className="formGrid" onSubmit={handleSubmit}>
          <label htmlFor="report-id">Report ID</label>
          <input
            id="report-id"
            type="text"
            value={reportId}
            onChange={(event) => setReportId(event.target.value)}
            placeholder="e.g. 1e5ad871-..."
          />

          <label htmlFor="report-format">Preferred format</label>
          <select id="report-format" value={reportFormat} onChange={(event) => setReportFormat(event.target.value as "json" | "txt" | "csv")}
          >
            <option value="json">json</option>
            <option value="txt">txt</option>
            <option value="csv">csv</option>
          </select>

          <div className="buttonRow">
            <button type="submit" className="primaryButton" disabled={reports.loading}>
              Fetch Report
            </button>
            <button type="button" className="secondaryButton" onClick={reports.cancel}>
              Cancel
            </button>
          </div>
        </form>

        {reports.loading ? <Loader text="Fetching report..." /> : null}
        <ErrorAlert message={formError || reports.error} />
        {reports.data ? <ReportDownloadCard report={reports.data.data} /> : null}
      </UploadCard>
    </section>
  );
}
