# Receipt.ai

A Wellybox-like receipt extraction application that automatically syncs emails from Gmail and Microsoft 365, extracts receipts, and provides a clean interface for managing them.

## Features

- **Multi-provider email sync**
  - Gmail via Gmail API
  - Microsoft 365 via Microsoft Graph API
  - OAuth2 authentication with encrypted token storage

- **Incremental sync**
  - Gmail: Uses History API with historyId cursor
  - Microsoft: Uses delta queries with @odata.deltaLink
  - Idempotent inserts prevent duplicates

- **Attachment handling**
  - Downloads PDF, PNG, JPG attachments
  - SHA256 hash-based deduplication
  - Efficient storage with hash-based directory structure

- **Receipt extraction**
  - Rules-based extraction with confidence scoring
  - Optional LLM fallback (OpenAI) for low-confidence extractions
  - Strict JSON schema validation

- **Modern UI**
  - React + TypeScript frontend
  - Dashboard with statistics
  - Account management
  - Receipt list with filtering and pagination
  - CSV export

- **Production-ready**
  - Docker Compose for development and production
  - Caddy reverse proxy with automatic TLS
  - PostgreSQL for data persistence
  - Redis + Celery for background jobs
  - Backup and restore scripts

## Quick Start (Development)

```bash
# 1. Clone the repository
git clone <repo-url>
cd Receipt.ai

# 2. Copy and configure environment
cp .env.example .env
# Edit .env with your OAuth credentials (see README_DEPLOYMENT.md)

# 3. Start the stack
docker compose up --build

# 4. Open in browser
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│                   React + TypeScript                         │
│                    (localhost:3000)                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        Backend                               │
│                   FastAPI + SQLAlchemy                       │
│                    (localhost:8000)                          │
├─────────────────────────────────────────────────────────────┤
│  /api/auth/*     OAuth flows (Gmail, Microsoft)             │
│  /api/accounts/* Account management                          │
│  /api/receipts/* Receipt CRUD + export                       │
│  /api/sync/*     Sync job management                         │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────┐    ┌─────────────────┐    ┌─────────────┐
│  PostgreSQL │    │   Celery Worker │    │    Redis    │
│   Database  │    │  (Background)   │    │   (Queue)   │
└─────────────┘    └─────────────────┘    └─────────────┘
                           │
                           ▼
               ┌───────────────────────┐
               │     Email APIs        │
               │  Gmail / Graph        │
               └───────────────────────┘
```

## Project Structure

```
Receipt.ai/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── api/            # API routes
│   │   ├── core/           # Config, database, encryption
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas
│   │   └── services/       # Business logic
│   ├── tests/              # pytest tests
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/       # API client
│   │   └── types/
│   ├── Dockerfile
│   └── package.json
├── worker/                 # Celery worker
│   ├── celery_app.py
│   ├── tasks.py
│   └── Dockerfile
├── docker/
│   ├── caddy/             # Caddy configuration
│   └── postgres/          # PostgreSQL init
├── scripts/
│   ├── backup.sh
│   └── restore.sh
├── docker-compose.yml      # Development
├── docker-compose.prod.yml # Production
├── .env.example
├── README.md
└── README_DEPLOYMENT.md    # Detailed deployment guide
```

## Configuration

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `ENCRYPTION_KEY` | Key for encrypting OAuth tokens at rest |
| `SECRET_KEY` | Application secret key |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `MICROSOFT_CLIENT_ID` | Microsoft app (client) ID |
| `MICROSOFT_CLIENT_SECRET` | Microsoft client secret |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MICROSOFT_TENANT_ID` | `common` | Microsoft tenant ID |
| `OPENAI_API_KEY` | - | Enable LLM extraction |
| `LLM_ENABLED` | `false` | Use LLM for low-confidence extraction |
| `POSTGRES_PASSWORD` | `receipt` | Database password |

See `.env.example` for full list.

## OAuth Setup

Detailed instructions in [README_DEPLOYMENT.md](README_DEPLOYMENT.md).

### Google Cloud (Gmail API)
1. Create project at https://console.cloud.google.com
2. Enable Gmail API
3. Configure OAuth consent screen
4. Create OAuth 2.0 credentials
5. Add redirect URI: `http://localhost:8000/api/auth/google/callback`

### Microsoft Entra (Graph API)
1. Register app at https://portal.azure.com
2. Note Application (client) ID
3. Create client secret
4. Add API permissions: Mail.Read, User.Read, offline_access
5. Add redirect URI: `http://localhost:8000/api/auth/microsoft/callback`

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/google` | GET | Start Gmail OAuth |
| `/api/auth/microsoft` | GET | Start Microsoft OAuth |
| `/api/accounts` | GET | List connected accounts |
| `/api/accounts/{id}` | DELETE | Disconnect account |
| `/api/sync/start` | POST | Start sync for account |
| `/api/receipts` | GET | List receipts (paginated) |
| `/api/receipts/export` | GET | Export receipts as CSV |
| `/api/receipts/{id}` | GET | Get receipt details |

Full API documentation available at `/docs` when running.

## Testing

```bash
# Run all tests
docker compose exec backend pytest -v

# Run specific test file
docker compose exec backend pytest tests/test_idempotency.py -v

# Run with coverage
docker compose exec backend pytest --cov=app --cov-report=html
```

### Test Coverage

- **Idempotency**: Email sync doesn't create duplicates
- **Hash stability**: Attachment SHA256 is consistent
- **Schema validation**: Invalid LLM responses are rejected
- **Encryption**: Token encryption/decryption roundtrip

## Production Deployment

See [README_DEPLOYMENT.md](README_DEPLOYMENT.md) for complete instructions.

```bash
# Quick production start
docker compose -f docker-compose.prod.yml up -d --build
```

Features:
- Automatic HTTPS via Let's Encrypt (Caddy)
- PostgreSQL with persistent volume
- Redis for job queue
- Celery worker + beat scheduler
- Built React frontend served by Caddy

## Backup & Restore

```bash
# Create backup
./scripts/backup.sh ./backups

# Restore from backup
./scripts/restore.sh ./backups/20240115_120000
```

Backups include:
- PostgreSQL database dump
- Attachment files
- Configuration (.env)

## Security

- OAuth2 refresh tokens encrypted at rest (AES-256 via Fernet)
- Tokens never logged
- HTTPS enforced in production
- CORS restricted to frontend origin
- PostgreSQL with strong password
- Secret keys from environment (not in code)

## License

MIT
