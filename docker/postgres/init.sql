-- PostgreSQL initialization script
-- This runs on first database creation

-- Enable useful extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create indexes for better search performance (if tables exist)
-- Note: Tables are created by SQLAlchemy, this is for additional optimizations
