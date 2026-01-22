#!/bin/bash
# Restore script for Receipt.ai
# Usage: ./scripts/restore.sh <backup_path>

set -e

BACKUP_PATH="${1}"

if [ -z "$BACKUP_PATH" ]; then
    echo "Usage: ./scripts/restore.sh <backup_path>"
    echo "Example: ./scripts/restore.sh ./backups/20240115_120000"
    exit 1
fi

if [ ! -d "$BACKUP_PATH" ]; then
    echo "Error: Backup directory not found: $BACKUP_PATH"
    exit 1
fi

echo "WARNING: This will overwrite your current database and attachments!"
read -p "Are you sure you want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

# Load environment variables
if [ -f .env ]; then
    source .env
fi

POSTGRES_USER="${POSTGRES_USER:-receipt}"
POSTGRES_DB="${POSTGRES_DB:-receipt}"

# Restore PostgreSQL
if [ -f "$BACKUP_PATH/database.sql.gz" ]; then
    echo "Restoring PostgreSQL database..."

    # Drop and recreate database
    docker exec receipt_postgres psql -U "$POSTGRES_USER" -c "DROP DATABASE IF EXISTS ${POSTGRES_DB};"
    docker exec receipt_postgres psql -U "$POSTGRES_USER" -c "CREATE DATABASE ${POSTGRES_DB};"

    # Restore data
    gunzip -c "$BACKUP_PATH/database.sql.gz" | docker exec -i receipt_postgres psql -U "$POSTGRES_USER" "$POSTGRES_DB"

    echo "Database restored."
else
    echo "Warning: No database backup found."
fi

# Restore attachments
if [ -f "$BACKUP_PATH/attachments.tar.gz" ]; then
    echo "Restoring attachments..."

    docker run --rm \
        -v receipt_attachment_data:/data \
        -v "$(pwd)/$BACKUP_PATH":/backup:ro \
        alpine sh -c "rm -rf /data/* && tar xzf /backup/attachments.tar.gz -C /data"

    echo "Attachments restored."
else
    echo "Warning: No attachments backup found."
fi

echo ""
echo "Restore completed!"
echo "You may need to restart the services: docker compose restart"
