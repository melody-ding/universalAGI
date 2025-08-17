# Universal AGI - Document Analysis & Chat System

## Overview

A comprehensive document analysis and conversational AI system that combines Chain of Thought (CoT) reasoning with multi-modal inputs. The system features document ingestion, intelligent analysis, compliance grouping, and an interactive chat interface with streaming responses and citation support.

### Key Features

- **Document Processing**: Upload and analyze various document formats with intelligent parsing
- **Multi-Modal Chat**: Conversational interface supporting text and images with CoT reasoning
- **Compliance Analysis**: Automated compliance grouping and framework matching
- **Smart Orchestration**: Intelligent routing between different analysis agents
- **Citation Support**: Real-time citations with footnotes for document references
- **Streaming Responses**: Real-time response streaming with thinking steps visualization

## Architecture

The system consists of three main components:

- **Frontend**: Next.js React application with TypeScript
- **Backend**: FastAPI Python service with LangChain agent integration
- **Database**: PostgreSQL with S3 for document storage

## Prerequisites

- **Node.js** (v18+)
- **Python** (3.9+)
- **Docker** and Docker Compose
- **AWS Account** (for S3 and RDS)
- **OpenAI API Key**

## Quick Start with Docker

1. **Clone the Repository:**
   ```bash
   git clone <repository-url>
   cd universalAGI
   ```

2. **Set Up Environment Variables:**
   ```bash
   cp env.example .env
   # Edit .env with your configuration
   ```

3. **Start with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

4. **Access the Application:**
   - Frontend: [http://localhost:3000](http://localhost:3000)
   - Backend API: [http://localhost:8000](http://localhost:8000)

## Development Setup

### Backend Setup

1. **Navigate to backend directory:**
   ```bash
   cd backend
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment:**
   ```bash
   cp env.example .env
   # Edit .env with your API keys and database configuration
   ```

4. **Run the backend:**
   ```bash
   python main.py
   ```

### Frontend Setup

1. **Navigate to web directory:**
   ```bash
   cd web
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Start development server:**
   ```bash
   npm run dev
   ```

## Environment Configuration

Required environment variables:

```bash
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key

# AWS Configuration
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=your_aws_region

# Database Configuration
RDS_CLUSTER_ARN=your_rds_cluster_arn
RDS_SECRET_ARN=your_rds_secret_arn
RDS_DATABASE_NAME=your_database_name

# S3 Configuration
S3_BUCKET_NAME=your_s3_bucket_name
```

## API Endpoints

### Core Endpoints
- `GET /` - Health check
- `POST /send-message` - Send chat message with streaming response
- `POST /upload-document` - Upload and process documents
- `GET /documents` - List processed documents
- `GET /documents/{id}` - Get document details
- `GET /compliance-groups` - List compliance groups

### Document Analysis
- `POST /documents/{id}/analyze` - Analyze document compliance
- `GET /documents/{id}/analysis` - Get analysis results

## Features

### Document Processing
- Multi-format support (PDF, DOCX, TXT, images)
- Intelligent text extraction and chunking
- Metadata extraction and indexing
- S3 storage integration

### AI Capabilities
- Chain of Thought reasoning
- Multi-document search and analysis
- Framework matching and compliance scoring
- Intelligent agent orchestration
- Streaming responses with thinking steps

### User Interface
- Modern React-based interface
- Real-time chat with citations
- Document management dashboard
- Compliance analysis visualization
- Responsive design with Tailwind CSS

## Deployment

### Production Deployment
```bash
# Build and deploy production containers
docker-compose -f docker-compose.prod.yml up -d
```

### AWS Deployment
See `backend/deploy/README.md` for detailed AWS deployment instructions using Terraform.

## Contributing

1. Follow the code style guidelines in `CLAUDE.md`
2. Keep all imports at the top level
3. Implement proper error handling with logging
4. Add tests for new features
5. Update documentation as needed
