"""
Document Index Tool for Agentic RAG
Indexes documents into vector database for semantic search
"""

from typing import Dict, Any, Optional, List
from dbrheo.tools.base import Tool
from dbrheo.types.tool_types import ToolResult
from dbrheo.types.core_types import AbortSignal
import json
import hashlib
import asyncio
from pathlib import Path
from datetime import datetime

# Import RAG components (private modules)
from ._rag_config import get_config
from ._embedding_client import get_embedding_client
from ._vector_db_client import get_vector_db_client
from ._content_processor import get_content_processor


class DocIndexTool(Tool):
    """
    Tool to index documents into vector database
    Handles document loading, chunking, embedding and storage
    """
    
    def __init__(self, config, i18n=None):
        super().__init__(
            name="doc_index",
            display_name="Document Indexer",
            description="Index documents into vector database for semantic search. Supports file/text/url sources with flexible chunking strategies.",
            parameter_schema={
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "Document source: file path, text content, or URL"
                    },
                    "source_type": {
                        "type": "string",
                        "enum": ["file", "text", "url"],
                        "description": "Type of source: 'file', 'text', or 'url'"
                    },
                    "collection_name": {
                        "type": "string",
                        "default": "default",
                        "description": "Vector database collection name"
                    },
                    "chunk_strategy": {
                        "type": "string",
                        "enum": ["auto", "paragraph", "fixed", "sentence"],
                        "default": "auto",
                        "description": "Chunking strategy: auto, paragraph, fixed size, or sentence"
                    },
                    "chunk_size": {
                        "type": "integer",
                        "default": 500,
                        "description": "Chunk size in characters (only for 'fixed' strategy)"
                    },
                    "chunk_overlap": {
                        "type": "integer",
                        "default": 50,
                        "description": "Overlap between chunks in characters"
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Additional metadata to store with documents"
                    },
                    "process_options": {
                        "type": "object",
                        "description": "Processing options: use_ocr (for images), extract_structure (for code/markdown), encoding (text encoding)",
                        "properties": {
                            "use_ocr": {"type": "boolean", "default": False},
                            "extract_structure": {"type": "boolean", "default": False},
                            "encoding": {"type": "string", "default": "utf-8"}
                        }
                    }
                },
                "required": ["source", "source_type"]
            },
            is_output_markdown=True,
            can_update_output=True
        )
        self.config = config
        self._init_components()
    
    def _init_components(self):
        """Initialize embedding model and vector database"""
        self.rag_config = get_config()
        self.embedding_client = get_embedding_client()
        self.vector_db = get_vector_db_client()
        self.content_processor = get_content_processor()
    
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """Validate parameters"""
        source_type = params.get("source_type")
        source = params.get("source")
        
        if source_type == "file":
            # Check if file exists
            if not Path(source).exists():
                return f"File not found: {source}"
        elif source_type == "url":
            # Basic URL validation
            if not source.startswith(("http://", "https://")):
                return "URL must start with http:// or https://"
        elif source_type == "text":
            # Check text is not empty
            if not source or not source.strip():
                return "Text content cannot be empty"
        
        # Validate chunk_size
        chunk_size = params.get("chunk_size", 500)
        if chunk_size < 100:
            return "Chunk size must be at least 100 characters"
        
        return None
    
    def get_description(self, params: Dict[str, Any]) -> str:
        """Get execution description"""
        source_type = params.get("source_type")
        collection = params.get("collection_name", "default")
        
        if source_type == "file":
            source = Path(params.get("source")).name
            return f"Indexing file '{source}' into collection '{collection}'"
        elif source_type == "url":
            return f"Indexing URL content into collection '{collection}'"
        else:
            return f"Indexing text content into collection '{collection}'"
    
    async def should_confirm_execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal
    ) -> bool:
        """No confirmation needed for indexing"""
        return False
    
    async def execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal,
        update_output: Optional[Any] = None
    ) -> ToolResult:
        """Execute document indexing"""
        try:
            # 1. Load content
            if update_output:
                update_output("Loading document content...")
            content = await self._load_content(params)
            
            # 2. Split into chunks
            if update_output:
                update_output("Splitting document into chunks...")
            chunks = self._split_chunks(content, params)
            
            # 3. Generate embeddings
            if update_output:
                update_output(f"Generating embeddings for {len(chunks)} chunks...")
            embeddings = await self._generate_embeddings(chunks)
            
            # 4. Store in vector database
            if update_output:
                update_output("Storing vectors in database...")
            doc_id = await self._store_vectors(chunks, embeddings, params)
            
            # Prepare result
            result = {
                "indexed_chunks": len(chunks),
                "collection_name": params.get("collection_name", "default"),
                "doc_id": doc_id,
                "status": "success",
                "details": self._get_indexing_details(chunks, params)
            }
            
            return ToolResult(
                summary=f"Successfully indexed {len(chunks)} chunks",
                llm_content=json.dumps(result, indent=2),
                return_display=self._format_display(result),
                error=None
            )
            
        except Exception as e:
            return ToolResult(
                summary=f"Indexing failed: {str(e)}",
                llm_content="",
                return_display=f"Error during indexing: {str(e)}",
                error=str(e)
            )
    
    async def _load_content(self, params: Dict[str, Any]) -> str:
        """Load content from source using flexible processor"""
        source_type = params.get("source_type")
        source = params.get("source")
        
        # Use content processor for flexible file handling
        process_options = params.get("process_options", {})
        content, metadata = await self.content_processor.process_content(
            source=source,
            source_type=source_type,
            **process_options
        )
        
        # Store file metadata for indexing
        if "metadata" not in params:
            params["metadata"] = {}
        params["metadata"].update(metadata)
        
        return content
    
    def _split_chunks(self, content: str, params: Dict[str, Any]) -> List[str]:
        """Split content into chunks based on strategy"""
        strategy = params.get("chunk_strategy", "auto")
        chunk_size = params.get("chunk_size", 500)
        overlap = params.get("chunk_overlap", 50)
        
        if strategy == "auto":
            # Simple heuristic: use paragraph if has double newlines
            if "\n\n" in content:
                strategy = "paragraph"
            else:
                strategy = "fixed"
        
        chunks = []
        
        if strategy == "paragraph":
            # Split by double newline
            paragraphs = content.split("\n\n")
            chunks = [p.strip() for p in paragraphs if p.strip()]
        elif strategy == "fixed":
            # Fixed size chunks with overlap
            text_len = len(content)
            start = 0
            while start < text_len:
                end = min(start + chunk_size, text_len)
                chunks.append(content[start:end])
                start = end - overlap if end < text_len else text_len
        elif strategy == "sentence":
            # Simple sentence splitting
            import re
            sentences = re.split(r'[.!?]\s+', content)
            current_chunk = ""
            for sentence in sentences:
                if len(current_chunk) + len(sentence) < chunk_size:
                    current_chunk += sentence + ". "
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = sentence + ". "
            if current_chunk:
                chunks.append(current_chunk.strip())
        
        return chunks if chunks else [content]
    
    async def _generate_embeddings(self, chunks: List[str]) -> List[List[float]]:
        """Generate embeddings for chunks"""
        # Use Gemini embedding client
        embeddings = await self.embedding_client.embed_batch(chunks)
        return embeddings
    
    async def _store_vectors(
        self, 
        chunks: List[str], 
        embeddings: List[List[float]], 
        params: Dict[str, Any]
    ) -> str:
        """Store vectors in database"""
        collection_name = params.get("collection_name", "default")
        base_metadata = params.get("metadata", {})
        
        # Generate document ID
        doc_content = "".join(chunks)
        doc_id = hashlib.md5(doc_content.encode()).hexdigest()[:12]
        
        # Prepare metadata for each chunk
        metadata_list = []
        for i, chunk in enumerate(chunks):
            chunk_metadata = base_metadata.copy()
            chunk_metadata.update({
                "doc_id": doc_id,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "timestamp": datetime.now().isoformat(),
                "source": params.get("source"),
                "source_type": params.get("source_type")
            })
            metadata_list.append(chunk_metadata)
        
        # Store in vector database
        count = await self.vector_db.upsert_vectors(
            vectors=embeddings,
            documents=chunks,
            metadata=metadata_list,
            collection_name=collection_name
        )
        
        return doc_id
    
    def _get_indexing_details(self, chunks: List[str], params: Dict[str, Any]) -> str:
        """Get indexing details for result"""
        strategy = params.get("chunk_strategy", "auto")
        avg_size = sum(len(c) for c in chunks) // len(chunks) if chunks else 0
        
        return f"Used {strategy} strategy, average chunk size {avg_size} chars"
    
    def _format_display(self, result: Dict[str, Any]) -> str:
        """Format result for display"""
        return f"""**Document Indexing Complete**

- **Chunks Indexed:** {result['indexed_chunks']}
- **Collection:** {result['collection_name']}
- **Document ID:** {result['doc_id']}
- **Details:** {result['details']}
"""


# Export the tool class for auto-registration
__all__ = ['DocIndexTool']