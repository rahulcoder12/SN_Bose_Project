# 🛡️ Zero Trust Auth

**Continuous behavioral biometric authentication engine** that uses keystroke dynamics, mouse movement patterns, and scroll behavior to transparently verify user identity in real-time using AI anomaly detection.

## Architecture

```
zero-trust-auth/
├── ingestion-api/          # FastAPI backend (Python)
│   ├── main.py             # Routes, middleware, AI inference
│   ├── auth.py             # JWT token management
│   ├── database.py         # PostgreSQL with connection pooling
│   ├── biometrics.py       # Keystroke, mouse, scroll feature extraction
│   ├── ml_pipeline.py      # Isolation Forest training pipeline
│   └── tests/              # Unit + integration tests
├── client-sdk/             # Vanilla JS telemetry SDK + web dashboard
├── enterprise-extension/   # Chrome Extension for continuous monitoring
├── docs/                   # Schema documentation
└── docker-compose.yml      # Container orchestration
```

### Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10, FastAPI, Uvicorn |
| Database | PostgreSQL (Neon Cloud) |
| Auth | JWT (python-jose), bcrypt |
| AI/ML | Scikit-learn (Isolation Forest), Pandas |
| Client | Vanilla JavaScript SDK |
| Extension | Chrome Extension (Manifest V3) |
| Deployment | Docker, Docker Compose |

## Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL database (or [Neon](https://neon.tech) account)

### Setup

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd zero-trust-auth

# 2. Create and activate virtual environment
cd ingestion-api
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env with your database URL and secrets

# 5. Start the server
uvicorn main:app --reload

# 6. Open API docs
open http://localhost:8000/developers
```

## API Endpoints

### Authentication
| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/v1/auth/register` | None | Register a new user |
| `POST` | `/api/v1/auth/login` | None | Login, receive JWT tokens |
| `POST` | `/api/v1/auth/refresh` | None | Refresh access token |
| `GET` | `/api/v1/auth/me` | JWT | Get current user profile |
| `POST` | `/api/v1/auth/regenerate` | JWT | Rotate password |

### Core Security
| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/v1/ingest` | API Key | Submit biometric telemetry |
| `POST` | `/api/v1/calibrate/complete` | API Key | Finalize calibration baseline |

### Admin & System
| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/v1/admin/sessions` | JWT | Live session monitoring |
| `GET` | `/health` | None | System health check |

## Authentication Flow

```
1. POST /auth/register  →  Create account (bcrypt-hashed password)
2. POST /auth/login      →  Receive { access_token, refresh_token }
3. GET  /auth/me         →  Send: Authorization: Bearer <access_token>
4. POST /auth/refresh    →  Send: { refresh_token } → new access_token
```

## Security Features

- **bcrypt** password hashing (12 rounds)
- **JWT** access tokens (30 min) + refresh tokens (7 days)
- **Rate limiting** (5/min login, 3/min register, 20/min telemetry)
- **API key** authentication for enterprise telemetry
- **Security headers** (HSTS, X-Content-Type-Options, X-Frame-Options)
- **Parameterized SQL** queries (SQL injection prevention)
- **Audit logging** with rotating file handler
- **GDPR compliance** — automatic 24-hour data eviction

## Running Tests

```bash
cd ingestion-api
source venv/bin/activate
pytest tests/ -v
```

## Docker

```bash
# Build and run with Docker Compose
docker-compose up --build

# Or build manually
cd ingestion-api
docker build -t zero-trust-api .
docker run -p 8000:8000 --env-file .env zero-trust-api
```

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | ✅ |
| `SECRET_KEY` | JWT signing key (min 32 chars) | ✅ |
| `WEBHOOK_URL` | SOC alert webhook endpoint | Optional |
| `API_KEY_1` | Enterprise client API key | ✅ |
| `API_KEY_2` | Enterprise client API key | Optional |

## License

ISC
