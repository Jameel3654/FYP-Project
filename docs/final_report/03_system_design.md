# Chapter 3: System Design

## 3.1 System Architecture
<!-- 
Placeholder & Writing Guidelines:
- Detail the three-tier architectural decomposition:
  1. Client Presentation Tier: Single Page Application (SPA) built with React and Tailwind CSS.
  2. API Gateway & Application Server Tier: Node.js Express server managing authentication, session orchestration, and routing.
  3. AI Engine Service Tier: Python FastAPI microservice encapsulating ML models (LLMLingua, LaBSE, Tesseract OCR, FAISS/Chroma vector store).
- Explain communication mechanisms: RESTful APIs, JSON payloads, and streaming endpoints.
-->
COF-RAG is architected as a modular, decoupled microservices platform. The separation of concerns ensures that compute-heavy machine learning workloads (token compression, embedding inference, and OCR extraction) execute independently in a dedicated Python environment without blocking high-concurrency client requests handled by the Node.js API gateway.

```text
+-------------------------------------------------------------+
|                      React Frontend                         |
|    (Chat Interface, Document Management, Analytics Dashboard) |
+------------------------------+------------------------------+
                               | HTTPS / JSON
                               v
+-------------------------------------------------------------+
|               Node.js / Express API Gateway                 |
|      (JWT Auth, Request Validation, MongoDB Data Layer)     |
+------------------------------+------------------------------+
                               | Internal HTTP Proxy
                               v
+-------------------------------------------------------------+
|                 FastAPI AI Engine Microservice              |
|  +--------------------+  +-------------------------------+  |
|  | Ingestion & OCR    |  | LLMLingua Context Compressor   |  |
|  +--------------------+  +-------------------------------+  |
|  | LaBSE Vector Index |  | Lost-in-Middle Reordering     |  |
|  +--------------------+  +-------------------------------+  |
+------------------------------+------------------------------+
                               | LLM Provider Integrations
                               v
               OpenAI / Gemini / Anthropic / Ollama
```

## 3.2 Data Flow Diagram
<!-- 
Placeholder & Writing Guidelines:
- Document the two core operational flows:
  1. Document Ingestion Flow: File Upload -> Format Detection -> OCR Fallback -> Semantic Chunking -> LaBSE Embedding -> Vector Store Persistence & Mongo Cataloging.
  2. Query & Context Optimization Flow: User Prompt -> Query Embedding -> Vector Retrieval (Top-k) -> Context Reordering (Attention-Aware) -> LLMLingua Compression -> Prompt Assembly -> LLM Invocation -> Metric Evaluation -> Response to User.
-->
The framework operates through two distinct data pipelines:
1. **Ingestion & Indexing Pipeline**: Uploaded files (.pdf, .docx, .txt) are processed by format detectors. Scanned documents trigger the OCR fallback pipeline. Extracted text is split into semantic chunks with overlapping boundaries, converted to dense vector embeddings using LaBSE, and persisted into the vector index.
2. **Context-Optimized Retrieval Pipeline**: When a user queries the system, the query is embedded and matched against indexed chunks. Top-$k$ candidate passages undergo bidirectional attention reordering, placing prime context chunks at the outer boundaries. The reordered prompt is subsequently compressed via LLMLingua to fit targeted token budgets prior to LLM dispatch.

## 3.3 Technology Stack
<!-- 
Placeholder & Writing Guidelines:
- Document the rationale for selecting each framework and library:
  - React & Vite: High-performance component-driven interface with low bundle footprint.
  - Node.js & Express: Lightweight, event-driven API gateway suited for I/O-bound proxy operations.
  - FastAPI & Python: Asynchronous Python server with native Pydantic typing and HuggingFace integration.
  - MongoDB: Flexible document schema for indexing heterogeneous metadata and benchmark logs.
  - Tesseract OCR & PyPDF: Battle-tested extraction utilities.
  - LLMLingua-2: Compact model-driven token reduction.
-->
The technology stack reflects intentional architectural trade-offs:
- **Presentation**: React 18, Vite, Tailwind CSS, Lucide React, Recharts.
- **Application Server**: Node.js 18+, Express.js, Mongoose, Multer for multipart file streaming.
- **AI Core**: Python 3.10+, FastAPI, Uvicorn, Hugging Face Transformers, SentenceTransformers, Microsoft LLMLingua, PyTorch.
- **Data Persistence**: MongoDB 7.0 for metadata, user profiles, chat logs, and evaluation metrics; Vector store (ChromaDB/FAISS) for dense embeddings.

## 3.4 Database Design
<!-- 
Placeholder & Writing Guidelines:
- Provide entity-relationship and schema diagrams for MongoDB collections:
  - Users: { _id, username, email, passwordHash, createdAt }
  - Documents: { _id, userId, originalName, mimeType, filePath, chunkCount, status, createdAt }
  - DocumentChunks: { _id, documentId, chunkIndex, content, tokenCount, embeddingId }
  - ChatSessions: { _id, userId, documentId, title, createdAt }
  - ChatMessages: { _id, sessionId, role, query, response, originalTokens, compressedTokens, compressionRatio, costUsd, costPkr, latencyMs }
  - BenchmarkResults: Schema corresponding to data/benchmark/results.csv.
-->
Data storage utilizes MongoDB collections organized around user operations, document metadata, and evaluation telemetry. Documents and their associated chunk partitions maintain relational references to support granular retrieval, while message records log token metrics and cost analytics for continuous monitoring.

## 3.5 API Design
<!-- 
Placeholder & Writing Guidelines:
- Detail REST API specifications including route paths, HTTP methods, request headers, body schemas, and response formats:
  - Express API Gateway routes: /api/auth, /api/documents, /api/chat, /api/benchmark.
  - FastAPI AI Engine internal routes: /api/v1/documents/process, /api/v1/context/compress, /api/v1/context/reorder, /api/v1/query, /api/v1/benchmark/run.
-->
The API conforms to REST principles with explicit status codes and JSON response wrappers. The internal FastAPI engine exposes typed endpoints validated by Pydantic models, facilitating direct programmatic access for standalone evaluation scripts and client gateway routing.

## 3.6 Security Considerations
<!-- 
Placeholder & Writing Guidelines:
- Cover critical security facets:
  - Authentication and Authorization: JSON Web Tokens (JWT) with bcrypt salt hashing.
  - Input Sanitization & File Upload Security: MIME type verification, file size limits, directory traversal prevention.
  - Secret Management: Environment-isolated variables (.env) for API keys (OpenAI, Gemini, Anthropic).
  - Data Privacy: Avoiding sensitive document leakage to third-party providers when running local Ollama inference.
-->
Security protocols protect both user credentials and sensitive enterprise documents. Key safeguards include strict MIME-type validation to prevent malicious uploads, encrypted JWT bearer authorization, and parameterized database queries to eliminate injection vulnerabilities. Crucially, all external LLM API credentials are maintained exclusively in environment variables and never logged or exposed to the client.
