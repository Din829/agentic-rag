"""
Collection Info Tool for Agentic RAG
Check vector database collections and statistics
"""

from typing import Dict, Any, Optional
from dbrheo.tools.base import Tool
from dbrheo.types.tool_types import ToolResult
from dbrheo.types.core_types import AbortSignal
import json

# Import vector db client
from ._rag_config import get_config
from ._vector_db_client import get_vector_db_client


class CollectionInfoTool(Tool):
    """
    Tool to check vector database collection information
    """
    
    def __init__(self, config, i18n=None):
        super().__init__(
            name="collection_info",
            display_name="Collection Info",
            description="Check vector database collections, document counts, and indexed status. Use this before indexing to avoid duplicates.",
            parameter_schema={
                "type": "object",
                "properties": {
                    "collection": {
                        "type": "string",
                        "default": "default",
                        "description": "Collection name to check"
                    },
                    "list_all": {
                        "type": "boolean",
                        "default": False,
                        "description": "List all collections in database"
                    },
                    "check_files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of file paths to check if indexed"
                    },
                    "list_sources": {
                        "type": "boolean",
                        "default": False,
                        "description": "List all unique source files in collection"
                    }
                },
                "required": []
            },
            is_output_markdown=True
        )
        self.config = config
        self.rag_config = get_config()
        self.vector_client = None
    
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """Validate parameters"""
        return None
    
    def get_description(self, params: Dict[str, Any]) -> str:
        """Get execution description"""
        if params.get("list_all"):
            return "Listing all collections in vector database"
        elif params.get("check_files"):
            return f"Checking if files are indexed in '{params.get('collection', 'default')}'"
        elif params.get("list_sources"):
            return f"Listing all source files in '{params.get('collection', 'default')}'"
        return f"Checking collection '{params.get('collection', 'default')}' info"
    
    async def should_confirm_execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal
    ) -> bool:
        """No confirmation needed for read-only operation"""
        return False
    
    async def execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal,
        update_output: Optional[Any] = None
    ) -> ToolResult:
        """Check collection information"""
        try:
            # Initialize vector client
            if self.vector_client is None:
                self.vector_client = get_vector_db_client()
            
            if params.get("list_all", False):
                # List all collections
                collections = await self.vector_client.list_collections()
                
                result = {
                    "collections": collections,
                    "total_count": len(collections)
                }
                
                display = "**Vector Database Collections**\n\n"
                for col in collections:
                    display += f"- {col['name']}: {col.get('vectors_count', 0)} vectors\n"
                
            elif params.get("check_files"):
                # Check if specific files are indexed
                collection_name = params.get("collection", "default")
                files_to_check = params.get("check_files", [])
                
                indexed_files = await self.vector_client.get_indexed_files(collection_name)
                
                result = {
                    "collection": collection_name,
                    "checked_files": {},
                    "total_indexed": len(indexed_files)
                }
                
                display = f"**File Index Status in '{collection_name}'**\n\n"
                
                for file_path in files_to_check:
                    # Normalize path for comparison
                    normalized = file_path.replace('\\', '/').lower()
                    is_indexed = any(normalized in f.replace('\\', '/').lower() for f in indexed_files)
                    result["checked_files"][file_path] = is_indexed
                    status = "✓ Indexed" if is_indexed else "✗ Not indexed"
                    display += f"- {file_path}: {status}\n"
                
                display += f"\nTotal files in collection: {len(indexed_files)}"
                
            elif params.get("list_sources"):
                # List all unique source files
                collection_name = params.get("collection", "default")
                
                sources = await self.vector_client.get_indexed_files(collection_name)
                
                result = {
                    "collection": collection_name,
                    "source_files": sources,
                    "total_count": len(sources)
                }
                
                display = f"**Indexed Files in '{collection_name}'**\n\n"
                if sources:
                    for source in sorted(sources):
                        display += f"- {source}\n"
                else:
                    display += "No files indexed yet."
                    
            else:
                # Check specific collection
                collection_name = params.get("collection", "default")
                
                # Get collection info
                info = await self.vector_client.get_collection_info(collection_name)
                
                if info:
                    result = {
                        "collection": collection_name,
                        "exists": True,
                        "vectors_count": info.get("vectors_count", 0),
                        "points_count": info.get("points_count", 0),
                        "indexed_vectors_count": info.get("indexed_vectors_count", 0),
                        "status": "ready" if info.get("vectors_count", 0) > 0 else "empty"
                    }
                    
                    display = f"**Collection: {collection_name}**\n\n"
                    display += f"- Status: {result['status']}\n"
                    display += f"- Documents: {result['points_count']}\n"
                    display += f"- Vectors: {result['vectors_count']}\n"
                    display += f"- Indexed: {result['indexed_vectors_count']}\n"
                else:
                    result = {
                        "collection": collection_name,
                        "exists": False,
                        "status": "not_found"
                    }
                    
                    display = f"Collection '{collection_name}' does not exist yet.\n"
                    display += "Use doc_index to create and populate it."
            
            return ToolResult(
                summary=f"Collection info retrieved",
                llm_content=json.dumps(result, indent=2),
                return_display=display,
                error=None
            )
            
        except Exception as e:
            return ToolResult(
                summary=f"Failed to get collection info",
                llm_content="",
                return_display=f"Error: {str(e)}",
                error=str(e)
            )


# Export the tool class
__all__ = ['CollectionInfoTool']