type JsonViewProps = {
  label: string;
  data: unknown;
};

export function JsonView({ label, data }: JsonViewProps) {
  if (!data) {
    return null;
  }

  return (
    <div className="jsonBlock">
      <h3>{label}</h3>
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </div>
  );
}
