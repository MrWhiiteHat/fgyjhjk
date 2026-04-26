"use client";

import { useMemo, useRef, useState } from "react";

interface FileDropzoneProps {
  id: string;
  label: string;
  accept: string;
  helperText: string;
  file: File | null;
  onFileChange: (file: File | null) => void;
}

export function FileDropzone({ id, label, accept, helperText, file, onFileChange }: FileDropzoneProps): React.JSX.Element {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const selectedName = useMemo(() => {
    if (!file) {
      return "No file selected yet";
    }
    return `${file.name} (${Math.max(1, Math.round(file.size / 1024))} KB)`;
  }, [file]);

  const onDrop: React.DragEventHandler<HTMLDivElement> = (event) => {
    event.preventDefault();
    setIsDragging(false);
    const dropped = event.dataTransfer.files?.[0] ?? null;
    onFileChange(dropped);
  };

  return (
    <div className="dropzoneStack">
      <label htmlFor={id}>{label}</label>
      <div
        className={isDragging ? "dropzone dropzoneActive" : "dropzone"}
        onDragOver={(event) => {
          event.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            inputRef.current?.click();
          }
        }}
      >
        <p className="dropzonePrimary">Drag and drop here, or click to browse</p>
        <p className="dropzoneSecondary">{helperText}</p>
        <p className="dropzoneFile">{selectedName}</p>
      </div>
      <input
        id={id}
        ref={inputRef}
        name={id}
        type="file"
        accept={accept}
        className="visuallyHidden"
        onChange={(event) => onFileChange(event.target.files?.[0] ?? null)}
      />
    </div>
  );
}
