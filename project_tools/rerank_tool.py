"""
Rerank Tool for Agentic RAG
Reranks search results for better relevance using cross-encoder
"""

from typing import Dict, Any, Optional, List
from dbrheo.tools.base import Tool
from dbrheo.types.tool_types import ToolResult
from dbrheo.types.core_types import AbortSignal
import json
import asyncio

# Import reranker client
from ._rag_config import get_config
from ._reranker_client import get_reranker_client


class RerankTool(Tool):
    """
    Tool to rerank documents for better relevance
    Uses cross-encoder model for precise relevance scoring
    """
    
    def __init__(self, config, i18n=None):
        super().__init__(
            name="rerank",
            display_name="Document Reranker",
            description="Rerank documents using cross-encoder for precise relevance. Improves search result quality by computing exact query-document similarity.",
            parameter_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Original query for reranking"
                    },
                    "documents": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of documents to rerank"
                    },
                    "top_k": {
                        "type": "integer",
                        "default": 3,
                        "minimum": 1,
                        "maximum": 10,
                        "description": "Number of top documents to return"
                    },
                    "threshold": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "description": "Minimum relevance score threshold"
                    },
                    "return_scores": {
                        "type": "boolean",
                        "default": True,
                        "description": "Whether to return relevance scores"
                    }
                },
                "required": ["query", "documents"]
            },
            is_output_markdown=True,
            can_update_output=True
        )
        self.config = config
        self.rag_config = get_config()
        self.reranker_client = None
    
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """Validate reranking parameters"""
        query = params.get("query")
        documents = params.get("documents", [])
        
        if not query or not query.strip():
            return "Query cannot be empty"
        
        if not documents:
            return "No documents provided for reranking"
        
        if len(documents) > 100:
            return "Too many documents (max 100)"
        
        top_k = params.get("top_k", 3)
        if top_k > len(documents):
            params["top_k"] = len(documents)  # Adjust silently
        
        return None
    
    def get_description(self, params: Dict[str, Any]) -> str:
        """Get execution description"""
        num_docs = len(params.get("documents", []))
        top_k = params.get("top_k", 3)
        
        return f"Reranking {num_docs} documents to get top {top_k}"
    
    async def should_confirm_execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal
    ) -> bool:
        """No confirmation needed for reranking"""
        return False
    
    async def execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal,
        update_output: Optional[Any] = None
    ) -> ToolResult:
        """Execute document reranking"""
        try:
            query = params.get("query")
            documents = params.get("documents", [])
            top_k = min(params.get("top_k", 3), len(documents))
            threshold = params.get("threshold")
            
            # Check if reranking is configured
            if not self._is_reranking_available():
                # Fallback: return original order
                return self._fallback_response(documents, top_k)
            
            # Initialize reranker client if needed
            if self.reranker_client is None:
                if update_output:
                    update_output("Initializing reranker...")
                self.reranker_client = get_reranker_client()
            
            # Perform reranking
            if update_output:
                update_output(f"Computing relevance scores for {len(documents)} documents...")
            
            reranked_results = await self._rerank_documents(
                query,
                documents,
                top_k,
                threshold
            )
            
            # Format results
            result = self._format_results(
                reranked_results,
                params.get("return_scores", True)
            )
            
            return ToolResult(
                summary=f"Reranked to top {len(result['documents'])} documents",
                llm_content=json.dumps(result, indent=2),
                return_display=self._format_display(result),
                error=None
            )
            
        except Exception as e:
            return ToolResult(
                summary=f"Reranking failed: {str(e)}",
                llm_content="",
                return_display=f"Error during reranking: {str(e)}",
                error=str(e)
            )
    
    def _is_reranking_available(self) -> bool:
        """Check if reranking model is available"""
        return self.rag_config.use_reranker and self.rag_config.reranker_model_path
    
    def _fallback_response(self, documents: List[str], top_k: int) -> ToolResult:
        """Fallback response when reranking is not available"""
        result = {
            "documents": documents[:top_k],
            "scores": None,
            "filtered_count": 0,
            "note": "Reranking model not available, returning original order"
        }
        
        return ToolResult(
            summary=f"Returned top {len(result['documents'])} documents (no reranking)",
            llm_content=json.dumps(result, indent=2),
            return_display="**Note:** Reranking model not available, returning documents in original order.",
            error=None
        )
    
    async def _rerank_documents(
        self,
        query: str,
        documents: List[str],
        top_k: int,
        threshold: Optional[float]
    ) -> Dict[str, Any]:
        """Perform actual reranking using Qwen3-Reranker-8B"""
        # Run reranking in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        
        # Call the synchronous reranker in a thread
        doc_scores = await loop.run_in_executor(
            None,
            self.reranker_client.rerank,
            query,
            documents,
            top_k,
            threshold
        )
        
        # Separate documents and scores
        if doc_scores:
            reranked_documents = [doc for doc, _ in doc_scores]
            reranked_scores = [score for _, score in doc_scores]
        else:
            reranked_documents = []
            reranked_scores = []
        
        # Calculate filtered count
        filtered_count = len(documents) - len(reranked_documents)
        
        return {
            "documents": reranked_documents,
            "scores": reranked_scores,
            "filtered_count": filtered_count
        }
    
    def _format_results(
        self,
        reranked_results: Dict[str, Any],
        return_scores: bool
    ) -> Dict[str, Any]:
        """Format reranking results"""
        result = {
            "documents": reranked_results["documents"],
            "filtered_count": reranked_results.get("filtered_count", 0)
        }
        
        if return_scores:
            result["scores"] = reranked_results["scores"]
        
        return result
    
    def _format_display(self, result: Dict[str, Any]) -> str:
        """Format results for display"""
        display = "**Reranked Documents**\n\n"
        
        documents = result.get("documents", [])
        scores = result.get("scores", [])
        filtered = result.get("filtered_count", 0)
        
        if filtered > 0:
            display += f"*Note: {filtered} documents filtered by threshold*\n\n"
        
        for i, doc in enumerate(documents):
            display += f"### Rank {i + 1}"
            
            # Add score if available
            if scores and i < len(scores):
                display += f" (Relevance: {scores[i]:.3f})"
            
            display += "\n\n"
            
            # Add document content (truncate if too long)
            if len(doc) > 500:
                display += doc[:497] + "...\n\n"
            else:
                display += doc + "\n\n"
            
            if i < len(documents) - 1:
                display += "---\n\n"
        
        return display


# Export the tool class for auto-registration
__all__ = ['RerankTool']