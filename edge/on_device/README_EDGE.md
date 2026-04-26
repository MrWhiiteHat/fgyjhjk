# Edge On-Device Inference Layer

This directory contains runtime-compatible preprocessing, model conversion, quantization, benchmarking, and validation utilities for edge deployment targets.

## Submodules
- `configs/`: deployment configuration for edge, mobile, and extension profiles.
- `preprocessing/`: image normalization, batching, and frame-sampling logic aligned with backend preprocessing contracts.
- `runtimes/`: runtime wrappers for ONNX and TFLite with a shared output payload contract.
- `model_conversion/`: export, quantize, benchmark, and validate scripts for edge artifacts.
- `explainability/`: lightweight explainability outputs and explicit limitations.
- `tests/`: runtime and conversion validation tests.

## Runtime Contract
Each runtime wrapper exposes these methods:
- `load_model()`
- `preprocess_input(media_path)`
- `run_inference(model_input)`
- `postprocess_output(output)`
- `unload_model()`

Prediction payloads include:
- `predicted_label`
- `predicted_probability`
- `probabilities`
- `threshold`
- `model_source`
- `inference_time_ms`

## Conversion and Validation Flow
1. Export model to ONNX.
2. Convert ONNX to target runtime artifacts (TFLite/CoreML where supported).
3. Quantize artifact for edge footprint constraints.
4. Benchmark latency with representative media.
5. Validate probability agreement against reference outputs.

## Notes
- Local extension runtime can be optional; backend fallback path is expected when local runtime is unavailable.
- Keep preprocessing parameters synchronized with backend and training configs.
- Always evaluate deviation tolerance when replacing quantized artifacts.
