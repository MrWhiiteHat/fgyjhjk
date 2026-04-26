import { formatPercentScore } from "@/lib/helpers";

interface ConfidenceBarProps {
  value: number;
  label?: string;
}

export function ConfidenceBar({ value, label = "Model score" }: ConfidenceBarProps): React.JSX.Element {
  const normalized = Math.max(0, Math.min(1, value));

  return (
    <div className="confidenceGroup">
      <div className="confidenceHeader">
        <span>{label}</span>
        <strong>{formatPercentScore(normalized)}</strong>
      </div>
      <div className="confidenceTrack" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={normalized * 100}>
        <div className="confidenceFill" style={{ width: `${normalized * 100}%` }} />
      </div>
      <p className="scoreNote">Score reflects model confidence, not absolute truth.</p>
    </div>
  );
}
