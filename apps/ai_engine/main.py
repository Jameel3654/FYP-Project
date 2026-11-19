"""
main.py -- FastAPI Application for COF-RAG AI Engine
======================================================
HTTP API that exposes the full COF-RAG pipeline to the Node.js backend.

Endpoints:
  GET  /health         -- Health check
  POST /api/process    -- Run full pipeline on file or text
  POST /api/query      -- Query a processed document via LLM (future)

The /api/process endpoint accepts either:
  - file_path: path to a PDF/image/text file on the server
  - text: direct text string (no file needed)
Plus a query string to optimize context for.

Architecture:
  React (port 5173) -> Node.js (port 5000) -> FastAPI (port 8000)
  The Node.js server forwards requests to this FastAPI app.

Run:
  cd apps/ai_engine
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import sys
import time

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

# Add project root to path so imports work both as module and standalone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.request_models import ProcessRequest, HealthResponse
from models.response_models import (
    ProcessResponse, PipelineStepResult, ErrorResponse
)
from utils.logger import get_logger
from utils.file_detector import detect_input_type
# The full pipeline lives in main_pipeline.py (shared with the CLI)
import main_pipeline

# Initialize Logger
logger = get_logger(__name__)

# Initialize FastAPI App
app = FastAPI(
    title="COF-RAG AI Engine",
    description="Context Optimization Framework for Document-Based RAG Systems. "
                "Two-stage compression: CrossEncoder + LLMLingua-2.",
    version="2.0.0",
)

# CORS Middleware -- allow React dev server and Node.js backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5000",   # Node.js backend
        "http://localhost:5173",   # Vite React dev server
        "http://localhost:3000",   # Alternative React port
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Upload directory for files sent via multipart form
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.on_event("startup")
async def startup_event():
    """Log startup. Models are lazy-loaded on first request."""
    logger.info("COF-RAG AI Engine v2.0 starting...")
    logger.info("Models will be lazy-loaded on first request.")
    logger.info(f"Upload directory: {UPLOAD_DIR}")


# =====================================================================
# GET /health -- Health Check
# =====================================================================
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Quick health check for the Node.js server to verify AI engine is up."""
    return HealthResponse(status="ok", version="2.0.0")


