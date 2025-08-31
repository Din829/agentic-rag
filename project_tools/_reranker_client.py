"""
Qwen3-Reranker-8B Client
Handles document reranking using local Qwen3 model
"""

import torch
from typing import List, Tuple, Optional
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import warnings
warnings.filterwarnings("ignore")

from ._rag_config import get_config


class RerankerClient:
    """
    Qwen3-Reranker-8B client for document reranking
    Uses INT8 quantization for 3080Ti compatibility
    """
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self._model = None
        self._tokenizer = None
        self._device = None
        self._initialized = False
    
    def _init_model(self):
        """Lazy load the reranker model"""
        if self._initialized:
            return
        
        if not self.config.use_reranker:
            return
        
        if not self.config.reranker_model_path:
            print("Warning: RERANKER_MODEL_PATH not configured")
            return
        
        try:
            print("Loading Qwen3-Reranker-8B model...")
            
            # Determine device
            if torch.cuda.is_available():
                self._device = torch.device("cuda")
                print(f"Using GPU: {torch.cuda.get_device_name(0)}")
            else:
                self._device = torch.device("cpu")
                print("Using CPU (will be slower)")
            
            # Load tokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.config.reranker_model_path,
                trust_remote_code=True
            )
            
            # Disable torch compile to avoid Triton requirement
            import os
            os.environ["TORCH_COMPILE_DISABLE"] = "1"
            os.environ["TORCHDYNAMO_DISABLE"] = "1"
            
            # Load GPTQ quantized model (already quantized, no need for BitsAndBytes)
            if self._device.type == "cuda":
                # Load GPTQ model directly
                self._model = AutoModelForSequenceClassification.from_pretrained(
                    self.config.reranker_model_path,
                    device_map="auto",
                    trust_remote_code=True,
                    torch_dtype=torch.float16  # Use FP16 for efficiency
                )
                print("GPTQ model loaded on GPU")
            else:
                # CPU loading
                self._model = AutoModelForSequenceClassification.from_pretrained(
                    self.config.reranker_model_path,
                    device_map="cpu",
                    trust_remote_code=True
                )
                print("Model loaded on CPU")
            
            self._model.eval()
            self._initialized = True
            print("Qwen3-Reranker-8B ready!")
            
        except Exception as e:
            print(f"Failed to load reranker model: {e}")
            self._initialized = False
    
    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: int = 3,
        threshold: Optional[float] = None
    ) -> List[Tuple[str, float]]:
        """
        Rerank documents based on query relevance
        
        Args:
            query: Search query
            documents: List of documents to rerank
            top_k: Number of top documents to return
            threshold: Minimum score threshold
        
        Returns:
            List of (document, score) tuples, sorted by relevance
        """
        if not self.config.use_reranker:
            # Return original order if reranker is disabled
            return [(doc, 1.0) for doc in documents[:top_k]]
        
        # Initialize model if needed
        if not self._initialized:
            self._init_model()
        
        if not self._initialized or self._model is None:
            # Fallback if model loading failed
            print("Warning: Reranker not available, returning original order")
            return [(doc, 1.0) for doc in documents[:top_k]]
        
        try:
            # Prepare query-document pairs
            pairs = [[query, doc] for doc in documents]
            
            # Tokenize in batches to avoid memory issues
            batch_size = 4  # Adjust based on GPU memory
            all_scores = []
            
            with torch.no_grad():
                for i in range(0, len(pairs), batch_size):
                    batch_pairs = pairs[i:i + batch_size]
                    
                    # Tokenize batch
                    inputs = self._tokenizer(
                        batch_pairs,
                        padding=True,
                        truncation=True,
                        max_length=512,
                        return_tensors="pt"
                    ).to(self._device)
                    
                    # Get scores
                    outputs = self._model(**inputs)
                    logits = outputs.logits
                    
                    # Handle different output formats
                    if len(logits.shape) > 1 and logits.shape[-1] > 1:
                        # Multi-class output, take first class as relevance score
                        scores = torch.sigmoid(logits[:, 0])
                    else:
                        # Single score output
                        scores = torch.sigmoid(logits.squeeze(-1))
                    
                    scores = scores.cpu().numpy()
                    all_scores.extend(scores.tolist())
            
            # Combine documents with scores
            doc_scores = list(zip(documents, all_scores))
            
            # Sort by score (descending)
            doc_scores.sort(key=lambda x: x[1], reverse=True)
            
            # Apply threshold if provided
            if threshold is not None:
                doc_scores = [(doc, score) for doc, score in doc_scores if score >= threshold]
            
            # Return top_k results
            return doc_scores[:top_k]
            
        except Exception as e:
            print(f"Error during reranking: {e}")
            # Fallback to original order
            return [(doc, 1.0) for doc in documents[:top_k]]
    
    def get_scores(self, query: str, documents: List[str]) -> List[float]:
        """
        Get relevance scores without reordering
        
        Args:
            query: Search query
            documents: List of documents
        
        Returns:
            List of scores in the same order as input documents
        """
        if not self.config.use_reranker or not self._initialized:
            return [1.0] * len(documents)
        
        try:
            doc_scores = self.rerank(query, documents, top_k=len(documents))
            # Create a mapping from document to score
            score_map = {doc: score for doc, score in doc_scores}
            # Return scores in original order
            return [score_map.get(doc, 0.0) for doc in documents]
        except Exception as e:
            print(f"Error getting scores: {e}")
            return [1.0] * len(documents)


# Singleton instance
_reranker_client: Optional[RerankerClient] = None


def get_reranker_client() -> RerankerClient:
    """Get or create reranker client singleton"""
    global _reranker_client
    if _reranker_client is None:
        _reranker_client = RerankerClient()
    return _reranker_client