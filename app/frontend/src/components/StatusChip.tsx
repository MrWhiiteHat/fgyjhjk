type StatusChipProps = {
  variant: "idle" | "ok" | "error" | "loading";
  text: string;
};

export function StatusChip({ variant, text }: StatusChipProps) {
  return <span className={`statusChip statusChip-${variant}`}>{text}</span>;
}
