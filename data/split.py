"""Class balancing, split generation, and final validation module."""

from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from utils import (  # noqa: E402
    FAKE_LABEL,
    REAL_LABEL,
    ensure_required_structure,
    group_id_from_frame_path,
    load_config,
    setup_logger,
    summarize_distribution,
    validate_label_int,
    write_csv_rows,
)


def read_labels(labels_csv: Path) -> List[Dict[str, str]]:
    """Read labels.csv and return records as list of dictionaries."""
    if not labels_csv.exists():
        return []

    with labels_csv.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    return rows


def distribution_from_rows(rows: Sequence[Dict[str, str]]) -> Dict[int, int]:
    """Compute class counts from records."""
    distribution = {REAL_LABEL: 0, FAKE_LABEL: 0}
    for row in rows:
        try:
            label_value = int(row["label"])
        except Exception:
            continue
        if label_value in distribution:
            distribution[label_value] += 1
    return distribution


def balance_rows(rows: List[Dict[str, str]], method: str, seed: int) -> List[Dict[str, str]]:
    """Apply oversampling or undersampling to balance class counts."""
    if method == "none":
        return list(rows)

    grouped = {REAL_LABEL: [], FAKE_LABEL: []}
    for row in rows:
        try:
            label_value = int(row["label"])
        except Exception:
            continue
        if label_value in grouped:
            grouped[label_value].append(row)

    real_rows = grouped[REAL_LABEL]
    fake_rows = grouped[FAKE_LABEL]

    if not real_rows or not fake_rows:
        return list(rows)

    randomizer = random.Random(seed)

    if method == "undersample":
        target = min(len(real_rows), len(fake_rows))
        balanced = randomizer.sample(real_rows, target) + randomizer.sample(fake_rows, target)
        randomizer.shuffle(balanced)
        return balanced

    if method == "oversample":
        target = max(len(real_rows), len(fake_rows))
        real_extended = list(real_rows)
        fake_extended = list(fake_rows)

        while len(real_extended) < target:
            real_extended.append(randomizer.choice(real_rows))
        while len(fake_extended) < target:
            fake_extended.append(randomizer.choice(fake_rows))

        balanced = real_extended + fake_extended
        randomizer.shuffle(balanced)
        return balanced

    return list(rows)


def allocate_counts(total: int, train_ratio: float, val_ratio: float, test_ratio: float) -> Tuple[int, int, int]:
    """Allocate item counts according to split ratios while preserving totals."""
    if total <= 0:
        return (0, 0, 0)

    train_count = int(round(total * train_ratio))
    val_count = int(round(total * val_ratio))
    test_count = total - train_count - val_count

    # Repair rounding edge cases.
    if test_count < 0:
        test_count = 0
    while train_count + val_count + test_count < total:
        train_count += 1
    while train_count + val_count + test_count > total and train_count > 0:
        train_count -= 1

    return (train_count, val_count, test_count)


def stratified_group_split(
    rows: List[Dict[str, str]],
    train_ratio: float,
    val_ratio: float,
    test_ratio: float,
    seed: int,
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], List[Dict[str, str]]]:
    """Split records by group ID and label to prevent frame leakage across splits."""
    groups_by_label: Dict[int, List[str]] = {REAL_LABEL: [], FAKE_LABEL: []}
    group_label_map: Dict[str, int] = {}

    for row in rows:
        try:
            label = int(row["label"])
        except Exception:
            continue

        group_id = group_id_from_frame_path(row["filepath"])
        if group_id in group_label_map and group_label_map[group_id] != label:
            # If conflict exists, keep the first assignment to preserve deterministic behavior.
            continue

        group_label_map[group_id] = label

    for group_id, label in group_label_map.items():
        if label in groups_by_label:
            groups_by_label[label].append(group_id)

    randomizer = random.Random(seed)
    for label in groups_by_label:
        randomizer.shuffle(groups_by_label[label])

    train_groups = set()
    val_groups = set()
    test_groups = set()

    for label, groups in groups_by_label.items():
        n_train, n_val, n_test = allocate_counts(len(groups), train_ratio, val_ratio, test_ratio)
        train_slice = groups[:n_train]
        val_slice = groups[n_train : n_train + n_val]
        test_slice = groups[n_train + n_val : n_train + n_val + n_test]

        train_groups.update(train_slice)
        val_groups.update(val_slice)
        test_groups.update(test_slice)

    overlap = (train_groups & val_groups) | (train_groups & test_groups) | (val_groups & test_groups)
    if overlap:
        raise RuntimeError(f"Data leakage detected between splits. Overlapping groups: {len(overlap)}")

    train_rows = []
    val_rows = []
    test_rows = []

    for row in rows:
        group_id = group_id_from_frame_path(row["filepath"])
        if group_id in train_groups:
            train_rows.append(row)
        elif group_id in val_groups:
            val_rows.append(row)
        elif group_id in test_groups:
            test_rows.append(row)

    return train_rows, val_rows, test_rows


def to_csv_rows(rows: Sequence[Dict[str, str]]) -> List[Tuple[str, int, str]]:
    """Convert dictionaries to tuple rows with strict output columns."""
    formatted = []
    for row in rows:
        formatted.append((str(row["filepath"]), int(row["label"]), str(row["dataset"])))
    return formatted


