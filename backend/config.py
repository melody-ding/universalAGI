import os
from typing import List

class Settings:
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]
    MODEL_NAME: str = "gpt-4o"
    MODEL_TEMPERATURE: float = 0.7
    MAX_CONVERSATION_HISTORY: int = 5
    
    @property
    def is_openai_configured(self) -> bool:
        return bool(self.OPENAI_API_KEY)

settings = Settings()