interface MetricsTableProps {
  title: string;
  values: Record<string, string | number | boolean>;
}

export function MetricsTable({ title, values }: MetricsTableProps): React.JSX.Element {
  const rows = Object.entries(values);
  return (
    <section className="card" aria-label={title}>
      <h3>{title}</h3>
      <table className="metricsTable">
        <thead>
          <tr>
            <th scope="col">Metric</th>
            <th scope="col">Value</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([key, value]) => (
            <tr key={key}>
              <td>{key}</td>
              <td>{String(value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
