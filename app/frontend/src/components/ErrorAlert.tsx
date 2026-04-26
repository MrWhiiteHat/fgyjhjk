interface ErrorAlertProps {
  message: string | null;
}

export function ErrorAlert({ message }: ErrorAlertProps): React.JSX.Element | null {
  if (!message) {
    return null;
  }
  return (
    <div className="errorAlert" role="alert" aria-live="assertive">
      {message}
    </div>
  );
}
