"""Generate model card markdown from template and registry metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ops.mlops.model_registry import ModelRegistry


def _render_card(template_text: str, metadata: dict) -> str:
    lines = template_text.splitlines()
    rendered = []
    for line in lines:
        rendered.append(line)

    rendered.append("")
    rendered.append("## Auto-Populated Metadata")
    rendered.append(f"- Model name: {metadata.get('model_name', '')}")
    rendered.append(f"- Model version: {metadata.get('model_version', '')}")
    rendered.append(f"- Artifact path: {metadata.get('artifact_path', '')}")
    rendered.append(f"- Checkpoint hash: {metadata.get('checkpoint_hash', '')}")
    rendered.append(f"- Stage: {metadata.get('promoted_stage', '')}")
    rendered.append(f"- Created at: {metadata.get('created_at', '')}")
    rendered.append("")
    rendered.append("### Validation Metrics")
    rendered.append("```json")
    rendered.append(json.dumps(metadata.get("validation_metrics", {}), indent=2, sort_keys=True))
    rendered.append("```")
    rendered.append("")
    rendered.append("### Test Metrics")
    rendered.append("```json")
    rendered.append(json.dumps(metadata.get("test_metrics", {}), indent=2, sort_keys=True))
    rendered.append("```")

    return "\n".join(rendered) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate model card from registry metadata")
    parser.add_argument("--model-version", required=True, type=str)
    parser.add_argument("--template", default="ops/governance/model_card_template.md", type=str)
    parser.add_argument("--output", default="ops/reports/model_card.md", type=str)
    args = parser.parse_args()

    registry = ModelRegistry()
    metadata_obj = registry.get_model(args.model_version)
    if metadata_obj is None:
        raise SystemExit(f"Model version not found: {args.model_version}")

    metadata = metadata_obj.to_dict()
    template_path = Path(args.template)
    if not template_path.exists():
        raise SystemExit(f"Template not found: {template_path}")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    card_text = _render_card(template_path.read_text(encoding="utf-8"), metadata)
    output_path.write_text(card_text, encoding="utf-8")

    print(json.dumps({"output": str(output_path.as_posix()), "model_version": args.model_version}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
