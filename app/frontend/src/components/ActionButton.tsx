type ActionButtonProps = {
  label: string;
  loading?: boolean;
  disabled?: boolean;
  onClick?: () => void;
  type?: "button" | "submit";
};

export function ActionButton({ label, loading = false, disabled = false, onClick, type = "button" }: ActionButtonProps) {
  return (
    <button className="actionButton" type={type} disabled={disabled || loading} onClick={onClick}>
      {loading ? "Working..." : label}
    </button>
  );
}
