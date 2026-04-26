# Deployment Guide

This folder contains backend/frontend container runtime artifacts, reverse-proxy configuration, and Kubernetes manifests.

## Included Files

- `Dockerfile.backend`: FastAPI backend image with Gunicorn+Uvicorn worker startup.
- `Dockerfile.frontend`: Next.js frontend build/runtime image.
- `docker-compose.yml`: Local production-like stack wiring backend, frontend, nginx, and Prometheus.
- `nginx.conf`: Reverse-proxy config routing `/api` to backend and `/` to frontend.
- `gunicorn_conf.py`: Worker, bind, timeout, and logging settings.
- `prometheus.yml`: Prometheus scrape config.
- `k8s/*.yaml`: Deployment/service/ingress/config manifests.

## Local Container Run

Run from `app/deployment`:

```bash
docker compose up --build
```

## Environment Variable Injection

- Backend service reads `app/backend/.env` through `env_file` and supports explicit overrides in compose.
- Frontend service reads `NEXT_PUBLIC_API_BASE_URL` from compose environment.
- Kubernetes backend/frontend deployments read config from `k8s/configmap.yaml`.
- Optional API key is injected via `k8s/secret.example.yaml` -> `API_KEY` env var.

## Volume Mounts

`docker-compose.yml` mounts:

- `training/outputs` (read-only) for model artifact availability.
- `evaluation/outputs` for generated evaluation outputs.
- `app/backend/outputs` for reports/logs persistence.
- `app/backend/tmp` for upload lifecycle isolation.

## Healthcheck Support

Compose services define healthchecks:

- Backend: `GET /api/v1/health`
- Frontend: `GET /`
- Nginx: `GET /`
- Prometheus: `GET /-/healthy`

Dependency startup order uses `depends_on` with `service_healthy` conditions.

## Production Startup Commands

Backend image startup command:

```bash
gunicorn -k uvicorn.workers.UvicornWorker -c app/deployment/gunicorn_conf.py app.backend.main:app
```

Frontend image startup command:

```bash
npm run start
```

## Kubernetes Apply Flow

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.example.yaml
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/backend-service.yaml
kubectl apply -f k8s/frontend-deployment.yaml
kubectl apply -f k8s/frontend-service.yaml
kubectl apply -f k8s/ingress.yaml
```

## Notes

- Replace image names in deployment manifests with your registry tags.
- Configure TLS and strict CORS for internet-facing production environments.
- Keep `SAVE_UPLOADS=false` unless retention is required and approved.
