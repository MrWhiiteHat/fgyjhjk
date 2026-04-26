"""Register a model version into the MLOps registry."""

from __future__ import annotations

import argparse
import json

from ops.mlops.experiment_sync import ExperimentSync


def main() -> int:
    parser = argparse.ArgumentParser(description="Register model metadata from training outputs")
    parser.add_argument("--model-name", required=True, type=str)
    parser.add_argument("--model-version", required=True, type=str)
    parser.add_argument("--artifact-path", required=True, type=str)
    parser.add_argument("--dataset-name", default="unknown_dataset", type=str)
    parser.add_argument("--notes", default="registered via CLI", type=str)
    parser.add_argument("--allow-overwrite", action="store_true")
    args = parser.parse_args()

    syncer = ExperimentSync()
    result = syncer.sync_from_outputs(
        model_name=args.model_name,
        model_version=args.model_version,
        artifact_path=args.artifact_path,
        dataset_name=args.dataset_name,
        notes=args.notes,
        allow_overwrite=args.allow_overwrite,
    )

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
