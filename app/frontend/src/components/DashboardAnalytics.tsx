import { formatPercentScore } from "@/lib/helpers";

interface DashboardAnalyticsProps {
  totalScans: number;
  fakeRate: number;
  avgConfidence: number;
}

export function DashboardAnalytics({ totalScans, fakeRate, avgConfidence }: DashboardAnalyticsProps): React.JSX.Element {
  return (
    <section className="grid3" aria-label="Dashboard analytics">
      <article className="statCard">
        <p className="statLabel">Total Scans</p>
        <p className="statValue">{totalScans}</p>
      </article>
      <article className="statCard">
        <p className="statLabel">Estimated Risk Rate</p>
        <p className="statValue">{formatPercentScore(fakeRate)}</p>
      </article>
      <article className="statCard">
        <p className="statLabel">Average Confidence</p>
        <p className="statValue">{formatPercentScore(avgConfidence)}</p>
      </article>
    </section>
  );
}
