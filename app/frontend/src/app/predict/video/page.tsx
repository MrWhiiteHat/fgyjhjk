"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { ErrorAlert } from "@/components/ErrorAlert";
import { FileDropzone } from "@/components/FileDropzone";
import { Loader } from "@/components/Loader";
import { PredictionResult } from "@/components/PredictionResult";
import { UploadCard } from "@/components/UploadCard";
import { VideoPreview } from "@/components/VideoPreview";
import { useToast } from "@/components/ToastProvider";
import { usePredictVideo } from "@/hooks/usePredictVideo";
import { API_BASE_URL } from "@/lib/constants";
import { useScanHistory } from "@/hooks/useScanHistory";
import { MAX_VIDEO_UPLOAD_MB, VIDEO_ACCEPT_ATTR, VIDEO_AGGREGATION_STRATEGIES } from "@/lib/constants";
import { validateThreshold, validateVideoFile } from "@/lib/validators";

export default function PredictVideoPage(): React.JSX.Element {
  const [file, setFile] = useState<File | null>(null);
  const [threshold, setThreshold] = useState(0.5);
  const [frameStride, setFrameStride] = useState(3);
  const [maxFrames, setMaxFrames] = useState(60);
  const [aggregationStrategy, setAggregationStrategy] = useState<(typeof VIDEO_AGGREGATION_STRATEGIES)[number]>(
    "mean_probability"
  );
  const [generateReport, setGenerateReport] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const prediction = usePredictVideo();
  const { pushToast } = useToast();
  const history = useScanHistory();
  const apiOrigin = (() => {
    try {
      return new URL(API_BASE_URL).origin;
    } catch {
      return "";
    }
  })();

  const constraintsText = useMemo(() => `MP4/WEBM/MOV/AVI/MKV up to ${MAX_VIDEO_UPLOAD_MB} MB`, []);

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

    history.addItem("video", file?.name ?? "uploaded-video", prediction.data.data.result);
    pushToast("Video prediction completed", "success");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prediction.data]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);

    const validFile = validateVideoFile(file);
    if (!validFile.valid) {
      setFormError(validFile.message);
      return;
    }

    const validThreshold = validateThreshold(threshold);
    if (!validThreshold.valid) {
      setFormError(validThreshold.message);
      return;
    }

    await prediction.run({
      file: file as File,
      threshold,
      frameStride,
      maxFrames,
      aggregationStrategy,
      generateReport
    });
  };

  return (
    <section className="pageStack">
      <UploadCard
        title="Video Prediction"
        description="Upload one video and aggregate frame-level scores."
        constraintsText={constraintsText}
      >
        <form className="formGrid" onSubmit={handleSubmit}>
          <FileDropzone
            id="video-file"
            label="Video file"
            accept={VIDEO_ACCEPT_ATTR}
            helperText="Drop a short clip for frame-level deepfake analysis"
            file={file}
            onFileChange={setFile}
          />

          <label htmlFor="threshold">Threshold (0 to 1)</label>
          <input
            id="threshold"
            type="number"
            min={0}
            max={1}
            step={0.01}
            value={threshold}
            onChange={(event) => setThreshold(Number(event.target.value))}
          />

          <label htmlFor="frameStride">Frame stride</label>
          <input
            id="frameStride"
            type="number"
            min={1}
            step={1}
            value={frameStride}
            onChange={(event) => setFrameStride(Number(event.target.value) || 1)}
          />

          <label htmlFor="maxFrames">Max frames</label>
          <input
            id="maxFrames"
            type="number"
            min={1}
            step={1}
            value={maxFrames}
            onChange={(event) => setMaxFrames(Number(event.target.value) || 1)}
          />

          <label htmlFor="aggregation">Aggregation strategy</label>
          <select id="aggregation" value={aggregationStrategy} onChange={(event) => setAggregationStrategy(event.target.value as (typeof VIDEO_AGGREGATION_STRATEGIES)[number])}>
            {VIDEO_AGGREGATION_STRATEGIES.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>

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
              Run Video Prediction
            </button>
            <button type="button" className="secondaryButton" onClick={prediction.cancel}>
              Cancel
            </button>
          </div>
        </form>

        <VideoPreview file={file} />
        {prediction.loading ? <Loader text="Running video inference..." /> : null}
        <ErrorAlert message={formError || prediction.error} />
        {prediction.data ? (
          <>
            <PredictionResult result={prediction.data.data.result} />
            <div className="card">
              <h3>Video Aggregation</h3>
              <p>Frames processed: {prediction.data.data.num_frames_processed}</p>
              <p>Fake frame ratio: {(prediction.data.data.fake_frame_ratio * 100).toFixed(2)}%</p>
              <p>Aggregated probability: {(prediction.data.data.aggregated_probability * 100).toFixed(2)}%</p>
              <p>Aggregation strategy: {prediction.data.data.aggregation_strategy}</p>
            </div>
            {prediction.data.data.result.report_id ? (
              <div className="card">
                <h3>Report Download</h3>
                <ul className="linkList">
                  <li>
                    <a href={`${apiOrigin}/api/v1/reports/${prediction.data.data.result.report_id}/download?format=json`} target="_blank" rel="noreferrer">
                      Download JSON
                    </a>
                  </li>
                  <li>
                    <a href={`${apiOrigin}/api/v1/reports/${prediction.data.data.result.report_id}/download?format=txt`} target="_blank" rel="noreferrer">
                      Download TXT
                    </a>
                  </li>
                  <li>
                    <a href={`${apiOrigin}/api/v1/reports/${prediction.data.data.result.report_id}/download?format=csv`} target="_blank" rel="noreferrer">
                      Download CSV
                    </a>
                  </li>
                </ul>
              </div>
            ) : null}
          </>
        ) : null}
      </UploadCard>
    </section>
  );
}
