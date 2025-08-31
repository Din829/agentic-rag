"""
RAG Configuration Module
Centralized configuration for Agentic RAG tools
"""

import os
from typing import Optional
from dataclasses import dataclass


@dataclass
class RAGConfig:
    """
    RAG configuration with environment variable support
    Minimal and flexible design - no hardcoded values
    """
    
    # Gemini Embedding Configuration
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    embedding_model: str = "models/embedding-001"  # Gemini-embedding-001 model
    embedding_dim: int = int(os.getenv("RAG_EMBEDDING_DIM", "768"))  # 768/1536/3072
    
    # Vector Database Configuration
    vector_db_type: str = os.getenv("RAG_VECTOR_DB", "qdrant")  # qdrant/memory
    qdrant_host: str = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port: int = int(os.getenv("QDRANT_PORT", "6333"))
    qdrant_api_key: Optional[str] = os.getenv("QDRANT_API_KEY")  # For cloud
    qdrant_path: Optional[str] = os.getenv("QDRANT_PATH")  # For local disk
    
    # Collection Configuration
    default_collection: str = os.getenv("RAG_DEFAULT_COLLECTION", "default")
    distance_metric: str = os.getenv("RAG_DISTANCE_METRIC", "cosine")  # cosine/dot/euclidean
    
    # Reranker Configuration (for future use)
    use_reranker: bool = os.getenv("RAG_USE_RERANKER", "false").lower() == "true"
    reranker_model_path: Optional[str] = os.getenv("RERANKER_MODEL_PATH")
    
    # Performance Settings
    batch_size: int = int(os.getenv("RAG_BATCH_SIZE", "10"))
    max_retries: int = int(os.getenv("RAG_MAX_RETRIES", "3"))
    timeout_seconds: int = int(os.getenv("RAG_TIMEOUT", "30"))
    
    def validate(self) -> Optional[str]:
        """Validate configuration"""
        if self.vector_db_type == "qdrant" and not self.gemini_api_key:
            return "GEMINI_API_KEY environment variable is required"
        
        if self.embedding_dim not in [768, 1536, 3072]:
            return "embedding_dim must be 768, 1536, or 3072"
        
        return None


# Singleton instance
_config: Optional[RAGConfig] = None


def get_config() -> RAGConfig:
    """Get or create RAG configuration singleton"""
    global _config
    if _config is None:
        _config = RAGConfig()
        # Validate on first load
        error = _config.validate()
        if error:
            print(f"Warning: RAG Config - {error}")
    return _config


def reset_config():
    """Reset configuration (mainly for testing)"""
    global _config
    _config = None