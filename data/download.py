"""Dataset download module for deepfake data pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Iterable, List
from urllib.parse import urlparse

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from utils import (  # noqa: E402
    build_auth_headers,
    download_file_with_resume,
    ensure_required_structure,
    extract_archives_in_directory,
    load_config,
    run_command,
    sanitize_name,
    setup_logger,
)


def resolve_filename_from_url(url: str, fallback_prefix: str, index: int) -> str:
    """Resolve a deterministic filename from a URL."""
    parsed = urlparse(url)
    tail = Path(parsed.path).name
    if tail:
        return tail
    return f"{sanitize_name(fallback_prefix)}_{index}.bin"


def download_direct_urls(
    urls: Iterable[str],
    output_dir: Path,
    auth_cfg: Dict,
    chunk_size_mb: int,
    timeout_sec: int,
    retries: int,
    dataset_name: str,
    logger,
) -> None:
    """Download direct links with resume support and optional auth headers."""
    headers = build_auth_headers(auth_cfg)
    chunk_size = max(1, int(chunk_size_mb)) * 1024 * 1024

    for idx, url in enumerate(urls, start=1):
        try:
            filename = resolve_filename_from_url(url, dataset_name, idx)
            destination = output_dir / filename
            logger.info("Downloading %s file %d: %s", dataset_name, idx, url)
            download_file_with_resume(
                url=url,
                destination=destination,
                headers=headers,
                chunk_size=chunk_size,
                timeout=timeout_sec,
                retries=retries,
            )
            logger.info("Downloaded file to %s", destination)
        except Exception as exc:
            logger.error("Failed direct download for %s (%s): %s", dataset_name, url, exc)


def download_with_kaggle_dataset(dataset_id: str, output_dir: Path, logger) -> bool:
    """Download a Kaggle dataset archive and unzip it in place."""
    command = [
        "kaggle",
        "datasets",
        "download",
        "-d",
        dataset_id,
        "-p",
        str(output_dir),
        "--unzip",
    ]
    return run_command(command, logger) == 0


def download_with_kaggle_competition(competition_id: str, output_dir: Path, logger) -> bool:
    """Download Kaggle competition files for DFDC."""
    command = [
        "kaggle",
        "competitions",
        "download",
        "-c",
        competition_id,
        "-p",
        str(output_dir),
    ]
    return run_command(command, logger) == 0


def download_faceforensics(config: Dict, logger) -> None:
    """Download FaceForensics++ data using configured method."""
    dataset_cfg = config["download"]["datasets"]["faceforensics"]
    output_dir = Path(config["paths"]["raw"]["faceforensics"])
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("FaceForensics++ format: original_sequences=REAL, manipulated_sequences=FAKE")
    logger.info(
        "FaceForensics++ access docs: %s",
        dataset_cfg.get("docs_url", "https://github.com/ondyari/FaceForensics"),
    )

    urls = dataset_cfg.get("urls", []) or []
    if urls:
        download_direct_urls(
            urls=urls,
            output_dir=output_dir,
            auth_cfg=dataset_cfg.get("auth", {}),
            chunk_size_mb=config["download"].get("chunk_size_mb", 8),
            timeout_sec=config["download"].get("timeout_sec", 60),
            retries=config["download"].get("retries", 3),
            dataset_name="faceforensics",
            logger=logger,
        )
        extract_archives_in_directory(output_dir, logger)
        return

    logger.warning(
        "No direct URLs provided for FaceForensics++. "
        "Set download.datasets.faceforensics.urls in config.yaml after approval."
    )


def download_celebdf(config: Dict, logger) -> None:
    """Download Celeb-DF v2 using Kaggle or direct URLs."""
    dataset_cfg = config["download"]["datasets"]["celebdf"]
    output_dir = Path(config["paths"]["raw"]["celebdf"])
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Celeb-DF format: Celeb-real/YouTube-real=REAL, Celeb-synthesis=FAKE")
    logger.info(
        "Celeb-DF docs: %s",
        dataset_cfg.get("docs_url", "https://github.com/yuezunli/celeb-deepfakeforensics"),
    )

    kaggle_dataset = dataset_cfg.get("kaggle", {}).get("dataset", "")
    if kaggle_dataset:
        logger.info("Attempting Kaggle dataset download for Celeb-DF: %s", kaggle_dataset)
        if download_with_kaggle_dataset(kaggle_dataset, output_dir, logger):
            extract_archives_in_directory(output_dir, logger)
            return
        logger.warning("Kaggle dataset download failed for Celeb-DF. Falling back to direct URLs if provided.")

    urls = dataset_cfg.get("urls", []) or []
    if urls:
        download_direct_urls(
            urls=urls,
            output_dir=output_dir,
            auth_cfg=dataset_cfg.get("auth", {}),
            chunk_size_mb=config["download"].get("chunk_size_mb", 8),
            timeout_sec=config["download"].get("timeout_sec", 60),
            retries=config["download"].get("retries", 3),
            dataset_name="celebdf",
            logger=logger,
        )
        extract_archives_in_directory(output_dir, logger)
    else:
        logger.warning("No Celeb-DF source configured. Provide kaggle.dataset or direct urls in config.yaml.")


def download_dfdc(config: Dict, logger) -> None:
    """Download DFDC using Kaggle competition API or direct URLs."""
    dataset_cfg = config["download"]["datasets"]["dfdc"]
    output_dir = Path(config["paths"]["raw"]["dfdc"])
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("DFDC format: each part contains metadata.json with REAL/FAKE labels")
    logger.info(
        "DFDC docs: %s",
        dataset_cfg.get("docs_url", "https://www.kaggle.com/c/deepfake-detection-challenge"),
    )

    competition_id = dataset_cfg.get("kaggle", {}).get("competition", "")
    if competition_id:
        logger.info("Attempting Kaggle competition download for DFDC: %s", competition_id)
        if download_with_kaggle_competition(competition_id, output_dir, logger):
            extract_archives_in_directory(output_dir, logger)
            return
        logger.warning("Kaggle competition download failed for DFDC. Falling back to direct URLs if provided.")

    urls = dataset_cfg.get("urls", []) or []
    if urls:
        download_direct_urls(
            urls=urls,
            output_dir=output_dir,
            auth_cfg=dataset_cfg.get("auth", {}),
            chunk_size_mb=config["download"].get("chunk_size_mb", 8),
            timeout_sec=config["download"].get("timeout_sec", 60),
            retries=config["download"].get("retries", 3),
            dataset_name="dfdc",
            logger=logger,
        )
        extract_archives_in_directory(output_dir, logger)
    else:
        logger.warning("No DFDC source configured. Provide kaggle.competition or direct urls in config.yaml.")


def handle_custom_dataset(config: Dict, logger) -> None:
    """Validate that custom dataset folder exists for user uploads."""
    custom_dir = Path(config["paths"]["raw"]["custom"])
    custom_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Custom dataset support enabled. Place files under %s", custom_dir)
    logger.info("Recommended structure: custom/real/* and custom/fake/*")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for dataset selection."""
    parser = argparse.ArgumentParser(description="Download deepfake datasets")
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to configuration file",
    )
    parser.add_argument(
        "--datasets",
        nargs="+",
        default=["all"],
        choices=["all", "faceforensics", "celebdf", "dfdc", "custom"],
        help="Datasets to download",
    )
    return parser.parse_args()


def main() -> None:
    """Run dataset download workflow."""
    args = parse_args()
    config = load_config(args.config)
    ensure_required_structure(config)

    logger = setup_logger(Path(config["paths"]["logs"]["pipeline"]))
    logger.info("Starting data download module")

    requested = set(args.datasets)
    if "all" in requested:
        requested = {"faceforensics", "celebdf", "dfdc", "custom"}

    if "faceforensics" in requested:
        download_faceforensics(config, logger)
    if "celebdf" in requested:
        download_celebdf(config, logger)
    if "dfdc" in requested:
        download_dfdc(config, logger)
    if "custom" in requested:
        handle_custom_dataset(config, logger)

    logger.info("Completed data download module")


if __name__ == "__main__":
    main()
