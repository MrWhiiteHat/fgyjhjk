"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { ErrorAlert } from "@/components/ErrorAlert";
import { FileDropzone } from "@/components/FileDropzone";
import { ImagePreview } from "@/components/ImagePreview";
import { Loader } from "@/components/Loader";
import { PredictionResult } from "@/components/PredictionResult";
import { UploadCard } from "@/components/UploadCard";
import { useToast } from "@/components/ToastProvider";
import { usePredictImage } from "@/hooks/usePredictImage";
import { API_BASE_URL } from "@/lib/constants";
import { useScanHistory } from "@/hooks/useScanHistory";
import { IMAGE_ACCEPT_ATTR, MAX_IMAGE_UPLOAD_MB } from "@/lib/constants";
import { validateImageFile, validateThreshold } from "@/lib/validators";

export default function PredictImagePage(): React.JSX.Element {
  const [file, setFile] = useState<File | null>(null);
  const [threshold, setThreshold] = useState(0.5);
  const [explain, setExplain] = useState(false);
  const [generateReport, setGenerateReport] = useState(false);
  const [lastRequestOptions, setLastRequestOptions] = useState<{ explain: boolean; generateReport: boolean } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const prediction = usePredictImage();
  const { pushToast } = useToast();
  const history = useScanHistory();
  const apiOrigin = (() => {
    try {
      return new URL(API_BASE_URL).origin;
    } catch {
      return "";
    }
  })();

  const constraintsText = useMemo(() => `JPEG/PNG/WEBP/BMP up to ${MAX_IMAGE_UPLOAD_MB} MB`, []);
  const warningMessages = useMemo(() => {
    const metadata = prediction.data?.data?.metadata_summary;
    if (!metadata || typeof metadata !== "object") {
      return [] as string[];
    }

    const maybeWarnings = (metadata as Record<string, unknown>).warnings;
    if (!Array.isArray(maybeWarnings)) {
      return [] as string[];
    }

    return maybeWarnings.map((item) => String(item)).filter((item) => item.trim().length > 0);
  }, [prediction.data]);
  const loaderText =
    explain || generateReport
      ? "Running prediction, generating explainability/report..."
      : "Running image inference...";

  // Guard to fire side-effects only once per new prediction result.
  const lastProcessedRequestId = useRef<string | null>(null);

  useEffect(() => {
    if (prediction.error) {
      pushToast(prediction.error, "error");
    }
  }, [prediction.error, pushToast]);

  useEffect(() => {
    if (!prediction.data) {
      return;
    }
    // Prevent re-firing for the same prediction result.
    const requestId = prediction.data.request_id;
    if (lastProcessedRequestId.current === requestId) {
      return;
    }
    lastProcessedRequestId.current = requestId;

    history.addItem("image", file?.name ?? "uploaded-image", prediction.data.data.prediction);
    pushToast("Image prediction completed", "success");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prediction.data]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);

    const validFile = validateImageFile(file);
    if (!validFile.valid) {
      setFormError(validFile.message);
      return;
    }

    const validThreshold = validateThreshold(threshold);
    if (!validThreshold.valid) {
      setFormError(validThreshold.message);
      return;
    }

    setLastRequestOptions({ explain, generateReport });

    await prediction.run({
      file: file as File,
      threshold,
      explain,
      generateReport
    });
  };

  return (
    <section className="pageStack">
      <UploadCard
        title="Image Prediction"
        description="Upload one image and receive prediction scores."
        constraintsText={constraintsText}
      >
        <form className="formGrid" onSubmit={handleSubmit}>
          <FileDropzone
            id="image-file"
            label="Image file"
            accept={IMAGE_ACCEPT_ATTR}
            helperText="Drop a single face image for real/fake assessment"
            file={file}
            onFileChange={setFile}
          />

          <label htmlFor="threshold">Threshold (0 to 1)</label>
          <input
            id="threshold"
            name="threshold"
            type="number"
            min={0}
            max={1}
            step={0.01}
            value={threshold}
            onChange={(event) => setThreshold(Number(event.target.value))}
          />

          <label className="checkboxRow" htmlFor="explain">
            <input id="explain" type="checkbox" checked={explain} onChange={(event) => setExplain(event.target.checked)} />
            Generate explainability
          </label>

          <label className="checkboxRow" htmlFor="report">
            <input
              id="report"
              type="checkbox"
              checked={generateReport}
              onChange={(event) => setGenerateReport(event.target.checked)}
            />
            Generate report
          </label>

          <div className="buttonRow">
            <button type="submit" className="primaryButton" disabled={prediction.loading}>
              Run Prediction
            </button>
            <button type="button" className="secondaryButton" onClick={prediction.cancel}>
              Cancel
            </button>
          </div>
        </form>

        <ImagePreview file={file} />
        {prediction.loading ? <Loader text={loaderText} /> : null}
        {prediction.loading && (explain || generateReport) ? (
          <p className="muted">Large images can take longer when explainability or report generation is enabled.</p>
        ) : null}
        <ErrorAlert message={formError || prediction.error} />
        {warningMessages.length > 0 ? (
          <div className="card">
            <h3>Warnings</h3>
            <ul className="linkList">
              {warningMessages.map((warning, index) => (
                <li key={`${index}-${warning}`}>{warning}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {prediction.data ? <PredictionResult result={prediction.data.data.prediction} /> : null}
        {prediction.data?.data.explainability ? (
          <div className="card">
            <h3>Explainability</h3>
            <p className="muted">Heatmap artifacts are ready for visual interpretation.</p>
            <ul className="linkList">
              <li>
                <a
                  href={
                    String(prediction.data.data.explainability.heatmap_path ?? "").startsWith("/")
                      ? `${apiOrigin}${String(prediction.data.data.explainability.heatmap_path ?? "")}`
                      : String(prediction.data.data.explainability.heatmap_path ?? "")
                  }
                  target="_blank"
                  rel="noreferrer"
                >
                  View Heatmap
                </a>
              </li>
              <li>
                <a
                  href={
                    String(prediction.data.data.explainability.overlay_path ?? "").startsWith("/")
                      ? `${apiOrigin}${String(prediction.data.data.explainability.overlay_path ?? "")}`
                      : String(prediction.data.data.explainability.overlay_path ?? "")
                  }
                  target="_blank"
                  rel="noreferrer"
                >
                  View Overlay
                </a>
              </li>
            </ul>
          </div>
        ) : lastRequestOptions?.explain ? (
          <div className="card">
            <h3>Explainability</h3>
            <p className="muted">Explainability was requested but not generated for this run. Check warnings above for details.</p>
          </div>
        ) : (
          <div className="card">
            <h3>Explainability</h3>
            <p className="muted">Enable explainability to generate heatmap overlays for model reasoning.</p>
          </div>
        )}
        {prediction.data?.data.report ? (
          <div className="card">
            <h3>Report Download</h3>
            <p className="muted">Download structured evidence for audit and sharing.</p>
            <ul className="linkList">
              {Object.entries(prediction.data.data.report.files).map(([format, url]) => (
                <li key={format}>
                  <a href={url.startsWith("/") ? `${apiOrigin}${url}` : url} target="_blank" rel="noreferrer">
                    Download {format.toUpperCase()}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ) : lastRequestOptions?.generateReport ? (
          <div className="card">
            <h3>Report Status</h3>
            <p className="muted">Report was requested but could not be generated for this run. Check warnings above for details.</p>
          </div>
        ) : null}
        <div className="card">
          <h3>Batch Upload</h3>
          <p className="muted">
            Batch image upload is planned for the next release. Use the video route for multi-frame analysis today.
          </p>
        </div>
      </UploadCard>
    </section>
  );
}
