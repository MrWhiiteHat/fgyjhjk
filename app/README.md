# Module 5: Backend API + Frontend Integration + Deployment Interface

This `app/` workspace contains the serving and product-integration layer built on top of Module 4 inference and explainability components.

## Structure

- `backend/`: FastAPI service, middleware, route handlers, schemas, business services, tests
- `frontend/`: Next.js dashboard for health, predictions, explainability, and report retrieval
- `deployment/`: Docker, Compose, Nginx, Prometheus, and Kubernetes deployment manifests

## Backend

### Run locally

```bash
python -m pip install -r app/backend/requirements.txt
uvicorn app.backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### API docs

- Swagger UI: `http://localhost:8000/docs`
- OpenAPI: `http://localhost:8000/openapi.json`

### Key routes

- `GET /api/v1/health`
- `POST /api/v1/predict/image`
- `POST /api/v1/predict/video`
- `POST /api/v1/predict/folder`
- `POST /api/v1/explain/image`
- `GET /api/v1/reports/{report_id}`
- `GET /api/v1/admin/model-info`
- `POST /api/v1/admin/reload-model`
- `GET /api/v1/admin/metrics`

### Backend tests

```bash
pytest app/backend/tests -q
```

## Frontend

### Run locally

```bash
cd app/frontend
npm install
cp .env.local.example .env.local
npm run dev
```

The dashboard runs at `http://localhost:3000` and calls backend endpoints via `NEXT_PUBLIC_API_BASE_URL`.

## Deployment

See `deployment/README_DEPLOY.md` for full Docker Compose and Kubernetes instructions.

## Integration Notes

- Backend reuses Module 4 predictor, preprocessing adapter, explainability runner, and video inference runtime.
- Cache keys include file hash + model version + threshold.
- Reports are indexed in backend outputs for retrieval by report ID.
- Webcam endpoint is intentionally a server-side stub and must be implemented on the client side.
