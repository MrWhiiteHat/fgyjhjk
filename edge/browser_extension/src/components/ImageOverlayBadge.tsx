import React from "react";

interface ImageOverlayBadgeProps {
  label: string;
  probability: number;
}

export function ImageOverlayBadge({ label, probability }: ImageOverlayBadgeProps): React.JSX.Element {
  return (
    <span className="overlay-badge">
      {label} {(probability * 100).toFixed(1)}%
    </span>
  );
}
