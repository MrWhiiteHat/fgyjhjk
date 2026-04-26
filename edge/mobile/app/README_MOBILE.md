# Mobile Edge App (React Native / Expo)

## Overview
This app provides local-first Real vs Fake media detection with backend fallback and offline sync.

## Core Flows
- Image detection
- Video frame-sampled detection
- Camera frame/burst detection
- Local history + sync status
- Optional explainability view

## Inference Modes
- `local`: force on-device runtime
- `backend`: force backend API inference
- `auto`: prefer local runtime, fallback to backend

## Setup
1. Install dependencies in `edge/mobile/app`.
2. Configure `.env` from `.env.example`.
3. Place edge model artifact in `src/assets/models/`.
4. Run `npm run start`.

## Notes
- Local inference runtime availability depends on native package integration and model compatibility.
- If local runtime is unavailable, app falls back to backend when allowed by settings.
- Privacy mode `strict_local` prevents sync and backend explainability upload.
