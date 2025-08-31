"""
Gemini Embedding Client
Handles text embedding using Google's Gemini API
"""

import asyncio
from typing import List, Optional
try:
    # Try new API first
    from google import genai
    from google.genai import types
    USE_NEW_API = True
except ImportError:
    # Fallback to old API
    import google.generativeai as genai
    USE_NEW_API = False
from ._rag_config import get_config


class EmbeddingClient:
    """
    Gemini embedding client with retry logic and batching
    """
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self._initialized = False
        self._client = None
    
    def _init_client(self):
        """Initialize Gemini client lazily"""
        if not self._initialized:
            if not self.config.gemini_api_key:
                raise ValueError("GEMINI_API_KEY not configured")
            
            if USE_NEW_API:
                # New API (google.genai)
                import os
                os.environ['GOOGLE_API_KEY'] = self.config.gemini_api_key
                self._client = genai.Client(api_key=self.config.gemini_api_key)
            else:
                # Old API (google.generativeai)
                genai.configure(api_key=self.config.gemini_api_key)
                self._client = None  # Will use genai directly
            self._initialized = True
    
    async def embed_text(self, text: str) -> List[float]:
        """
        Embed a single text
        Returns embedding vector of configured dimension
        """
        self._init_client()
        
        try:
            # Generate embedding with configured dimension
            result = await self._embed_with_retry(text)
            return result
        except Exception as e:
            print(f"Embedding error: {e}")
            # Return zero vector as fallback
            return [0.0] * self.config.embedding_dim
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embed multiple texts with batching
        Handles API limits automatically
        """
        self._init_client()
        
        embeddings = []
        batch_size = min(self.config.batch_size, 250)  # Gemini limit is 250
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = await self._embed_batch_with_retry(batch)
            embeddings.extend(batch_embeddings)
        
        return embeddings
    
    async def _embed_with_retry(self, text: str) -> List[float]:
        """Embed with exponential backoff retry"""
        for attempt in range(self.config.max_retries):
            try:
                if USE_NEW_API:
                    # New API with google.genai
                    result = self._client.models.embed_content(
                        model="models/embedding-001",
                        contents=text,
                        config=types.EmbedContentConfig(
                            task_type="RETRIEVAL_DOCUMENT",
                            output_dimensionality=self.config.embedding_dim
                        ) if 'types' in globals() else None
                    )
                    # Extract embedding from response
                    if hasattr(result, 'embeddings'):
                        emb = result.embeddings[0] if isinstance(result.embeddings, list) else result.embeddings
                        # Handle ContentEmbedding object
                        if hasattr(emb, 'values'):
                            return emb.values
                        return emb
                    return result
                else:
                    # Old API fallback - use genai.embed_content directly
                    result = genai.embed_content(
                        model="models/embedding-001",
                        content=text,
                        task_type="retrieval_document",
                        output_dimensionality=self.config.embedding_dim
                    )
                    if hasattr(result, 'embedding'):
                        emb = result['embedding']
                        # Handle ContentEmbedding object
                        if hasattr(emb, 'values'):
                            return emb.values
                        return emb
                    return result
                    
            except Exception as e:
                if attempt == self.config.max_retries - 1:
                    raise e
                # Exponential backoff
                await asyncio.sleep(2 ** attempt)
    
    async def _embed_batch_with_retry(self, texts: List[str]) -> List[List[float]]:
        """Batch embed with retry logic"""
        for attempt in range(self.config.max_retries):
            try:
                if USE_NEW_API:
                    # New API supports batch embedding directly
                    result = self._client.models.embed_content(
                        model="models/embedding-001",
                        contents=texts,
                        config=types.EmbedContentConfig(
                            task_type="RETRIEVAL_DOCUMENT",
                            output_dimensionality=self.config.embedding_dim
                        ) if 'types' in globals() else None
                    )
                    if hasattr(result, 'embeddings'):
                        # Extract values from ContentEmbedding objects
                        embeddings = []
                        for emb in result.embeddings:
                            if hasattr(emb, 'values'):
                                embeddings.append(emb.values)
                            else:
                                embeddings.append(emb)
                        return embeddings
                    return result
                else:
                    # Old API - embed one by one
                    embeddings = []
                    for text in texts:
                        result = genai.embed_content(
                            model="models/embedding-001",
                            content=text,
                            task_type="retrieval_document",
                            output_dimensionality=self.config.embedding_dim
                        )
                        if hasattr(result, 'embedding'):
                            emb = result['embedding']
                            # Handle ContentEmbedding object
                            if hasattr(emb, 'values'):
                                embeddings.append(emb.values)
                            else:
                                embeddings.append(emb)
                        else:
                            embeddings.append(result)
                    return embeddings
                
            except Exception as e:
                if attempt == self.config.max_retries - 1:
                    raise e
                await asyncio.sleep(2 ** attempt)
    
    def embed_query(self, query: str) -> List[float]:
        """
        Synchronous wrapper for query embedding
        Uses 'retrieval_query' task type for better search results
        """
        self._init_client()
        
        try:
            if USE_NEW_API:
                # New API with google.genai
                result = self._client.models.embed_content(
                    model="models/embedding-001",
                    contents=query,
                    config=types.EmbedContentConfig(
                        task_type="RETRIEVAL_QUERY",  # Optimized for queries
                        output_dimensionality=self.config.embedding_dim
                    ) if 'types' in globals() else None
                )
                # Extract embedding from response
                if hasattr(result, 'embeddings'):
                    emb = result.embeddings[0] if isinstance(result.embeddings, list) else result.embeddings
                    if hasattr(emb, 'values'):
                        return emb.values
                    return emb
                return result
            else:
                # Old API fallback
                result = genai.embed_content(
                    model="models/embedding-001",
                    content=query,
                    task_type="retrieval_query",  # Optimized for queries
                    output_dimensionality=self.config.embedding_dim
                )
                if hasattr(result, 'embedding'):
                    emb = result['embedding']
                    if hasattr(emb, 'values'):
                        return emb.values
                    return emb
                return result
                
        except Exception as e:
            print(f"Query embedding error: {e}")
            return [0.0] * self.config.embedding_dim


# Singleton instance for reuse
_embedding_client: Optional[EmbeddingClient] = None


def get_embedding_client() -> EmbeddingClient:
    """Get or create embedding client singleton"""
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = EmbeddingClient()
    return _embedding_client