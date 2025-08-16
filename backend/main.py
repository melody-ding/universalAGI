from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routes import router
from utils.logging_config import get_logger
from utils.error_handler import setup_error_handlers

# Get logger for main application
logger = get_logger(__name__)

app = FastAPI(title="Chat Backend API", version="1.0.0")

# Setup error handling and logging middleware
setup_error_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

logger.info("Application started successfully")

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting uvicorn server")
    uvicorn.run(app, host="0.0.0.0", port=8000)