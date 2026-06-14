# FastAPI + React Auth Boilerplate

A minimal full-stack starter with:

- FastAPI backend
- Python 3.13 backend runtime
- React (Vite) frontend
- PostgreSQL database
- SQLAlchemy ORM
- Alembic migrations
- bcrypt password hashing + PyJWT tokens
- Username/password auth
- Google OIDC login flow
- Docker Compose local development

## Project Structure

- `backend`: FastAPI app, SQLAlchemy models, Alembic migrations
- `frontend`: React app with login/signup/dashboard pages
- `docker-compose.yml`: Orchestrates db/backend/frontend

## Quick Start

1. Copy env vars:

   ```bash
   cp .env.example .env
   ```

2. Start all services:

   ```bash
   docker compose up --build
   ```

3. Open apps:

   - Frontend: http://localhost:5173
   - Backend docs: http://localhost:8000/docs

## Authentication Endpoints

- `POST /api/v1/auth/signup`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `GET /api/v1/auth/google/login`
- `GET /api/v1/auth/google/callback`

## Token Behavior

- Login/signup return an access token and refresh token.
- `POST /api/v1/auth/refresh` rotates refresh tokens and issues a new access token.
- `POST /api/v1/auth/logout` revokes the provided refresh token.

## Run Backend Tests

```bash
docker compose run --rm backend pytest -q
```

## Google OIDC Setup

1. Create OAuth credentials in Google Cloud Console.
2. Add to `.env`:
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`
3. Authorized redirect URI:
   - `http://localhost:8000/api/v1/auth/google/callback`

## Notes

- On backend container start, migrations run automatically via `alembic upgrade head`.
- For production, replace dev servers and configure secure cookies/HTTPS and refresh-token flows.
