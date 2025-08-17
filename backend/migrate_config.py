#!/usr/bin/env python3
"""
Configuration Migration Script

This script helps migrate from the old scattered configuration pattern 
to the new consolidated configuration system.

Usage:
    python migrate_config.py --check     # Check current configuration
    python migrate_config.py --export    # Export current config to .env format
    python migrate_config.py --validate  # Validate current configuration
"""

import argparse
import os
import sys
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

try:
    from config import settings, Environment
    CONFIG_AVAILABLE = True
except ImportError as e:
    print(f"Error importing config: {e}")
    CONFIG_AVAILABLE = False


def check_configuration():
    """Check the current configuration status"""
    print("=== Configuration Status Check ===\n")
    
    if not CONFIG_AVAILABLE:
        print("❌ New configuration system not available")
        return False
    
    print("✅ New configuration system loaded successfully")
    print(f"Environment: {settings.environment.value}")
    print(f"Debug mode: {settings.debug}")
    print(f"Server: {settings.server.host}:{settings.server.port}")
    
    # Check critical configuration
    critical_ok = True
    
    if not settings.openai.api_key:
        print("⚠️  OPENAI_API_KEY not configured")
        critical_ok = False
    else:
        print("✅ OpenAI API key configured")
    
    if settings.environment == Environment.PRODUCTION:
        if not settings.database.cluster_arn:
            print("❌ RDS_CLUSTER_ARN not configured (required in production)")
            critical_ok = False
        else:
            print("✅ Database cluster ARN configured")
            
        if not settings.aws.s3_bucket_name:
            print("❌ S3_BUCKET_NAME not configured (required in production)")
            critical_ok = False
        else:
            print("✅ S3 bucket configured")
    
    if critical_ok:
        print("\n✅ All critical configuration is present")
    else:
        print("\n❌ Some critical configuration is missing")
    
    return critical_ok


