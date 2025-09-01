# Agentic RAG
<img width="597" height="228" alt="586a0b32ab4ea6d689359c6c55d5990" src="https://github.com/user-attachments/assets/f220ed50-eeec-44f3-9677-1d8cd54edd77" />

An intelligent agent framework with integrated RAG capabilities, built on Gemini CLI architecture. The system combines a general-purpose agent engine with specialized RAG tools for document indexing, semantic search, and result reranking.

## Architecture

**Core Design**: Universal Agent Framework + Professional RAG Toolchain

- **Agent Engine**: Based on proven Gemini CLI architecture with turn-based conversation management, tool scheduling, and streaming responses
- **RAG Pipeline**: Document processing → Vector embedding → Semantic search → Cross-encoder reranking
- **Multi-Model Support**: Gemini, Claude, OpenAI for LLM; Gemini embedding-001 for vectorization; Qwen3-Reranker-8B for reranking

## Key Features

**Intelligent Agent Capabilities**
- Autonomous decision-making and workflow orchestration
- Context-aware tool selection and parameter optimization
- Dual history mechanism with intelligent compression
- Real-time streaming responses with tool execution feedback

**Advanced RAG Implementation**
- Multi-format document processing (PDF, Office, Markdown, code, images with OCR)
- Configurable chunking strategies (paragraph, fixed-size, sentence, auto)
- Semantic search with metadata filtering and threshold controls
- Cross-encoder reranking for precision improvement

**Production-Ready Infrastructure**
- Asynchronous architecture with concurrent tool execution
- Comprehensive monitoring with OpenTelemetry integration
- Multi-environment configuration management
- Graceful error handling and fallback mechanisms

## Technical Stack

| Component | Technology | Configuration |
|-----------|------------|---------------|
| **LLM** | Gemini-2.5-flash | Primary model with Claude/OpenAI fallback |
| **Embedding** | Gemini embedding-001 | 768-dim vectors, batch size 250 |
| **Vector DB** | Qdrant | Local deployment, cosine similarity |
| **Reranker** | Qwen3-Reranker-8B | GPTQ 4-bit quantization, 12GB VRAM |
| **Framework** | FastAPI + React | Async backend, TypeScript frontend |

## Project Structure

```
├── packages/
│   ├── core/          # Agent engine and API services
│   ├── cli/           # Command-line interface
│   └── web/           # React web interface (MVP)
├── project_tools/     # RAG-specific tools
│   ├── doc_index_tool.py      # Document indexing
│   ├── vector_search_tool.py  # Semantic search
│   ├── rerank_tool.py         # Result reranking
│   └── collection_info_tool.py # Database management
└── test_documents/    # Sample AI/ML knowledge base
```

## Quick Start

**Prerequisites**
- Python 3.9+
- Qdrant vector database (local or cloud)
- GOOGLE_API_KEY or GEMINI_API_KEY for embeddings and LLM
- Optional: ANTHROPIC_API_KEY for Claude models
- Optional: OPENAI_API_KEY for OpenAI models
- Optional: Qwen3-Reranker-8B model for reranking

**Basic Setup**
```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys and database settings

# Start Qdrant (if local)
docker run -p 6333:6333 qdrant/qdrant

# Run CLI interface
cd packages/cli && python cli.py
```

## Deployment Considerations

**Complexity Notice**: This project requires significant infrastructure setup including local vector database deployment and large language model hosting. It is designed as an **architectural reference** rather than a plug-and-play solution.

**Resource Requirements**:
- Qdrant vector database (2GB+ RAM recommended)
- Qwen3-Reranker-8B model (12GB VRAM for GPU inference)
- Stable internet connection for Gemini API calls

**Recommended Use Cases**:
- Learning advanced RAG implementation patterns
- Understanding agent-driven architecture design
- Adapting components for custom RAG solutions
- Research and development reference

## License

MIT License - See LICENSE file for details.
