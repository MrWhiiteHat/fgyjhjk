# Dataset Download and Format Guide

## 1) FaceForensics++
- Official access request + docs: https://github.com/ondyari/FaceForensics
- Download method in this pipeline:
  - Preferred: set direct approved URLs in `config.yaml` under `download.datasets.faceforensics.urls`.
  - Auth: set `download.datasets.faceforensics.auth` (`none`, `bearer`, `basic`, or custom header).
  - Command: `python data/download.py --datasets faceforensics`
- Expected format (raw):
  - `original_sequences/*` => REAL
  - `manipulated_sequences/*` => FAKE
- Extraction handling:
  - Archives are auto-extracted in place.
  - Media are organized into `dataset/processed/{real,fake}` by `data/labeling.py`.

## 2) Celeb-DF (V2)
- Official docs: https://github.com/yuezunli/celeb-deepfakeforensics
- Download method in this pipeline:
  - Preferred: Kaggle API configured as `download.datasets.celebdf.kaggle.dataset`.
  - Alternative: set direct URLs in `download.datasets.celebdf.urls`.
  - Command: `python data/download.py --datasets celebdf`
- Expected format (raw):
  - `Celeb-real/*` => REAL
  - `YouTube-real/*` => REAL
  - `Celeb-synthesis/*` => FAKE
- Extraction handling:
  - Zip archives auto-extracted.
  - Files labeled by folder semantics in `data/labeling.py`.

## 3) DFDC (DeepFake Detection Challenge)
- Official challenge page/API: https://www.kaggle.com/c/deepfake-detection-challenge
- Download method in this pipeline:
  - Preferred: Kaggle competition API using `download.datasets.dfdc.kaggle.competition`.
  - Alternative: set direct URLs in `download.datasets.dfdc.urls`.
  - Command: `python data/download.py --datasets dfdc`
- Expected format (raw):
  - Part folders each containing video files and `metadata.json`.
  - `metadata.json` field `label` is `REAL` or `FAKE`.
- Extraction handling:
  - Competition archives auto-extracted.
  - Labels are read from metadata.json; fallback path-based labeling used when metadata missing.

## 4) Custom Dataset Support
- Place user-uploaded data in `dataset/raw/custom/`.
- Supported options:
  - Folder labels:
    - `dataset/raw/custom/real/*`
    - `dataset/raw/custom/fake/*`
  - CSV labels:
    - `dataset/raw/custom/labels.csv` with columns `filepath,label`
    - Label accepts `real/fake`, `0/1`, `r/f`
- Command: `python data/labeling.py --action organize`
- Supported files:
  - Videos: `.mp4`, `.avi`, `.mov`, `.mkv`, `.webm`
  - Images: `.jpg`, `.jpeg`, `.png`, `.bmp`, `.webp`

## Resume and Large Files
- Direct HTTP downloads use range-based resume (`.part` temporary files).
- Chunk size, timeout, and retries are configurable in `config.yaml`.
- Kaggle downloads require local Kaggle auth (`~/.kaggle/kaggle.json`) and are handled by the Kaggle CLI.
