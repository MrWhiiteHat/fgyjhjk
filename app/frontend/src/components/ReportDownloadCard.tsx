import { ReportData } from "@/lib/types";
import { API_BASE_URL } from "@/lib/constants";

interface ReportDownloadCardProps {
  report: ReportData;
}

export function ReportDownloadCard({ report }: ReportDownloadCardProps): React.JSX.Element {
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
    <section className="card" aria-label="Report download links">
      <h3>Report {report.report_id}</h3>
      <ul className="linkList">
        {Object.entries(report.files).map(([format, path]) => (
          <li key={format}>
            <a href={resolveUrl(path)} target="_blank" rel="noreferrer">
              {format.toUpperCase()} file
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}
