"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { ErrorAlert } from "@/components/ErrorAlert";
import { ExplainabilityPanel } from "@/components/ExplainabilityPanel";
import { FileDropzone } from "@/components/FileDropzone";
import { ImagePreview } from "@/components/ImagePreview";
import { Loader } from "@/components/Loader";
import { useToast } from "@/components/ToastProvider";
import { UploadCard } from "@/components/UploadCard";
import { useExplain } from "@/hooks/useExplain";
import { IMAGE_ACCEPT_ATTR, MAX_IMAGE_UPLOAD_MB } from "@/lib/constants";
import { validateImageFile } from "@/lib/validators";

export default function ExplainPage(): React.JSX.Element {
  const [file, setFile] = useState<File | null>(null);
  const [explanationType, setExplanationType] = useState<"gradcam" | "saliency" | "both">("both");
  const [targetLayer, setTargetLayer] = useState("layer4");
  const [formError, setFormError] = useState<string | null>(null);

  const explain = useExplain();
  const { pushToast } = useToast();
  const constraintsText = useMemo(() => `JPEG/PNG/WEBP/BMP up to ${MAX_IMAGE_UPLOAD_MB} MB`, []);

  useEffect(() => {
    if (explain.error) {
      pushToast(explain.error, "error");
    }
  }, [explain.error, pushToast]);

  useEffect(() => {
    if (explain.data) {
      pushToast("Explainability map generated", "success");
    }
  }, [explain.data, pushToast]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);

    const validFile = validateImageFile(file);
    if (!validFile.valid) {
      setFormError(validFile.message);
      return;
    }

    await explain.run({
      file: file as File,
      explanationType,
      targetLayer: targetLayer.trim() || undefined
    });
  };

  return (
    <section className="pageStack">
      <UploadCard
        title="Explainability"
        description="Generate Grad-CAM/saliency overlays for one uploaded image."
        constraintsText={constraintsText}
      >
        <form className="formGrid" onSubmit={handleSubmit}>
          <FileDropzone
            id="image-file"
            label="Image file"
            accept={IMAGE_ACCEPT_ATTR}
            helperText="Drop an image to generate heatmap and saliency overlays"
            file={file}
            onFileChange={setFile}
          />

          <label htmlFor="explanation-type">Explanation type</label>
          <select
            id="explanation-type"
            value={explanationType}
            onChange={(event) => setExplanationType(event.target.value as "gradcam" | "saliency" | "both")}
          >
            <option value="gradcam">gradcam</option>
            <option value="saliency">saliency</option>
            <option value="both">both</option>
          </select>

          <label htmlFor="target-layer">Target layer</label>
          <input
            id="target-layer"
            type="text"
            value={targetLayer}
            onChange={(event) => setTargetLayer(event.target.value)}
          />

          <div className="buttonRow">
            <button type="submit" className="primaryButton" disabled={explain.loading}>
              Generate Explanation
            </button>
            <button type="button" className="secondaryButton" onClick={explain.cancel}>
              Cancel
            </button>
          </div>
        </form>

        <ImagePreview file={file} />
        {explain.loading ? <Loader text="Generating explanation..." /> : null}
        <ErrorAlert message={formError || explain.error} />
        {explain.data ? <ExplainabilityPanel payload={explain.data.data} /> : null}
      </UploadCard>
    </section>
  );
}
