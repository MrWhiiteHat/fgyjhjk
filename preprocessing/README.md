# Module 2: Preprocessing Layer

This module transforms Module 1 frame/video/image samples into aligned, normalized, de-duplicated face tensors for training and inference.

## Strict output structure implemented

- dataset/preprocessed/train/real
- dataset/preprocessed/train/fake
- dataset/preprocessed/val/real
- dataset/preprocessed/val/fake
- dataset/preprocessed/test/real
- dataset/preprocessed/test/fake
- dataset/face_crops/real
- dataset/face_crops/fake
- dataset/face_landmarks/real
- dataset/face_landmarks/fake
- dataset/rejected/blurry
- dataset/rejected/no_face
- dataset/rejected/multi_face
- dataset/rejected/corrupted
- dataset/rejected/duplicates
- dataset/metadata/preprocessed_labels.csv
- dataset/metadata/preprocessing_report.csv
- dataset/metadata/rejected_samples.csv

## Mandatory Module 2 files

- preprocessing/config.yaml
- preprocessing/utils.py
- preprocessing/detect_faces.py
- preprocessing/align_faces.py
- preprocessing/quality_checks.py
- preprocessing/normalize.py
- preprocessing/deduplicate.py
- preprocessing/build_preprocessed_dataset.py

## Configuration system

All preprocessing behavior is controlled by preprocessing/config.yaml.

Mandatory fields included:
- input_frames_dir
- labels_csv_path
- output_face_crops_dir
- output_preprocessed_dir
- output_landmarks_dir
- rejected_dir
- image_size
- face_detector
- confidence_threshold
- min_face_size
- max_faces_allowed
- blur_threshold
- brightness_min
- brightness_max
- duplicate_hash_threshold
- normalization_mean
- normalization_std
- num_workers
- save_landmarks
- save_debug_images

Additional fields included:
- train_csv_path
- val_csv_path
- test_csv_path
- preprocessed_labels_csv_path
- preprocessing_report_csv_path
- rejected_samples_csv_path
- log_file_path
- fallback_detector
- face_crop_margin_ratio
- allowed_image_extensions
- allowed_video_extensions
- random_seed
- use_fp16_storage

## Pipeline logic

### 1) Input loading
- Reads split metadata from:
  - dataset/metadata/train.csv
  - dataset/metadata/val.csv
  - dataset/metadata/test.csv
- Uses filepath,label,dataset rows from Module 1.

### 2) Face detection
- Primary: RetinaFace.
- Optional fallback: MTCNN.
- Safety fallback when deep detector packages are unavailable: OpenCV Haar cascade.
- Returns and records:
  - bbox
  - confidence
  - landmarks (when detector provides them)
  - detector backend used
- Detections below confidence threshold are discarded.
- Rejection rules:
  - 0 detections => no_face
  - detections > max_faces_allowed => multi_face
  - best face smaller than min_face_size => no_face

### 3) Face cropping and alignment
- Crops bbox with margin ratio.
- If landmarks are available:
  - Applies eye+nose affine alignment to canonical geometry.
- If landmarks are unavailable:
  - Falls back to crop + resize.

### 4) Resize and normalization
- Aligned face is resized to configured image_size.
- Converts BGR to RGB.
- Applies channel-wise normalization using normalization_mean and normalization_std.
- Saves normalized tensor as .npy in split/class output directories.

### 5) Quality filtering
- Computes blur score via Laplacian variance.
- Computes brightness score via grayscale mean.
- Rejects samples when:
  - blur score < blur_threshold
  - brightness out of [brightness_min, brightness_max]
- Quality metrics are logged and written into report CSV.

### 6) Corruption handling
- Handles missing files.
- Handles unsupported formats.
- Handles decode failures.
- Handles empty crops and invalid media reads.
- Rejected corrupted samples are copied to dataset/rejected/corrupted.

### 7) Deduplication
- Computes 64-bit pHash on aligned face.
- Uses Hamming distance threshold duplicate_hash_threshold.
- Rejects near-duplicates to dataset/rejected/duplicates.
- Stores hash value and nearest duplicate info in reports.

### 8) Outputs and metadata updates
- Accepted samples produce:
  - face crop image in dataset/face_crops/{real,fake}
  - optional landmarks JSON in dataset/face_landmarks/{real,fake}
  - normalized tensor in dataset/preprocessed/{split}/{real,fake}
  - optional debug aligned image in dataset/preprocessed/{split}/{real,fake}
- Metadata files generated:
  - dataset/metadata/preprocessed_labels.csv
  - dataset/metadata/preprocessing_report.csv
  - dataset/metadata/rejected_samples.csv

## CSV schemas

### dataset/metadata/preprocessed_labels.csv
Columns:
- sample_id
- source_filepath
- split
- label
- dataset
- face_crop_path
- landmarks_path
- preprocessed_path
- detector
- confidence
- bbox
- face_hash
- width
- height

### dataset/metadata/preprocessing_report.csv
Columns:
- sample_id
- source_filepath
- split
- label
- dataset
- status
- rejection_reason
- detector
- confidence
- num_faces
- bbox
- landmarks
- blur_score
- brightness
- face_hash
- processing_ms
- notes

### dataset/metadata/rejected_samples.csv
Columns:
- sample_id
- source_filepath
- split
- label
- dataset
- rejection_reason
- rejected_path
- notes

## Logging

- Runtime log file:
  - dataset/logs/preprocessing_pipeline.log
- Log coverage includes:
  - run start/end
  - per-sample accept/reject
  - rejection reason
  - split/class counts
  - rejection-reason distribution

## Commands

### Install base dependencies
- pip install -r requirements.txt

### Install optional deep detectors
- pip install -r preprocessing/requirements_optional.txt

### Run preprocessing pipeline
- python preprocessing/build_preprocessed_dataset.py --config preprocessing/config.yaml

## Validation checklist

1. Required output directories exist.
2. Metadata CSVs exist and have headers.
3. All rejected samples are copied under reason-mapped rejected folders.
4. Accepted samples (if any) have:
   - crop image
   - normalized tensor
   - optional landmarks JSON
5. preprocessing_report.csv row count equals input sample count.
6. preprocessed_labels.csv + rejected_samples.csv row counts sum to input sample count.
