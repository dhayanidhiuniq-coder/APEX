# APEX

APEX - Private per-user AI workspace application.

## Story 1.1: Monorepo Architecture

This is a minimal monorepo with:

- **Frontend**: Next.js 16 with TypeScript, App Router, and Tailwind CSS (http://localhost:3000)
- **Backend**: FastAPI with uvicorn (http://localhost:8000)

## Prerequisites

- Node.js 24.21.0
- npm 11.19.0
- Python 3.14.7
- uv 0.12.23
- Git 2.56.0

## Installation

### Install root dependencies

```bash
npm install
```

### Setup backend

```bash
cd backend
uv venv
uv sync
```

### Setup frontend

```bash
cd frontend
npm install
```

## Environment Setup

Copy `.env.example` to `.env` and adjust values if needed:

```bash
cp .env.example .env
```

Current Story 1.1 variables:
- `NEXT_PUBLIC_API_URL` (frontend): `http://localhost:8000`
- `CORS_ORIGINS` (backend): `http://localhost:3000`

## How to start

### Start both (recommended)

```bash
npm run dev
```

This starts:
- Frontend: http://localhost:3000
- Backend: http://localhost:8000

### Start frontend only

```bash
npm run dev:frontend
# or
cd frontend && npm run dev
```

### Start backend only

```bash
npm run dev:backend
# or
cd backend && uv run uvicorn apex_backend.main:app --host 0.0.0.0 --port 8000 --reload
```

## API Endpoints

- `GET /health` - Returns `{"status": "ok"}`

## Validation

- Frontend: http://localhost:3000
- Backend: http://localhost:8000/health
