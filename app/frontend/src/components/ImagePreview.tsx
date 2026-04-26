"use client";

import { useEffect, useMemo } from "react";

interface ImagePreviewProps {
  file: File | null;
}

export function ImagePreview({ file }: ImagePreviewProps): React.JSX.Element {
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
    return <p className="muted">No image selected.</p>;
  }

  return <img src={previewUrl} alt="Selected upload preview" className="imagePreview" />;
}
