"""
Vector Database Client
Handles Qdrant vector database operations
"""

from typing import List, Dict, Any, Optional, Tuple
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, Range, MatchValue,
    SearchRequest, SearchParams
)
import uuid
from ._rag_config import get_config


class VectorDBClient:
    """
    Qdrant client with flexible initialization
    Supports memory mode, local disk, and remote server
    """
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self._client = None
        self._collections = set()
    
    def _get_client(self) -> QdrantClient:
        """Get or create Qdrant client lazily"""
        if self._client is None:
            if self.config.vector_db_type == "memory":
                # In-memory mode for testing
                self._client = QdrantClient(":memory:")
            elif self.config.qdrant_path:
                # Local disk persistence
                self._client = QdrantClient(path=self.config.qdrant_path)
            else:
                # Remote Qdrant server
                # For local Docker with API key authentication
                self._client = QdrantClient(
                    url=f"http://{self.config.qdrant_host}:{self.config.qdrant_port}",
                    api_key=self.config.qdrant_api_key,
                    timeout=self.config.timeout_seconds
                )
        return self._client
    
    def ensure_collection(self, collection_name: str = None) -> bool:
        """
        Ensure collection exists, create if not
        Returns True if created, False if already exists
        """
        collection_name = collection_name or self.config.default_collection
        
        if collection_name in self._collections:
            return False
        
        client = self._get_client()
        
        try:
            # Check if collection exists
            collections = client.get_collections().collections
            exists = any(c.name == collection_name for c in collections)
            
            if not exists:
                # Create collection with configured settings
                distance_map = {
                    "cosine": Distance.COSINE,
                    "dot": Distance.DOT,
                    "euclidean": Distance.EUCLID
                }
                
                client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=self.config.embedding_dim,
                        distance=distance_map.get(
                            self.config.distance_metric, 
                            Distance.COSINE
                        )
                    )
                )
                self._collections.add(collection_name)
                return True
            
            self._collections.add(collection_name)
            return False
            
        except Exception as e:
            print(f"Error ensuring collection: {e}")
            return False
    
    async def upsert_vectors(
        self,
        vectors: List[List[float]],
        documents: List[str],
        metadata: List[Dict[str, Any]] = None,
        collection_name: str = None,
        ids: List[str] = None
    ) -> int:
        """
        Insert or update vectors with documents
        Returns number of vectors inserted
        """
        collection_name = collection_name or self.config.default_collection
        self.ensure_collection(collection_name)
        
        client = self._get_client()
        
        # Generate IDs if not provided
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in range(len(vectors))]
        
        # Prepare metadata
        if metadata is None:
            metadata = [{}] * len(vectors)
        
        # Add documents to metadata
        for i, meta in enumerate(metadata):
            meta["document"] = documents[i]
        
        # Create points
        points = [
            PointStruct(
                id=ids[i],
                vector=vectors[i],
                payload=metadata[i]
            )
            for i in range(len(vectors))
        ]
        
        try:
            # Batch upsert
            operation_info = client.upsert(
                collection_name=collection_name,
                points=points,
                wait=True
            )
            
            return len(points)
            
        except Exception as e:
            print(f"Error upserting vectors: {e}")
            return 0
    
    async def list_collections(self) -> List[Dict[str, Any]]:
        """
        List all collections in the database
        """
        client = self._get_client()
        collections = client.get_collections()
        
        result = []
        for collection in collections.collections:
            info = client.get_collection(collection.name)
            result.append({
                "name": collection.name,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count
            })
        
        return result
    
    async def get_collection_info(self, collection_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a collection
        """
        client = self._get_client()
        
        try:
            collection = client.get_collection(collection_name)
            return {
                "vectors_count": collection.vectors_count,
                "points_count": collection.points_count,
                "indexed_vectors_count": collection.indexed_vectors_count if hasattr(collection, 'indexed_vectors_count') else collection.vectors_count,
                "status": collection.status
            }
        except Exception:
            return None
    
    async def get_indexed_files(self, collection_name: str) -> List[str]:
        """
        Get list of all unique source files indexed in collection
        """
        client = self._get_client()
        
        try:
            # Scroll through all points to get unique sources
            sources = set()
            offset = None
            limit = 100
            
            while True:
                result = client.scroll(
                    collection_name=collection_name,
                    scroll_filter=None,
                    limit=limit,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False
                )
                
                points, next_offset = result
                
                for point in points:
                    if point.payload and 'source' in point.payload:
                        sources.add(point.payload['source'])
                
                if next_offset is None:
                    break
                offset = next_offset
            
            return list(sources)
            
        except Exception as e:
            print(f"Error getting indexed files: {e}")
            return []
    
    async def search_vectors(
        self,
        query_vector: List[float],
        collection_name: str = None,
        top_k: int = 5,
        filter_dict: Dict[str, Any] = None,
        score_threshold: float = None,
        include_payload: bool = True
    ) -> Dict[str, Any]:
        """
        Search for similar vectors
        Returns documents, scores, and metadata
        """
        collection_name = collection_name or self.config.default_collection
        
        # Ensure collection exists
        if not self.ensure_collection(collection_name):
            client = self._get_client()
        else:
            # Collection was just created, no data yet
            return {
                "documents": [],
                "scores": [],
                "metadata": []
            }
        
        client = self._get_client()
        
        # Build filter if provided
        qdrant_filter = None
        if filter_dict:
            conditions = []
            for key, value in filter_dict.items():
                if isinstance(value, dict):
                    # Range filter
                    if "gte" in value or "lte" in value:
                        conditions.append(
                            FieldCondition(
                                key=key,
                                range=Range(
                                    gte=value.get("gte"),
                                    lte=value.get("lte")
                                )
                            )
                        )
                else:
                    # Exact match
                    conditions.append(
                        FieldCondition(
                            key=key,
                            match=MatchValue(value=value)
                        )
                    )
            
            if conditions:
                qdrant_filter = Filter(must=conditions)
        
        try:
            # Perform search
            results = client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=top_k,
                query_filter=qdrant_filter,
                score_threshold=score_threshold,
                with_payload=include_payload
            )
            
            # Extract results
            documents = []
            scores = []
            metadata = []
            
            for hit in results:
                scores.append(hit.score)
                
                if include_payload and hit.payload:
                    # Extract document from payload
                    doc = hit.payload.pop("document", "")
                    documents.append(doc)
                    metadata.append(hit.payload)
                else:
                    documents.append("")
                    metadata.append({})
            
            return {
                "documents": documents,
                "scores": scores,
                "metadata": metadata
            }
            
        except Exception as e:
            print(f"Error searching vectors: {e}")
            return {
                "documents": [],
                "scores": [],
                "metadata": []
            }
    
    def delete_collection(self, collection_name: str = None) -> bool:
        """Delete a collection"""
        collection_name = collection_name or self.config.default_collection
        
        try:
            client = self._get_client()
            client.delete_collection(collection_name)
            self._collections.discard(collection_name)
            return True
        except Exception as e:
            print(f"Error deleting collection: {e}")
            return False
    
    def get_collection_info(self, collection_name: str = None) -> Dict[str, Any]:
        """Get collection statistics"""
        collection_name = collection_name or self.config.default_collection
        
        try:
            client = self._get_client()
            info = client.get_collection(collection_name)
            
            return {
                "vectors_count": info.vectors_count,
                "indexed_vectors_count": info.indexed_vectors_count,
                "points_count": info.points_count,
                "status": info.status
            }
        except Exception as e:
            print(f"Error getting collection info: {e}")
            return {}


# Singleton instance
_vector_db_client: Optional[VectorDBClient] = None


def get_vector_db_client() -> VectorDBClient:
    """Get or create vector database client singleton"""
    global _vector_db_client
    if _vector_db_client is None:
        _vector_db_client = VectorDBClient()
    return _vector_db_client