# Receipt.ai Deployment Guide

Complete guide for deploying Receipt.ai in development and production environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [OAuth Setup](#oauth-setup)
   - [Google Cloud (Gmail API)](#google-cloud-gmail-api)
   - [Microsoft Entra (Graph API)](#microsoft-entra-graph-api)
3. [Development Setup](#development-setup)
4. [Production Deployment](#production-deployment)
5. [Backup & Restore](#backup--restore)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- Docker and Docker Compose v2+
- A domain name (for production with HTTPS)
- Google Cloud account (for Gmail integration)
- Microsoft Azure account (for Microsoft 365 integration)

---

## OAuth Setup

### Google Cloud (Gmail API)

1. **Create a Google Cloud Project**
   ```
   https://console.cloud.google.com/
   ```
   - Click "Select a project" → "New Project"
   - Name: "Receipt AI" (or your choice)
   - Click "Create"

2. **Enable the Gmail API**
   - Go to "APIs & Services" → "Library"
   - Search for "Gmail API"
   - Click "Enable"

3. **Configure OAuth Consent Screen**
   - Go to "APIs & Services" → "OAuth consent screen"
   - Choose "External" (or "Internal" for Workspace)
   - Fill in:
     - App name: "Receipt.ai"
     - User support email: your email
     - Developer contact: your email
   - Click "Save and Continue"
   - Add scopes:
     - `https://www.googleapis.com/auth/gmail.readonly`
     - `https://www.googleapis.com/auth/userinfo.email`
   - Add test users (your Gmail addresses)
   - Complete the wizard

4. **Create OAuth Credentials**
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth client ID"
   - Application type: "Web application"
   - Name: "Receipt.ai Web Client"
   - Authorized redirect URIs:
     - Development: `http://localhost:8000/api/auth/google/callback`
     - Production: `https://your-domain.com/api/auth/google/callback`
   - Click "Create"
   - **Copy the Client ID and Client Secret**

5. **Important Notes**
   - For production, you'll need to verify your app with Google
   - Until verified, only test users can authenticate
   - Verification requires privacy policy and terms of service URLs

### Microsoft Entra (Graph API)

1. **Register an Application**
   ```
   https://portal.azure.com/
   ```
   - Navigate to "Microsoft Entra ID" (formerly Azure AD)
   - Go to "App registrations" → "New registration"
   - Name: "Receipt.ai"
   - Supported account types: "Accounts in any organizational directory and personal Microsoft accounts"
   - Redirect URI (Web):
     - Development: `http://localhost:8000/api/auth/microsoft/callback`
     - Production: `https://your-domain.com/api/auth/microsoft/callback`
   - Click "Register"

2. **Note Your Application (client) ID**
   - On the Overview page, copy the "Application (client) ID"
   - This is your `MICROSOFT_CLIENT_ID`

3. **Create a Client Secret**
   - Go to "Certificates & secrets"
   - Click "New client secret"
   - Description: "Receipt.ai Production"
   - Expiration: Choose appropriate duration
   - Click "Add"
   - **Immediately copy the secret value** (shown only once)
   - This is your `MICROSOFT_CLIENT_SECRET`

4. **Configure API Permissions**
   - Go to "API permissions"
   - Click "Add a permission" → "Microsoft Graph"
   - Choose "Delegated permissions"
   - Add:
     - `Mail.Read`
     - `User.Read`
     - `offline_access`
   - Click "Add permissions"
   - If you're an admin, click "Grant admin consent"

5. **Multi-Tenant Configuration**
   - For `MICROSOFT_TENANT_ID`:
     - Use `common` for any Microsoft account
     - Use `organizations` for work/school accounts only
     - Use your specific tenant ID for single-tenant apps

---

## Development Setup

### 1. Clone and Configure

```bash
# Clone the repository
cd /path/to/Receipt.ai

# Copy environment template
cp .env.example .env

# Edit .env with your OAuth credentials
nano .env
```

### 2. Set Development Environment Variables

Edit `.env`:
```bash
# Security (use these for development)
ENCRYPTION_KEY=dev-encryption-key-change-in-production
SECRET_KEY=dev-secret-key-change-in-production

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Microsoft OAuth
MICROSOFT_CLIENT_ID=your-microsoft-app-id
MICROSOFT_CLIENT_SECRET=your-microsoft-secret
MICROSOFT_TENANT_ID=common

# Optional: Enable LLM extraction
# OPENAI_API_KEY=sk-...
# LLM_ENABLED=true
```

### 3. Start Development Stack

```bash
# Build and start all services
docker compose up --build

# Or run in background
docker compose up -d --build

# View logs
docker compose logs -f
```

### 4. Access the Application

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### 5. Run Tests

```bash
# Run tests inside container
docker compose exec backend pytest -v

# Or run locally
cd backend
pip install -r requirements.txt
pytest -v
```

---

## Production Deployment

### 1. Server Requirements

- Ubuntu 22.04+ or similar Linux
- 2+ CPU cores, 4GB+ RAM
- Docker and Docker Compose installed
- Domain name pointing to your server
- Ports 80 and 443 open

### 2. Generate Secure Keys

```bash
# Generate encryption key (32 bytes)
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate database password
python -c "import secrets; print(secrets.token_urlsafe(24))"
```

### 3. Configure Production Environment

Create `.env` on your server:

```bash
# REQUIRED: Security Keys
ENCRYPTION_KEY=<generated-encryption-key>
SECRET_KEY=<generated-secret-key>

# REQUIRED: Database
POSTGRES_USER=receipt
POSTGRES_PASSWORD=<generated-db-password>
POSTGRES_DB=receipt

# OPTIONAL: Redis password
REDIS_PASSWORD=<optional-redis-password>

# REQUIRED: Domain Configuration
DOMAIN=receipts.yourdomain.com
BACKEND_URL=https://receipts.yourdomain.com
FRONTEND_URL=https://receipts.yourdomain.com

# Google OAuth (update redirect URI in Google Console)
GOOGLE_CLIENT_ID=your-production-client-id
GOOGLE_CLIENT_SECRET=your-production-secret

# Microsoft OAuth (update redirect URI in Azure Portal)
MICROSOFT_CLIENT_ID=your-production-app-id
MICROSOFT_CLIENT_SECRET=your-production-secret
MICROSOFT_TENANT_ID=common

# Optional: LLM
OPENAI_API_KEY=sk-...
LLM_ENABLED=true
```

### 4. Update OAuth Redirect URIs

**Google Cloud Console:**
- Add: `https://receipts.yourdomain.com/api/auth/google/callback`

**Microsoft Azure Portal:**
- Add: `https://receipts.yourdomain.com/api/auth/microsoft/callback`

### 5. Configure Caddy

Edit `docker/caddy/Caddyfile`:

```caddyfile
receipts.yourdomain.com {
    # ... (rest of config)
}
```

### 6. Deploy

```bash
# Pull latest code
git pull origin main

# Build and start production stack
docker compose -f docker-compose.prod.yml up -d --build

# Check status
docker compose -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.prod.yml logs -f
```

### 7. Verify Deployment

1. Visit `https://receipts.yourdomain.com`
2. Check that HTTPS certificate is valid (Caddy auto-obtains from Let's Encrypt)
3. Test OAuth flows for both Gmail and Microsoft

---

## Backup & Restore

### Automated Backups

Create a cron job for daily backups:

```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * cd /path/to/Receipt.ai && ./scripts/backup.sh /backups/receipt
```

### Manual Backup

```bash
# Create backup
./scripts/backup.sh ./backups

# Backup will contain:
# - database.sql.gz (PostgreSQL dump)
# - attachments.tar.gz (uploaded files)
# - .env.backup (configuration)
```

### Restore from Backup

```bash
# Restore (will prompt for confirmation)
./scripts/restore.sh ./backups/20240115_120000
```

### Offsite Backup Recommendations

1. **Database**: Use `pg_dump` output for cloud storage (S3, GCS, etc.)
2. **Attachments**: Sync to cloud storage or use volume backup solutions
3. **Encryption Key**: Store securely in a password manager (if lost, tokens cannot be decrypted)

---

## Troubleshooting

### OAuth Errors

**"redirect_uri_mismatch" (Google)**
- Ensure redirect URI in Google Console exactly matches
- Development: `http://localhost:8000/api/auth/google/callback`
- Production: `https://your-domain.com/api/auth/google/callback`

**"AADSTS50011" (Microsoft)**
- Add redirect URI in Azure Portal → App registrations → Authentication
- Ensure it matches exactly including protocol and path

**"access_denied" / "consent_required"**
- Google: Add user as test user in OAuth consent screen
- Microsoft: Ensure API permissions are granted

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker compose logs postgres

# Connect to database manually
docker compose exec postgres psql -U receipt -d receipt

# Check tables exist
\dt
```

### Celery Worker Issues

```bash
# Check worker logs
docker compose logs worker

# Check Redis connection
docker compose exec redis redis-cli ping
```

### Sync Not Working

1. Check worker is running: `docker compose ps`
2. Check account tokens are valid (OAuth may need re-auth)
3. Check sync_error field on account: `/api/accounts/{id}/stats`

### TLS/HTTPS Issues (Production)

```bash
# Check Caddy logs
docker compose -f docker-compose.prod.yml logs caddy

# Verify DNS is pointed correctly
dig receipts.yourdomain.com

# Test certificate
curl -v https://receipts.yourdomain.com
```

### Reset Everything (Development)

```bash
# Stop and remove containers, volumes
docker compose down -v

# Rebuild and start fresh
docker compose up --build
```

---

## Security Checklist

- [ ] Generated unique ENCRYPTION_KEY and SECRET_KEY
- [ ] Strong POSTGRES_PASSWORD set
- [ ] OAuth credentials are production credentials (not development)
- [ ] Redirect URIs use HTTPS in production
- [ ] `.env` file has restricted permissions (`chmod 600 .env`)
- [ ] Backups are encrypted or stored securely
- [ ] Server firewall only allows ports 80, 443, and SSH
- [ ] Regular security updates applied to server

---

## Support

For issues and feature requests, please open an issue on GitHub.
