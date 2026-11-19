"""
request_models.py -- Pydantic Request Models
==============================================
Defines the shape of incoming HTTP request bodies.
FastAPI auto-validates these -- bad requests get clear error messages.
"""

from pydantic import BaseModel, Field
from typing import Optional


class ProcessRequest(BaseModel):
    """
    Request to process a document through the full pipeline.

    Two modes:
      1. File mode: send file_path to a file on the server
      2. Text mode: send text directly (no file needed)
    """
    file_path: Optional[str] = Field(
        None, description="Path to PDF, image, or text file on server"
    )
    text: Optional[str] = Field(
        None, description="Direct text input (no file needed)"
    )
    query: str = Field(
        ..., description="The question to optimize context for"
    )
    top_k: int = Field(
        5, description="Minimum number of chunks to retrieve (default 5)"
    )
    target_words: int = Field(
        1200, ge=200, le=5000,
        description="Final context size in words (default 1200 = ~2-3 pages)"
    )


class QueryRequest(BaseModel):
    """
    Request to query a previously processed document.
    Sends the optimized context to an LLM for answering.
    """
    document_id: str = Field(
        ..., description="MongoDB document ID"
    )
    question: str = Field(
        ..., description="Question to ask about the document"
    )
    llm_provider: str = Field(
        "gpt-4", description="LLM provider: gpt-4 or gemini"
    )


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