def validate_rows(rows: Sequence[Dict[str, str]], dataset_root: Path) -> Tuple[int, int]:
    """Validate labels and file existence; return error and missing counts."""
    invalid_labels = 0
    missing_files = 0

    for row in rows:
        try:
            label = int(row["label"])
        except Exception:
            invalid_labels += 1
            continue

        if not validate_label_int(label):
            invalid_labels += 1

        file_path = dataset_root / row["filepath"]
        if not file_path.exists():
            missing_files += 1

    return invalid_labels, missing_files


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for balancing and split generation."""
    parser = argparse.ArgumentParser(description="Create train/val/test splits")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to config file")
    parser.add_argument(
        "--balance-method",
        type=str,
        default="",
        choices=["", "none", "oversample", "undersample"],
        help="Override balancing method from config",
    )
    parser.add_argument(
        "--balance-apply-to",
        type=str,
        default="",
        choices=["", "all", "train"],
        help="Override where balancing is applied",
    )
    return parser.parse_args()


def main() -> None:
    """Run balancing, split creation, and final validation workflow."""
    args = parse_args()
    config = load_config(args.config)
    ensure_required_structure(config)

    logger = setup_logger(Path(config["paths"]["logs"]["pipeline"]))
    logger.info("Starting split module")

    dataset_root = Path(config["paths"]["root"])
    labels_csv = Path(config["paths"]["metadata"]["labels"])
    train_csv = Path(config["paths"]["metadata"]["train"])
    val_csv = Path(config["paths"]["metadata"]["val"])
    test_csv = Path(config["paths"]["metadata"]["test"])

    rows = read_labels(labels_csv)
    if not rows:
        logger.warning("labels.csv is empty or missing: %s", labels_csv)
        print("labels.csv is empty or missing. Run labeling.py --action label first.")
        return

    split_cfg = config["split"]
    train_ratio = float(split_cfg.get("train", 0.7))
    val_ratio = float(split_cfg.get("val", 0.15))
    test_ratio = float(split_cfg.get("test", 0.15))
    seed = int(split_cfg.get("random_seed", 42))

    if abs((train_ratio + val_ratio + test_ratio) - 1.0) > 1e-6:
        raise ValueError("Split ratios must sum to 1.0")

    balancing_cfg = config.get("balancing", {})
    method = args.balance_method or balancing_cfg.get("method", "oversample")
    apply_to = args.balance_apply_to or balancing_cfg.get("apply_to", "train")

    before_distribution = distribution_from_rows(rows)
    logger.info("Class distribution before balancing: %s", summarize_distribution(before_distribution))
    print(f"Class distribution before balancing: {summarize_distribution(before_distribution)}")

    if apply_to == "all":
        rows = balance_rows(rows, method, seed)
        after_distribution = distribution_from_rows(rows)
        logger.info("Class distribution after balancing: %s", summarize_distribution(after_distribution))
        print(f"Class distribution after balancing: {summarize_distribution(after_distribution)}")

    train_rows, val_rows, test_rows = stratified_group_split(
        rows=rows,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        test_ratio=test_ratio,
        seed=seed,
    )

    if apply_to == "train":
        train_before = distribution_from_rows(train_rows)
        logger.info("Train distribution before balancing: %s", summarize_distribution(train_before))
        print(f"Train distribution before balancing: {summarize_distribution(train_before)}")
        train_rows = balance_rows(train_rows, method, seed)
        train_after = distribution_from_rows(train_rows)
        logger.info("Train distribution after balancing: %s", summarize_distribution(train_after))
        print(f"Train distribution after balancing: {summarize_distribution(train_after)}")

    write_csv_rows(train_csv, ["filepath", "label", "dataset"], to_csv_rows(train_rows))
    write_csv_rows(val_csv, ["filepath", "label", "dataset"], to_csv_rows(val_rows))
    write_csv_rows(test_csv, ["filepath", "label", "dataset"], to_csv_rows(test_rows))
    logger.info("Wrote split CSV files: train=%s val=%s test=%s", train_csv, val_csv, test_csv)

    invalid_labels, missing_files = validate_rows(rows, dataset_root)

    total_real = distribution_from_rows(rows).get(REAL_LABEL, 0)
    total_fake = distribution_from_rows(rows).get(FAKE_LABEL, 0)

    print(f"Total Real: {total_real}")
    print(f"Total Fake: {total_fake}")
    print(f"Train: {len(train_rows)}")
    print(f"Val: {len(val_rows)}")
    print(f"Test: {len(test_rows)}")
    print(f"Invalid Labels: {invalid_labels}")
    print(f"Missing Files: {missing_files}")

    logger.info(
        "Final summary | total_real=%d total_fake=%d train=%d val=%d test=%d invalid_labels=%d missing_files=%d",
        total_real,
        total_fake,
        len(train_rows),
        len(val_rows),
        len(test_rows),
        invalid_labels,
        missing_files,
    )
    logger.info("Completed split module")


if __name__ == "__main__":
    main()
