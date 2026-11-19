"""
response_models.py -- Pydantic Response Models
================================================
Defines the shape of HTTP response bodies.
These ensure consistent API responses across all endpoints.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class PipelineStepResult(BaseModel):
    """Result from a single pipeline step."""
    step: str
    elapsed_seconds: float
    details: Dict[str, Any] = {}


class ProcessResponse(BaseModel):
    """
    Response from the /api/process endpoint.
    Contains the full pipeline results including the final optimized context.
    """
    success: bool = True

    # Input info
    input_type: str = Field(..., description="digital_pdf|scanned_pdf|image|text_file|direct_text")
    input_words: int = Field(..., description="Total words in original text")

    # Pipeline results
    chunks_created: int = Field(..., description="Number of chunks after chunking")
    chunks_retrieved: int = Field(..., description="Number of relevant chunks found")
    chunking_strategy: str = Field(..., description="Strategy used: semantic|paragraph|fixed")

    # Compression results
    stage1_words: int = Field(..., description="Words after Stage 1 cross-encoder pruning")
    stage2_words: int = Field(..., description="Words after Stage 2 LLMLingua-2 compression")
    compression_ratio: float = Field(..., description="Total compression ratio (0.0 to 1.0)")
    compression_method: str = Field(..., description="Methods used: CrossEncoder + LLMLingua-2")

    # Final output
    final_context: str = Field(..., description="The optimized context, ready for LLM")
    final_words: int = Field(..., description="Word count of final context")
    sentence_count: int = Field(..., description="Sentences in final reranked context")

    # Timing
    total_time_seconds: float = Field(..., description="Total pipeline execution time")

    # Step details (for frontend display)
    steps: List[PipelineStepResult] = []

    # Structured records (exact values, never compressed)
    records_found: int = Field(0, description="Structured records detected in the document")
    structured_records: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Records relevant to the query: record_id, account_holder, "
                    "city, account_number, branch_code, status, clearing_zone, fields",
    )


class QueryResponse(BaseModel):
    """
    Response from the /api/query endpoint.
    Contains the LLM answer plus compression stats.
    """
    answer: str
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float
    cost_usd: float
    cost_pkr: float
    llm_provider: str
    response_time_ms: float


class ErrorResponse(BaseModel):
    """Standard error response."""
    success: bool = False
    error: str
    detail: Optional[str] = None
