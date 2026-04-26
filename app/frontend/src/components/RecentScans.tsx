import { HistoryItem } from "@/hooks/useScanHistory";
import { formatPercentScore } from "@/lib/helpers";

interface RecentScansProps {
  items: HistoryItem[];
  onClear: () => void;
}

export function RecentScans({ items, onClear }: RecentScansProps): React.JSX.Element {
  return (
    <section className="card" aria-label="Recent scan history">
      <div className="sectionHeaderRow">
        <h3>Recent Scan History</h3>
        <button type="button" className="secondaryButton" onClick={onClear} disabled={items.length === 0}>
          Clear
        </button>
      </div>

      {items.length === 0 ? <p className="muted">No scan history yet. Run an image or video prediction to populate this panel.</p> : null}

      {items.length > 0 ? (
        <ul className="historyList">
          {items.slice(0, 8).map((item) => (
            <li key={item.id} className="historyItem">
              <div>
                <p className="historyTitle">{item.filename}</p>
                <p className="historyMeta">
                  {item.mode.toUpperCase()} · {new Date(item.timestamp).toLocaleString()}
                </p>
              </div>
              <div className="historyStats">
                <span className={`riskBadge risk-${item.result.risk_level}`}>{item.result.risk_level}</span>
                <strong>{formatPercentScore(item.result.risk_score)}</strong>
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