def export_configuration():
    """Export current configuration to .env format"""
    if not CONFIG_AVAILABLE:
        print("❌ Configuration system not available")
        return False
    
    env_content = f"""# Generated configuration export
# Environment Configuration
ENVIRONMENT={settings.environment.value}
DEBUG={str(settings.debug).lower()}

# Server Configuration
SERVER_HOST={settings.server.host}
SERVER_PORT={settings.server.port}
ALLOWED_ORIGINS={','.join(settings.server.allowed_origins)}
MAX_CONVERSATION_HISTORY={settings.server.max_conversation_history}
CORS_ALLOW_CREDENTIALS={str(settings.server.cors_allow_credentials).lower()}

# OpenAI Configuration
OPENAI_API_KEY={settings.openai.api_key or 'your_openai_api_key_here'}
OPENAI_MODEL_NAME={settings.openai.model_name}
OPENAI_TEMPERATURE={settings.openai.temperature}
OPENAI_MAX_TOKENS={settings.openai.max_tokens}

# AWS Configuration
AWS_ACCESS_KEY_ID={settings.aws.access_key_id or 'your_aws_access_key_id'}
AWS_SECRET_ACCESS_KEY={settings.aws.secret_access_key or 'your_aws_secret_access_key'}
AWS_REGION={settings.aws.region}
S3_BUCKET_NAME={settings.aws.s3_bucket_name or 'your-s3-bucket-name'}

# Database Configuration
RDS_CLUSTER_ARN={settings.database.cluster_arn or 'your-rds-cluster-arn'}
RDS_SECRET_ARN={settings.database.secret_arn or 'your-rds-secret-arn'}
RDS_DATABASE_NAME={settings.database.database_name}

# Logging Configuration
LOG_LEVEL={settings.logging.level.value}
LOG_FORMAT={settings.logging.format.value}
LOG_FILE={settings.logging.file_path or ''}
LOG_CONSOLE={str(settings.logging.enable_console).lower()}

# Agent Router Configuration
ROUTER_WEIGHT_AVG_VEC_SIM={settings.agent.router.weights.get('avg_vec_sim', 0.9)}
ROUTER_WEIGHT_FTS_HIT_RATE={settings.agent.router.weights.get('fts_hit_rate', 0.5)}
ROUTER_WEIGHT_TOP_DOC_SHARE={settings.agent.router.weights.get('top_doc_share', 0.8)}
ROUTER_WEIGHT_UNIQUE_DOCS={settings.agent.router.weights.get('unique_docs', -0.7)}
ROUTER_WEIGHT_QUOTES_IDS={settings.agent.router.weights.get('has_quotes_or_ids', -0.1)}
ROUTER_WEIGHT_TEMPORAL={settings.agent.router.weights.get('has_compare_temporal_conditions', -0.6)}
ROUTER_THRESHOLD={settings.agent.router.threshold}

# Agent Escalation Configuration
ESCALATION_MIN_STRONG_SEGMENTS={settings.agent.escalation.min_strong_segments}
ESCALATION_MAX_DISTINCT_DOCS={settings.agent.escalation.max_distinct_docs}
ESCALATION_MIN_AVG_VEC_SIM={settings.agent.escalation.min_avg_vec_sim}
ESCALATION_MIN_FTS_HIT_RATE={settings.agent.escalation.min_fts_hit_rate}

# Agent Parameters
AGENT_PROBE_DOC_LIMIT={settings.agent.probe_doc_limit}
AGENT_PROBE_CANDIDATES_PER_TYPE={settings.agent.probe_candidates_per_type}
AGENT_SHORT_TOP_DOCS={settings.agent.short_top_docs}
AGENT_SHORT_PER_DOC={settings.agent.short_per_doc}
AGENT_SHORT_VECTOR_LIMIT={settings.agent.short_vector_limit}
AGENT_SHORT_TEXT_LIMIT={settings.agent.short_text_limit}
AGENT_SHORT_ALPHA={settings.agent.short_alpha}
AGENT_LONG_MAX_SUBQUERIES={settings.agent.long_max_subqueries}
AGENT_LONG_MAX_STEPS={settings.agent.long_max_steps}
AGENT_LONG_BUDGET_TOKENS={settings.agent.long_budget_tokens}
AGENT_LONG_BUDGET_TIME_SEC={settings.agent.long_budget_time_sec}
AGENT_MAX_RESPONSE_TOKENS={settings.agent.max_response_tokens}
AGENT_MAX_CONTEXT_TOKENS={settings.agent.max_context_tokens}
AGENT_MAX_CONTEXT_CHARS={settings.agent.max_context_chars}
"""
    
    output_file = backend_dir / "current_config.env"
    with open(output_file, "w") as f:
        f.write(env_content)
    
    print(f"✅ Configuration exported to {output_file}")
    print("You can use this file as a template for your deployment")
    return True


def validate_configuration():
    """Validate the current configuration"""
    print("=== Configuration Validation ===\n")
    
    if not CONFIG_AVAILABLE:
        print("❌ Configuration system not available")
        return False
    
    try:
        settings.validate()
        print("✅ Configuration validation passed")
        return True
    except ValueError as e:
        print(f"❌ Configuration validation failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Configuration migration utilities")
    parser.add_argument("--check", action="store_true", help="Check current configuration")
    parser.add_argument("--export", action="store_true", help="Export configuration to .env format")
    parser.add_argument("--validate", action="store_true", help="Validate configuration")
    
    args = parser.parse_args()
    
    if not any([args.check, args.export, args.validate]):
        parser.print_help()
        return
    
    success = True
    
    if args.check:
        success &= check_configuration()
        print()
    
    if args.validate:
        success &= validate_configuration()
        print()
    
    if args.export:
        success &= export_configuration()
        print()
    
    if not success:
        print("❌ Some operations failed")
        sys.exit(1)
    else:
        print("✅ All operations completed successfully")


if __name__ == "__main__":
    main()
