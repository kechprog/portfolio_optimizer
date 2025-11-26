# Alembic Database Migrations

This directory contains Alembic database migration scripts for the Portfolio Optimizer backend.

## Setup

Alembic is configured to work with PostgreSQL using async SQLAlchemy patterns.

### Prerequisites

1. Ensure PostgreSQL is running (via Docker Compose):
   ```bash
   cd backend
   docker-compose up -d
   ```

2. Ensure your `.env` file has the `DATABASE_URL` set:
   ```
   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/portfolio_db
   ```

## Common Commands

### Run Migrations

Apply all pending migrations to the database:
```bash
cd backend
alembic upgrade head
```

### Create a New Migration

Auto-generate a migration based on model changes:
```bash
alembic revision --autogenerate -m "description of changes"
```

Create an empty migration (for data migrations or custom SQL):
```bash
alembic revision -m "description of changes"
```

### Rollback Migrations

Rollback one migration:
```bash
alembic downgrade -1
```

Rollback to a specific revision:
```bash
alembic downgrade <revision_id>
```

Rollback all migrations:
```bash
alembic downgrade base
```

### Check Migration Status

View current migration status:
```bash
alembic current
```

View migration history:
```bash
alembic history
```

View pending migrations:
```bash
alembic history --verbose
```

## Migration Files

Migration files are stored in `alembic/versions/`. Each migration has:
- A unique revision ID
- An `upgrade()` function to apply changes
- A `downgrade()` function to revert changes

## Database Models

Database models are defined in `db/models.py` using SQLAlchemy's declarative base.

When you modify models:
1. Update the model in `db/models.py`
2. Generate a migration: `alembic revision --autogenerate -m "description"`
3. Review the generated migration file
4. Apply the migration: `alembic upgrade head`

## Initial Migration

The initial migration (`001_create_users_table.py`) creates the users table with:
- `id` (UUID, primary key)
- `session_id` (VARCHAR, unique, indexed)
- `connected_at` (TIMESTAMP WITH TIME ZONE)
- `last_active_at` (TIMESTAMP WITH TIME ZONE)
- `metadata_` (JSONB, nullable)

## Configuration

- `alembic.ini`: Main configuration file
- `alembic/env.py`: Environment setup with async support
- Database URL is read from the `DATABASE_URL` environment variable

## Troubleshooting

### Connection Issues

If you get connection errors:
1. Verify PostgreSQL is running: `docker ps`
2. Check your `.env` file has the correct `DATABASE_URL`
3. Ensure you can connect to PostgreSQL:
   ```bash
   psql postgresql://postgres:postgres@localhost:5432/portfolio_db
   ```

### Import Errors

If you get import errors when running migrations:
1. Make sure you're in the `backend` directory
2. Ensure all dependencies are installed: `pip install -r requirements.txt`
3. Check that `PYTHONPATH` includes the backend directory

### Migration Conflicts

If you have migration conflicts (multiple heads):
```bash
alembic merge -m "merge heads" <rev1> <rev2>
```

## Best Practices

1. Always review auto-generated migrations before applying them
2. Test migrations in development before applying to production
3. Keep migrations small and focused
4. Write meaningful migration messages
5. Never modify migrations that have been applied to production
6. Always write downgrade functions to enable rollbacks
