import { PredictionResult as PredictionResultType } from "@/lib/types";
import { ConfidenceBar } from "@/components/ConfidenceBar";
import { formatMs } from "@/lib/helpers";

interface PredictionResultProps {
  result: PredictionResultType;
}

export function PredictionResult({ result }: PredictionResultProps): React.JSX.Element {
  return (
    <section className="resultCard" aria-label="Prediction result">
      <h3>Prediction Summary</h3>
      <p>
        Final Decision: <strong>{result.final_decision || result.predicted_label}</strong>
      </p>
      <div className="badgeRow">
        <span className={`riskBadge risk-${result.risk_level}`}>Risk {result.risk_level.toUpperCase()}</span>
        {result.uncertain_prediction ? <span className="riskBadge risk-uncertain">Uncertain</span> : null}
      </div>
      <ConfidenceBar value={result.confidence_score} label="Confidence score" />
      <ConfidenceBar value={result.authenticity_score} label="Authenticity score" />
      <ConfidenceBar value={result.risk_score} label="Risk score" />
      <dl className="metaList">
        <div>
          <dt>Threshold Used</dt>
          <dd>{result.threshold_used.toFixed(2)}</dd>
        </div>
        <div>
          <dt>Uncertainty Margin</dt>
          <dd>{result.uncertainty_margin.toFixed(3)}</dd>
        </div>
        <div>
          <dt>Inference Time</dt>
          <dd>{formatMs(result.inference_time_ms)}</dd>
        </div>
        <div>
          <dt>Model</dt>
          <dd>{result.model_name}</dd>
        </div>
        <div>
          <dt>Artifact</dt>
          <dd className="artifactText">{result.artifact_path}</dd>
        </div>
      </dl>
    </section>
  );
}
