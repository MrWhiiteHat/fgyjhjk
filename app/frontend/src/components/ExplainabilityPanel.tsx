import { ExplainabilityData } from "@/lib/types";
import { API_BASE_URL } from "@/lib/constants";

interface ExplainabilityPanelProps {
  payload: ExplainabilityData;
}

export function ExplainabilityPanel({ payload }: ExplainabilityPanelProps): React.JSX.Element {
  const apiOrigin = (() => {
    try {
      return new URL(API_BASE_URL).origin;
    } catch {
      return "";
    }
  })();

  const resolveUrl = (path: string) => {
    if (path.startsWith("http://") || path.startsWith("https://")) {
      return path;
    }
    if (path.startsWith("/")) {
      return `${apiOrigin}${path}`;
    }
    return path;
  };

  return (
    <section className="card" aria-label="Explainability result">
      <h3>Explainability Result</h3>
      <dl className="metaList">
        <div>
          <dt>Type</dt>
          <dd>{payload.explanation_type}</dd>
        </div>
        <div>
          <dt>Target Layer</dt>
          <dd>{payload.target_layer || "default"}</dd>
        </div>
        <div>
          <dt>Generated At</dt>
          <dd>{payload.generated_at}</dd>
        </div>
      </dl>
      <ul className="linkList">
        <li>
          <a href={resolveUrl(payload.heatmap_path)} target="_blank" rel="noreferrer">
            Heatmap Output
          </a>
        </li>
        <li>
          <a href={resolveUrl(payload.overlay_path)} target="_blank" rel="noreferrer">
            Overlay Output
          </a>
        </li>
      </ul>
    </section>
  );
}
