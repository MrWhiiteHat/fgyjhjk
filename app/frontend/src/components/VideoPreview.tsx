"use client";

import { useEffect, useMemo } from "react";

interface VideoPreviewProps {
  file: File | null;
}

export function VideoPreview({ file }: VideoPreviewProps): React.JSX.Element {
  const previewUrl = useMemo(() => {
    if (!file) {
      return "";
    }
    return URL.createObjectURL(file);
  }, [file]);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  if (!file || !previewUrl) {
    return <p className="muted">No video selected.</p>;
  }

  return (
    <video className="videoPreview" src={previewUrl} controls preload="metadata" aria-label="Selected video preview">
      <track kind="captions" />
    </video>
  );
}
