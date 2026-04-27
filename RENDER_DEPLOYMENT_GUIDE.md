# 🚀 Render Deployment Guide

This guide covers deploying the **RealFake Detection Platform** (Backend and Frontend) to [Render](https://render.com) using the included Blueprint (`render.yaml`). 

By deploying with Render Blueprint, you define your infrastructure as code. Render will automatically provision both your FastAPI backend and Next.js frontend, hook them up with CI/CD, and link their environments.

---

## 📋 Prerequisites

1. A [GitHub](https://github.com) account with the RealFake Detection repository pushed.
2. A [Render](https://render.com) account (you can sign up with your GitHub account).
3. The project code pushed to your GitHub repository (Render pulls directly from your repo).

---

## 🛠️ Step-by-Step Deployment

### 1. Verify `render.yaml`
Ensure the `render.yaml` file exists in the root of your repository. It should look like this:

```yaml
services:
  # Backend FastAPI Service
  - type: web
    name: realfake-backend
    runtime: docker
    dockerfilePath: app/deployment/Dockerfile.backend
    dockerContext: .
    plan: starter
    autoDeploy: true
    healthCheckPath: /api/v1/health
    envVars:
      - key: APP_ENV
        value: production
      - key: APP_HOST
        value: 0.0.0.0
      - key: APP_PORT
        value: 8000
      - key: MODEL_PRELOAD_ON_STARTUP
        value: "true"
      - key: ENABLE_CORS
        value: "true"
      - key: CORS_ORIGINS
        value: "*"

  # Frontend Next.js Service
  - type: web
    name: realfake-frontend
    runtime: docker
    dockerfilePath: app/deployment/Dockerfile.frontend
    dockerContext: .
    plan: starter
    autoDeploy: true
    envVars:
      - key: NEXT_PUBLIC_API_URL
        fromService:
          type: web
          name: realfake-backend
          property: url
```

*Note: The `NEXT_PUBLIC_API_URL` environment variable allows the frontend to automatically resolve the backend URL without hardcoding.*

### 2. Connect Your Repository to Render

1. Go to your [Render Dashboard](https://dashboard.render.com).
2. Click **New +** and select **Blueprint**.
3. Connect your GitHub account (if not already connected) and give Render permission to read the `realfake-detection` repository.
4. Select the `realfake-detection` repository from the list.

### 3. Deploy the Blueprint

1. After selecting the repository, Render will automatically detect the `render.yaml` file in the root directory.
2. Give your blueprint a service group name (e.g., `realfake-platform`).
3. Click **Apply**.
4. Render will now automatically spin up two Web Services:
   - `realfake-backend`
   - `realfake-frontend`

### 4. Monitor the Build
- Navigate to the **Dashboard** and you will see the build process in action.
- The build process will use the `Dockerfile.backend` and `Dockerfile.frontend` located in the `app/deployment/` directory.
- This might take 5-10 minutes on the first deployment as Render downloads and caches the necessary dependencies (Node.js modules, Python PIP packages, etc.).

---

## ⚙️ Post-Deployment Configuration

Once the deployment finishes and the status turns **Live** (✅), perform the following checks:

### 1. CORS Configuration (Important)
By default, the `render.yaml` file sets `CORS_ORIGINS` to `*` to ensure successful communication out-of-the-box. 
For a production environment, you should lock this down:
1. Go to the `realfake-backend` service in your Render Dashboard.
2. Navigate to the **Environment** tab.
3. Update the `CORS_ORIGINS` value to your frontend's actual Render URL (e.g., `https://realfake-frontend-abc.onrender.com`).
4. Click **Save Changes** (Render will automatically redeploy the backend).

### 2. Verify Next.js Frontend
Go to the URL provided by Render for your `realfake-frontend` service. Ensure that:
- The dashboard loads successfully.
- Logging in / Signing up works (testing the API connection to the backend).
- Uploading an image returns a successful prediction.

---

## 📦 Troubleshooting / Common Issues

- **Build Failing (Out of Memory):** Machine Learning dependencies (like PyTorch) can be large. If the backend build fails due to OOM errors on the Free tier, consider upgrading the `realfake-backend` plan from `starter` to a slightly higher tier (e.g., `Standard`) inside the Render Dashboard.
- **API Requests Failing (CORS):** If your frontend gets CORS errors in the browser console, double-check that your `CORS_ORIGINS` on the backend matches the exact URL of the frontend (no trailing slash).
- **Environment Variables Sync:** Remember that any variables prefixed with `NEXT_PUBLIC_` are baked into the frontend image at build time. If the backend URL changes, you must trigger a Manual Deploy for the frontend so it rebuilds with the new environment variables.

---
**Enjoy your newly deployed RealFake Detection Platform!** 🎉
