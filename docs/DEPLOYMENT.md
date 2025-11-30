# Deployment Guide

## Overview

This guide covers deploying Planning Precedent AI to production. The system consists of:

1. **Backend** - FastAPI application (Python)
2. **Frontend** - Next.js application (TypeScript)
3. **Database** - Supabase (PostgreSQL + pgvector)
4. **Cache/Queue** - Redis
5. **Background Workers** - Celery

## Prerequisites

- Docker and Docker Compose
- Supabase account and project
- OpenAI API key
- Domain name and SSL certificate
- AWS account (optional, for Textract)

## Environment Setup

### 1. Create Supabase Project

1. Go to [supabase.com](https://supabase.com) and create a new project
2. Note down:
   - Project URL
   - Anon key
   - Service role key
3. Enable the `vector` extension:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
4. Run the migration script from `database/migrations/001_initial_schema.sql`

### 2. Configure Environment Variables

Create `.env` files:

**Backend (.env):**
```bash
# Application
APP_ENV=production
SECRET_KEY=your-secure-secret-key-minimum-32-chars
DEBUG=false

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key
DATABASE_URL=postgresql://postgres:password@db.your-project.supabase.co:5432/postgres

# OpenAI
OPENAI_API_KEY=sk-your-api-key

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
```

**Frontend (.env.local):**
```bash
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
```

### 3. SSL Certificates

For production, set up SSL using Let's Encrypt:

```bash
certbot certonly --standalone -d api.yourdomain.com -d yourdomain.com
```

Copy certificates to `nginx/ssl/`.

## Deployment Options

### Option A: Docker Compose (Recommended for VPS)

1. **Clone and configure:**
   ```bash
   git clone https://github.com/your-org/planning-precedent-ai.git
   cd planning-precedent-ai
   cp backend/.env.example backend/.env
   # Edit .env with your values
   ```

2. **Build and start:**
   ```bash
   docker-compose -f docker-compose.yml --profile production up -d --build
   ```

3. **Run database migrations:**
   ```bash
   docker-compose exec backend alembic upgrade head
   ```

4. **Initial data scrape:**
   ```bash
   docker-compose exec celery-worker python -m app.scripts.initial_scrape
   ```

### Option B: Kubernetes (For Scale)

See `k8s/` directory for Kubernetes manifests.

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/
```

### Option C: Serverless (AWS/GCP)

#### AWS Deployment:
- Backend: AWS Lambda + API Gateway
- Frontend: Vercel or AWS Amplify
- Database: Supabase (managed)
- Queue: AWS SQS instead of Redis

#### GCP Deployment:
- Backend: Cloud Run
- Frontend: Cloud Run or Vercel
- Database: Supabase (managed)
- Queue: Cloud Tasks

## Post-Deployment

### 1. Verify Health

```bash
curl https://api.yourdomain.com/health
```

### 2. Set Up Monitoring

- **Sentry**: Add `SENTRY_DSN` to backend .env
- **Prometheus/Grafana**: Enable metrics endpoint
- **Uptime monitoring**: Use UptimeRobot or similar

### 3. Configure Scheduled Scraping

The Celery Beat scheduler runs automatic scraping. Configure in `app/celery/config.py`:

```python
beat_schedule = {
    'scrape-new-decisions': {
        'task': 'app.tasks.scrape_decisions',
        'schedule': crontab(hour=2, minute=0),  # 2 AM daily
    },
}
```

### 4. Backup Strategy

- **Database**: Supabase includes automatic backups
- **Redis**: Not critical (cache only)
- **Scraped PDFs**: Configure S3 bucket for document storage

## Scaling Considerations

### Horizontal Scaling

1. **Backend**: Add more Gunicorn workers or deploy multiple containers
2. **Celery**: Add more worker containers for parallel scraping
3. **Frontend**: Deploy to CDN (Vercel handles this automatically)

### Database Scaling

- Supabase Pro plan for production workloads
- Consider read replicas for search-heavy workloads
- Index optimisation for vector search

### Caching Strategy

- Redis for API response caching
- CDN for static assets
- Embedding cache to reduce OpenAI API calls

## Cost Estimation (Monthly)

| Service | Free Tier | Production |
|---------|-----------|------------|
| Supabase | 500MB database | £20-50 |
| OpenAI | Pay per use | £50-200 |
| Hosting (VPS) | - | £20-50 |
| AWS Textract | Pay per page | £10-30 |
| Domain + SSL | - | £10 |
| **Total** | ~£0 | ~£110-340 |

## Troubleshooting

### Common Issues

1. **Vector search slow**: Check HNSW index exists
2. **Scraper blocked**: Reduce rate limit, add delays
3. **PDF extraction fails**: Check Tesseract installation
4. **Memory issues**: Increase container limits

### Logs

```bash
# Backend logs
docker-compose logs -f backend

# Celery logs
docker-compose logs -f celery-worker

# All logs
docker-compose logs -f
```

## Security Checklist

- [ ] Strong SECRET_KEY (32+ random characters)
- [ ] HTTPS only (redirect HTTP)
- [ ] Rate limiting enabled
- [ ] CORS configured for your domains only
- [ ] API keys stored securely (not in code)
- [ ] Database connection uses SSL
- [ ] Regular security updates
- [ ] Supabase RLS policies enabled
