# Project Prompt Configuration

## RAG Tools Usage Guide

You now have three RAG tools, please use them flexibly according to user needs:

### 1. doc_index - Document Indexing Tool
Used to index various content into vector database
- Automatic file type recognition: text, code, PDF, images, etc.
- Intelligent processing options: images can use OCR for text extraction, code can extract structure
- Selectable chunking strategies: paragraph, fixed (fixed size), sentence, auto (automatic)
- Uses Gemini embedding to generate vectors
- Stores to Qdrant vector database

### 2. vector_search - Vector Search Tool
Used for semantic search of relevant content
- Input query text, returns semantically similar document chunks
- Supports specifying collection, return count, similarity threshold
- Supports metadata filtering and custom distance metrics

### 3. rerank - Reranking Tool
Used to optimize search result relevance
- Uses Qwen3-Reranker-8B model for precise relevance calculation
- Reorders search results to improve accuracy
- Supports threshold setting to filter low-relevance content

### 4. collection_info - Collection Information Tool
Used to check vector database status
- View whether specific collection exists and document count
- List all collections and their statistics
- **Check if specific files are already indexed** (check_files parameter)
- **List all indexed files in collection** (list_sources parameter)
- Avoid duplicate indexing of existing documents

## Recommended Usage Workflow

1. **Check Phase**: First use collection_info to check if collection exists and document count
2. **Index Phase**: If collection doesn't exist or is empty, use doc_index to index documents
   - System automatically recognizes file types and selects appropriate processing methods
   - PDFs extract text, images optionally use OCR, code preserves structure
3. **Search Phase**: Use vector_search for initial semantic search (recall)
4. **Rerank Phase**: Strongly recommend always using rerank for reordering, this is a key step in RAG
   - Vector search provides initial recall
   - rerank provides precise relevance ranking
   - Combining both achieves optimal results


