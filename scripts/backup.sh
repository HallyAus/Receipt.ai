#!/bin/bash
# Backup script for Receipt.ai
# Usage: ./scripts/backup.sh [backup_dir]

set -e

BACKUP_DIR="${1:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="$BACKUP_DIR/$TIMESTAMP"

echo "Creating backup at $BACKUP_PATH..."
mkdir -p "$BACKUP_PATH"

# Load environment variables
if [ -f .env ]; then
    source .env
fi

POSTGRES_USER="${POSTGRES_USER:-receipt}"
POSTGRES_DB="${POSTGRES_DB:-receipt}"

# Backup PostgreSQL
echo "Backing up PostgreSQL database..."
docker exec receipt_postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$BACKUP_PATH/database.sql.gz"

# Backup attachments volume
echo "Backing up attachments..."
docker run --rm \
    -v receipt_attachment_data:/data:ro \
    -v "$(pwd)/$BACKUP_PATH":/backup \
    alpine tar czf /backup/attachments.tar.gz -C /data .

# Backup .env file (encrypted)
echo "Backing up configuration..."
if [ -f .env ]; then
    cp .env "$BACKUP_PATH/.env.backup"
    echo "WARNING: .env file backed up but NOT encrypted. Secure this backup!"
fi

# Create manifest
echo "Creating backup manifest..."
cat > "$BACKUP_PATH/manifest.json" << EOF
{
    "timestamp": "$TIMESTAMP",
    "version": "1.0.0",
    "contents": [
        "database.sql.gz",
        "attachments.tar.gz",
        ".env.backup"
    ]
}
EOF

echo "Backup completed: $BACKUP_PATH"
echo ""
echo "Files created:"
ls -lh "$BACKUP_PATH"
echo ""
echo "To restore, use: ./scripts/restore.sh $BACKUP_PATH"
