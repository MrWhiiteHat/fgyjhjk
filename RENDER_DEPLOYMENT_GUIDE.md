# 🚀 Render Deployment Guide

This guide will help you deploy the entire **RealFake Detection Platform** to [Render](https://render.com) using the included Blueprint (`render.yaml`).

Render's Blueprint feature allows you to define your infrastructure as code. With our updated `render.yaml`, both the FastAPI Backend and the Next.js Frontend will be deployed automatically in their own Docker containers.

## 📋 Prerequisites
1. A [GitHub](https://github.com) account.
2. A [Render](https://render.com) account.
3. Your code successfully pushed to your GitHub repository.

---

## 🛠️ Deployment Steps

### Step 1: Connect your GitHub Account
1. Log in to your [Render Dashboard](https://dashboard.render.com/).
2. If this is your first time, you may need to connect your GitHub account.

### Step 2: Use the Blueprint
1. In the Render Dashboard, click the **"New +"** button in the top right corner.
2. Select **"Blueprint"** from the dropdown menu.
3. You will see a list of your GitHub repositories. Connect and select the `realfake-detection` repository.
4. Render will automatically detect the `render.yaml` file in the root directory.

### Step 3: Configure the Services
1. You will be presented with a summary of the services about to be deployed:
   - **`realfake-backend`** (Web Service, FastAPI + Docker)
   - **`realfake-frontend`** (Web Service, Next.js + Docker)
2. Enter a **Service Group Name** (e.g., `realfake-platform`).
3. Click **"Apply"** at the bottom of the page.

### Step 4: Wait for the Build
Render will now begin building the Docker images for both the frontend and the backend simultaneously. 
- You can click into each service to view the live build logs.
- *Note: Since the backend requires ML libraries like PyTorch, the backend build may take 3-5 minutes.*

### Step 5: Verify Deployment
Once the deployment succeeds (indicated by a green "Live" status):
1. **Frontend:** Navigate to the provided Render URL for `realfake-frontend` (e.g., `https://realfake-frontend.onrender.com`).
2. **Backend:** The backend will be live at its respective URL. The frontend is already pre-configured to communicate with the backend via the `NEXT_PUBLIC_API_URL` environment variable defined in the `render.yaml`.

---

## 🔧 Environment Variables (Already Handled)
The `render.yaml` handles the crucial environment variables automatically:

**Backend:**
- `APP_ENV`: production
- `CORS_ORIGINS`: `https://realfake-frontend.onrender.com` (Ensure this matches the frontend's assigned Render URL if you change the service name!)

**Frontend:**
- `NEXT_PUBLIC_API_URL`: `https://realfake-backend.onrender.com`

If you change the names of your services in Render, **you MUST update the URLs** in the `render.yaml` or directly in the Environment settings of your Render dashboard!

---

## 💡 Troubleshooting
- **Frontend can't talk to backend:** Check the browser console. If there's a CORS error, verify that the `CORS_ORIGINS` in the backend's environment variables exactly matches the frontend's Render URL (no trailing slash).
- **Out of Memory (OOM) Errors:** The backend uses PyTorch. If the Render Free tier runs out of memory, you may need to upgrade the backend to a paid tier (Starter/Standard) with more RAM, or set `MODEL_PRELOAD_ON_STARTUP` to `false` in the dashboard.