# =====================================================================
# POST /api/process -- Run Full Pipeline (JSON body)
# =====================================================================
@app.post("/api/process", response_model=ProcessResponse)
async def process_document(request: ProcessRequest):
    """
    Run the full COF-RAG pipeline on a file or direct text.

    Accepts JSON body with:
      - file_path: path to file on server, OR
      - text: direct text string
      - query: the question to optimize for
      - top_k: number of chunks to retrieve (default 5)

    Returns the optimized context plus all pipeline stats.
    """
    logger.info(f"Processing request: query='{request.query[:50]}...'")
    pipeline_start = time.time()
    steps = []

    # Validate input -- must have either file_path or text
    if not request.file_path and not request.text:
        raise HTTPException(
            status_code=400,
            detail="Must provide either 'file_path' or 'text'"
        )

    # Determine input data
    if request.text:
        input_data = request.text
        logger.info(f"Direct text input: {len(input_data)} chars")
    else:
        input_data = request.file_path
        if not os.path.exists(input_data):
            raise HTTPException(
                status_code=404,
                detail=f"File not found: {input_data}"
            )
        logger.info(f"File input: {input_data}")

    try:
        # Run the SAME pipeline as the CLI (main_pipeline.run_pipeline).
        # WHY: keeping one implementation means record handling, cleanup
        # and compression fixes apply to the web app automatically.
        main_pipeline._STEP_TIMINGS.clear()
        results = main_pipeline.run_pipeline(
            input_data, request.query,
            top_k=request.top_k, target_words=request.target_words,
        )

        if "final_context" not in results:
            # run_pipeline returns partial results when a step fails
            failed_at = ("extraction" if "extraction" not in results else
                         "chunking" if "chunking" not in results else
                         "retrieval")
            raise RuntimeError(f"Pipeline failed during {failed_at} -- see server log")

        detection = results.get("detection", {})
        extraction = results.get("extraction", {})
        chunking = results.get("chunking", {})
        retrieval = results.get("retrieval", {})
        compression = results.get("compression", {})
        reranking = results.get("reranking", {})

        # Attach useful details to each step for the frontend
        step_details = {
            "Input Detection": {"input_type": detection.get("input_type")},
            "Text Extraction": {"words": extraction.get("word_count"),
                                "method": extraction.get("extraction_method"),
                                "quality": extraction.get("quality_score"),
                                "records": len(results.get("structured_records", []))},
            "Chunking": {"chunks": chunking.get("count"),
                         "strategy": chunking.get("strategy_used")},
            "Retrieval": {"selected": len(retrieval.get("relevant_chunks", []))},
            "Two-Stage Compression": {"method": compression.get("method_detail"),
                                      "ratio": compression.get("total_compression_ratio")},
            "Reranking": {"sentences": reranking.get("sentence_count", 0)},
        }
        steps = [
            PipelineStepResult(step=t["step"], elapsed_seconds=t["elapsed_seconds"],
                               details=step_details.get(t["step"], {}))
            for t in main_pipeline._STEP_TIMINGS
        ]

        # Records for the frontend table (drop the pre-formatted text blob)
        selected = [
            {k: v for k, v in r.items() if k != "formatted_text"}
            for r in results.get("selected_records", [])
        ]

        response = ProcessResponse(
            success=True,
            input_type=detection.get("input_type", "unknown"),
            input_words=results.get("original_words", extraction.get("word_count", 0)),
            chunks_created=chunking.get("count", 0),
            chunks_retrieved=len(retrieval.get("relevant_chunks", [])),
            chunking_strategy=chunking.get("strategy_used", "none"),
            stage1_words=compression.get("stage1_words_after_provence", 0),
            stage2_words=compression.get("stage2_words_after_llmlingua2", 0),
            compression_ratio=compression.get("total_compression_ratio", 0.0),
            compression_method=compression.get("method_detail", "none"),
            final_context=results["final_context"],
            final_words=results["final_words"],
            sentence_count=reranking.get("sentence_count", 0),
            total_time_seconds=round(time.time() - pipeline_start, 2),
            steps=steps,
            records_found=len(results.get("structured_records", [])),
            structured_records=selected,
        )

        logger.info(
            f"Pipeline complete: {response.input_words} -> {response.final_words} words, "
            f"{len(selected)} records, {response.total_time_seconds:.1f}s"
        )
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pipeline error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================================
# POST /api/process/upload -- Upload File + Run Pipeline (multipart)
# =====================================================================
@app.post("/api/process/upload", response_model=ProcessResponse)
async def process_upload(
    file: UploadFile = File(...),
    query: str = Form(...),
    top_k: int = Form(5),
    target_words: int = Form(1200),
):
    """
    Upload a file and run the full pipeline.
    This is for the React frontend which uploads files via multipart form.

    Accepts:
      - file: the uploaded file (PDF, image, text)
      - query: the question (form field)
      - top_k: chunks to retrieve (form field, default 5)
    """
    # Save uploaded file to disk
    safe_name = file.filename.replace(" ", "_")
    save_path = os.path.join(UPLOAD_DIR, safe_name)

    try:
        contents = await file.read()
        with open(save_path, "wb") as f:
            f.write(contents)
        logger.info(f"Uploaded file saved: {save_path} ({len(contents)} bytes)")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File save failed: {e}")

    # Run the pipeline using the saved file
    request = ProcessRequest(file_path=save_path, query=query,
                             top_k=top_k, target_words=target_words)
    return await process_document(request)


# =====================================================================
# Run with: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
# =====================================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
