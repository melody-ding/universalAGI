import os
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum


class Environment(str, Enum):
    """Application environment types"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Logging level options"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(str, Enum):
    """Logging format options"""
    JSON = "json"
    TEXT = "text"


@dataclass
class DatabaseConfig:
    """Database configuration settings"""
    # RDS Data API settings
    cluster_arn: str
    secret_arn: str
    database_name: str = "postgres"
    
    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        return cls(
            cluster_arn=os.getenv("RDS_CLUSTER_ARN", ""),
            secret_arn=os.getenv("RDS_SECRET_ARN", ""),
            database_name=os.getenv("RDS_DATABASE_NAME", "postgres")
        )


@dataclass
class AWSConfig:
    """AWS service configuration"""
    access_key_id: str
    secret_access_key: str
    region: str
    s3_bucket_name: str
    
    @classmethod
    def from_env(cls) -> "AWSConfig":
        return cls(
            access_key_id=os.getenv("AWS_ACCESS_KEY_ID", ""),
            secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", ""),
            region=os.getenv("AWS_REGION", "us-east-1"),
            s3_bucket_name=os.getenv("S3_BUCKET_NAME", "")
        )


@dataclass
class OpenAIConfig:
    """OpenAI API configuration"""
    api_key: str
    model_name: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: int = 4000
    
    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)
    
    @classmethod
    def from_env(cls) -> "OpenAIConfig":
        return cls(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model_name=os.getenv("OPENAI_MODEL_NAME", "gpt-4o"),
            temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "4000"))
        )


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: LogLevel
    format: LogFormat
    file_path: Optional[str]
    enable_console: bool
    
    @classmethod
    def from_env(cls) -> "LoggingConfig":
        return cls(
            level=LogLevel(os.getenv("LOG_LEVEL", "INFO")),
            format=LogFormat(os.getenv("LOG_FORMAT", "json")),
            file_path=os.getenv("LOG_FILE"),
            enable_console=os.getenv("LOG_CONSOLE", "true").lower() == "true"
        )


@dataclass
class RouterConfig:
    """Configuration for routing between SHORT and LONG paths"""
    weights: dict
    threshold: float
    
    @classmethod
    def default(cls) -> "RouterConfig":
        return cls(
            weights={
                "avg_vec_sim": float(os.getenv("ROUTER_WEIGHT_AVG_VEC_SIM", "0.9")),
                "fts_hit_rate": float(os.getenv("ROUTER_WEIGHT_FTS_HIT_RATE", "0.5")),
                "top_doc_share": float(os.getenv("ROUTER_WEIGHT_TOP_DOC_SHARE", "0.8")),
                "unique_docs": float(os.getenv("ROUTER_WEIGHT_UNIQUE_DOCS", "-0.7")),
                "has_quotes_or_ids": float(os.getenv("ROUTER_WEIGHT_QUOTES_IDS", "-0.1")),
                "has_compare_temporal_conditions": float(os.getenv("ROUTER_WEIGHT_TEMPORAL", "-0.6"))
            },
            threshold=float(os.getenv("ROUTER_THRESHOLD", "0.5"))
        )


@dataclass
class EscalationConfig:
    """Configuration for escalation rules"""
    min_strong_segments: int
    max_distinct_docs: int
    min_avg_vec_sim: float
    min_fts_hit_rate: float
    
    @classmethod
    def default(cls) -> "EscalationConfig":
        return cls(
            min_strong_segments=int(os.getenv("ESCALATION_MIN_STRONG_SEGMENTS", "2")),
            max_distinct_docs=int(os.getenv("ESCALATION_MAX_DISTINCT_DOCS", "4")),
            min_avg_vec_sim=float(os.getenv("ESCALATION_MIN_AVG_VEC_SIM", "0.60")),
            min_fts_hit_rate=float(os.getenv("ESCALATION_MIN_FTS_HIT_RATE", "0.10"))
        )


@dataclass
class AgentConfig:
    """Agent and routing configuration"""
    router: RouterConfig
    escalation: EscalationConfig
    
    # Search parameters
    probe_doc_limit: int = 10
    probe_candidates_per_type: int = 3
    
    # SHORT path parameters
    short_top_docs: int = 15
    short_per_doc: int = 3
    short_vector_limit: int = 20
    short_text_limit: int = 20
    short_alpha: float = 0.6
    
    # LONG path parameters
    long_max_subqueries: int = 3
    long_max_steps: int = 5
    long_budget_tokens: int = 8000
    long_budget_time_sec: int = 30
    
    # Response limits
    max_response_tokens: int = 4000
    max_context_tokens: int = 12000
    max_context_chars: int = 48000
    
    @classmethod
    def default(cls) -> "AgentConfig":
        return cls(
            router=RouterConfig.default(),
            escalation=EscalationConfig.default(),
            probe_doc_limit=int(os.getenv("AGENT_PROBE_DOC_LIMIT", "10")),
            probe_candidates_per_type=int(os.getenv("AGENT_PROBE_CANDIDATES_PER_TYPE", "3")),
            short_top_docs=int(os.getenv("AGENT_SHORT_TOP_DOCS", "15")),
            short_per_doc=int(os.getenv("AGENT_SHORT_PER_DOC", "3")),
            short_vector_limit=int(os.getenv("AGENT_SHORT_VECTOR_LIMIT", "20")),
            short_text_limit=int(os.getenv("AGENT_SHORT_TEXT_LIMIT", "20")),
            short_alpha=float(os.getenv("AGENT_SHORT_ALPHA", "0.6")),
            long_max_subqueries=int(os.getenv("AGENT_LONG_MAX_SUBQUERIES", "3")),
            long_max_steps=int(os.getenv("AGENT_LONG_MAX_STEPS", "5")),
            long_budget_tokens=int(os.getenv("AGENT_LONG_BUDGET_TOKENS", "8000")),
            long_budget_time_sec=int(os.getenv("AGENT_LONG_BUDGET_TIME_SEC", "30")),
            max_response_tokens=int(os.getenv("AGENT_MAX_RESPONSE_TOKENS", "4000")),
            max_context_tokens=int(os.getenv("AGENT_MAX_CONTEXT_TOKENS", "12000")),
            max_context_chars=int(os.getenv("AGENT_MAX_CONTEXT_CHARS", "48000"))
        )


@dataclass
class ServerConfig:
    """Server and API configuration"""
    host: str
    port: int
    allowed_origins: List[str]
    max_conversation_history: int
    cors_allow_credentials: bool
    
    @classmethod
    def from_env(cls) -> "ServerConfig":
        # Handle allowed origins as comma-separated string
        origins_str = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
        allowed_origins = [origin.strip() for origin in origins_str.split(",")]
        
        return cls(
            host=os.getenv("SERVER_HOST", "0.0.0.0"),
            port=int(os.getenv("SERVER_PORT", "8000")),
            allowed_origins=allowed_origins,
            max_conversation_history=int(os.getenv("MAX_CONVERSATION_HISTORY", "5")),
            cors_allow_credentials=os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
        )


@dataclass
class Settings:
    """Main application settings"""
    environment: Environment
    debug: bool
    database: DatabaseConfig
    aws: AWSConfig
    openai: OpenAIConfig
    logging: LoggingConfig
    agent: AgentConfig
    server: ServerConfig
    
    # Legacy properties for backward compatibility
    @property
    def OPENAI_API_KEY(self) -> str:
        return self.openai.api_key
    
    @property
    def MODEL_NAME(self) -> str:
        return self.openai.model_name
    
    @property
    def MODEL_TEMPERATURE(self) -> float:
        return self.openai.temperature
    
    @property
    def ALLOWED_ORIGINS(self) -> List[str]:
        return self.server.allowed_origins
    
    @property
    def MAX_CONVERSATION_HISTORY(self) -> int:
        return self.server.max_conversation_history
    
    @property
    def is_openai_configured(self) -> bool:
        return self.openai.is_configured
    
    def validate(self) -> None:
        """Validate critical configuration"""
        errors = []
        
        if not self.openai.api_key:
            errors.append("OPENAI_API_KEY is required")
        
        if self.environment == Environment.PRODUCTION:
            if not self.database.cluster_arn:
                errors.append("RDS_CLUSTER_ARN is required in production")
            if not self.database.secret_arn:
                errors.append("RDS_SECRET_ARN is required in production")
            if not self.aws.s3_bucket_name:
                errors.append("S3_BUCKET_NAME is required in production")
            if not self.aws.access_key_id or not self.aws.secret_access_key:
                errors.append("AWS credentials are required in production")
        
        if errors:
            raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")
    
    @classmethod
    def from_env(cls) -> "Settings":
        """Create settings from environment variables"""
        settings = cls(
            environment=Environment(os.getenv("ENVIRONMENT", "development")),
            debug=os.getenv("DEBUG", "false").lower() == "true",
            database=DatabaseConfig.from_env(),
            aws=AWSConfig.from_env(),
            openai=OpenAIConfig.from_env(),
            logging=LoggingConfig.from_env(),
            agent=AgentConfig.default(),
            server=ServerConfig.from_env()
        )
        
        # Validate configuration if not in development
        if settings.environment != Environment.DEVELOPMENT:
            settings.validate()
        
        return settings


# Global settings instance
settings = Settings.from_env()