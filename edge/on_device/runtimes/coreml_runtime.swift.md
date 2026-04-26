# CoreML Runtime Bridge Specification

This project includes a documented CoreML integration path for iOS native inference.

## Scope
- Native bridge guidance for converting exported PyTorch/ONNX models into CoreML.
- Standardized method mapping to the shared runtime contract:
  - load_model()
  - preprocess_input()
  - run_inference()
  - postprocess_output()
  - unload_model()

## Expected Swift Components
- `EdgeModelManager`: loads and caches compiled `.mlmodelc` artifact.
- `ImagePreprocessor`: enforces the same input size and normalization values as edge configs.
- `InferenceRunner`: executes prediction and maps output into shared schema.
- `RuntimeTelemetry`: captures model load time and inference latency.

## Output Contract (must match backend style)
```json
{
  "predicted_label": "REAL|FAKE",
  "predicted_probability": 0.0,
  "probabilities": {"REAL": 0.0, "FAKE": 0.0},
  "threshold": 0.5,
  "model_source": "coreml_local",
  "inference_time_ms": 0.0
}
```

## Conversion Notes
- Preferred path: ONNX -> CoreML (`coremltools`), then verify against reference predictions.
- Support float16 model generation where feasible.
- Quantized int8 support depends on model operator set and should be validated per release.

## Security Notes
- Package model in app bundle, optionally encrypted with device-bound key material.
- Avoid writing raw media to unprotected temporary folders.
- Respect privacy mode toggles to skip cloud sync.

## Validation Expectations
- Probability deviation threshold against reference model <= 0.05 absolute by default.
- Latency benchmark should include cold-start and warm runs.
- Failure path must return typed error instead of crashing UI thread.
