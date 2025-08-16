# Deployment Guide

## Environment Configuration

The frontend now uses configurable API endpoints that work in both development and production environments.

### Development

For local development, the app uses `http://localhost:8000` by default. You can override this by setting:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Production Deployment

#### Option 1: Same Domain Deployment
If your frontend and backend are deployed on the same domain, set:
```bash
NEXT_PUBLIC_API_URL=""
```
This will use relative paths (e.g., `/api/documents`).

#### Option 2: Different Domain Deployment
If your backend is on a different domain, set:
```bash
NEXT_PUBLIC_API_URL=https://your-backend-domain.com
```

### Environment Variables

1. Copy `.env.example` to `.env.local` for local development
2. Set `NEXT_PUBLIC_API_URL` based on your deployment scenario
3. For production, configure the environment variable in your hosting platform

### Deployment Platforms

#### Vercel
```bash
vercel env add NEXT_PUBLIC_API_URL
```

#### Netlify
Add to netlify.toml or dashboard environment variables

#### Docker
```dockerfile
ENV NEXT_PUBLIC_API_URL=https://your-backend-domain.com
```

## API Endpoints

The app will automatically use the correct endpoints:
- `/send-message-stream`
- `/upload-document` 
- `/documents`