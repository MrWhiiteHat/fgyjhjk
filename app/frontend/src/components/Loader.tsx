interface LoaderProps {
  text?: string;
}

export function Loader({ text = "Loading..." }: LoaderProps): React.JSX.Element {
  return (
    <div className="loader" role="status" aria-live="polite">
      <span className="loaderDot" aria-hidden="true" />
      <span>{text}</span>
    </div>
  );
}
