# Technical Reference & API Documentation

This document contains detailed technical information, API contracts, and internal system configurations for the RealFake Detection Platform.

## Backend setup

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r app/backend/requirements.txt
```

## Frontend setup

```bash
cd app/frontend
npm install
```

## Backend Run Instructions

```bash
uvicorn app.backend.main:app --host 0.0.0.0 --port 8000
```

Backend base URL: `http://localhost:8000/api/v1`

## Frontend Run Instructions

```bash
cd app/frontend
npm run dev
```

Frontend base URL: `http://localhost:3000`

## Docker Run Instructions

```bash
cd app/deployment
docker compose up --build
```

Services:
- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- Nginx gateway: `http://localhost`
- Prometheus: `http://localhost:9090`

## Environment Configuration

- `app/backend/.env.example`
- `app/frontend/.env.local.example`

### Important backend variables:
- `MODEL_ARTIFACT_PATH`
- `MODEL_TYPE`
- `DEFAULT_THRESHOLD`
- `ENABLE_EXPLAINABILITY`
- `ENABLE_RATE_LIMIT`
- `TEMP_CLEANUP_ENABLED`
- `TEMP_MAX_AGE_SECONDS`

## API Usage Examples

### 1) Image prediction request
```bash
curl -X POST "http://localhost:8000/api/v1/predict/image" \
   -F "file=@sample.jpg" \
   -F "threshold=0.5" \
   -F "explain=true" \
   -F "generate_report=true"
```

### 2) Video prediction request
```bash
curl -X POST "http://localhost:8000/api/v1/predict/video" \
   -F "file=@sample.mp4" \
   -F "threshold=0.5" \
   -F "frame_stride=2" \
   -F "max_frames=120" \
   -F "aggregation_strategy=mean_probability"
```

## JSON Contract

All successful API responses follow:
```json
{
   "success": true,
   "request_id": "uuid",
   "timestamp": "2026-04-17T10:15:30.000000+00:00",
   "message": "...",
   "data": {},
   "errors": []
}
```

## Output and Report Paths

- Temporary uploads: `app/backend/tmp`
- Runtime outputs: `app/backend/outputs`
- Reports: `app/backend/outputs/reports/<report_id>/`
- Backend logs: `app/backend/outputs/logs`

## Test Instructions

```bash
python -m pytest app/backend/tests -q
python -m pytest edge/on_device/tests edge/tests -q
```
