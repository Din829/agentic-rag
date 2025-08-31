"""
Vector Search Tool for Agentic RAG
Performs semantic search in vector database
"""

from typing import Dict, Any, Optional, List
from dbrheo.tools.base import Tool
from dbrheo.types.tool_types import ToolResult
from dbrheo.types.core_types import AbortSignal
import json
import asyncio

# Import RAG components (private modules)
from ._rag_config import get_config
from ._embedding_client import get_embedding_client
from ._vector_db_client import get_vector_db_client


class VectorSearchTool(Tool):
    """
    Tool to search documents using vector similarity
    Returns semantically similar documents from vector database
    """
    
    def __init__(self, config, i18n=None):
        super().__init__(
            name="vector_search",
            display_name="Vector Search",
            description="Search for semantically similar documents in vector database. Returns ranked results with similarity scores.",
            parameter_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query text"
                    },
                    "collection_name": {
                        "type": "string",
                        "default": "default",
                        "description": "Vector collection to search in"
                    },
                    "top_k": {
                        "type": "integer",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 20,
                        "description": "Number of results to return"
                    },
                    "filter": {
                        "type": "object",
                        "description": "Metadata filters (e.g., {'source': 'doc.md', 'date': '2024'})"
                    },
                    "include_metadata": {
                        "type": "boolean",
                        "default": True,
                        "description": "Whether to include metadata in results"
                    },
                    "score_threshold": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "description": "Minimum similarity score threshold"
                    }
                },
                "required": ["query"]
            },
            is_output_markdown=True,
            can_update_output=False
        )
        self.config = config
        self._init_components()
    
    def _init_components(self):
        """Initialize embedding model and vector database client"""
        self.rag_config = get_config()
        self.embedding_client = get_embedding_client()
        self.vector_db = get_vector_db_client()
    
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """Validate search parameters"""
        query = params.get("query")
        
        if not query or not query.strip():
            return "Query cannot be empty"
        
        top_k = params.get("top_k", 5)
        if top_k < 1 or top_k > 20:
            return "top_k must be between 1 and 20"
        
        threshold = params.get("score_threshold")
        if threshold is not None and (threshold < 0 or threshold > 1):
            return "score_threshold must be between 0 and 1"
        
        return None
    
    def get_description(self, params: Dict[str, Any]) -> str:
        """Get execution description"""
        query = params.get("query", "")
        collection = params.get("collection_name", "default")
        top_k = params.get("top_k", 5)
        
        # Truncate long queries for display
        if len(query) > 50:
            query = query[:47] + "..."
        
        return f"Searching '{query}' in collection '{collection}' (top {top_k})"
    
    async def should_confirm_execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal
    ) -> bool:
        """No confirmation needed for search"""
        return False
    
    async def execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal,
        update_output: Optional[Any] = None
    ) -> ToolResult:
        """Execute vector search"""
        try:
            query = params.get("query")
            collection_name = params.get("collection_name", "default")
            top_k = params.get("top_k", 5)
            
            # 1. Generate query embedding
            query_embedding = await self._embed_query(query)
            
            # 2. Search in vector database
            search_results = await self._search_vectors(
                query_embedding,
                collection_name,
                top_k,
                params.get("filter"),
                params.get("score_threshold")
            )
            
            # 3. Format results
            formatted_results = self._format_results(
                search_results,
                params.get("include_metadata", True)
            )
            
            # Check if results are empty
            if not formatted_results["documents"]:
                return ToolResult(
                    summary="No matching documents found",
                    llm_content=json.dumps(formatted_results, indent=2),
                    return_display="No documents found matching your query.",
                    error=None
                )
            
            return ToolResult(
                summary=f"Found {len(formatted_results['documents'])} relevant documents",
                llm_content=json.dumps(formatted_results, indent=2),
                return_display=self._format_display(formatted_results),
                error=None
            )
            
        except Exception as e:
            return ToolResult(
                summary=f"Search failed: {str(e)}",
                llm_content="",
                return_display=f"Error during search: {str(e)}",
                error=str(e)
            )
    
    async def _embed_query(self, query: str) -> List[float]:
        """Generate embedding for query"""
        # Use synchronous method for query embedding
        # Uses 'retrieval_query' task type for better results
        embedding = self.embedding_client.embed_query(query)
        return embedding
    
    async def _search_vectors(
        self,
        query_embedding: List[float],
        collection_name: str,
        top_k: int,
        filter_dict: Optional[Dict[str, Any]],
        score_threshold: Optional[float]
    ) -> Dict[str, Any]:
        """Search in vector database"""
        # Search using Qdrant client
        results = await self.vector_db.search_vectors(
            query_vector=query_embedding,
            collection_name=collection_name,
            top_k=top_k,
            filter_dict=filter_dict,
            score_threshold=score_threshold,
            include_payload=True
        )
        
        return results
    
    def _format_results(
        self,
        search_results: Dict[str, Any],
        include_metadata: bool
    ) -> Dict[str, Any]:
        """Format search results"""
        formatted = {
            "documents": search_results.get("documents", []),
            "scores": search_results.get("scores", []),
            "query_used": search_results.get("query", "")  # Original query
        }
        
        if include_metadata:
            formatted["metadata"] = search_results.get("metadata", [])
        
        return formatted
    
    def _format_display(self, results: Dict[str, Any]) -> str:
        """Format results for display"""
        display = "**Search Results**\n\n"
        
        documents = results.get("documents", [])
        scores = results.get("scores", [])
        metadata = results.get("metadata", [])
        
        for i, doc in enumerate(documents):
            display += f"### Result {i + 1}"
            
            # Add score if available
            if i < len(scores):
                display += f" (Score: {scores[i]:.3f})"
            
            display += "\n\n"
            
            # Add metadata if available
            if metadata and i < len(metadata):
                meta = metadata[i]
                if meta:
                    display += f"*Source: {meta.get('source', 'Unknown')}*\n\n"
            
            # Add document content (truncate if too long)
            if len(doc) > 500:
                display += doc[:497] + "...\n\n"
            else:
                display += doc + "\n\n"
            
            display += "---\n\n"
        
        return display.rstrip("---\n\n")


# Export the tool class for auto-registration
__all__ = ['VectorSearchTool']