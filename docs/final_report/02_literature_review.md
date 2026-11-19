# Chapter 2: Literature Review

## 2.1 Retrieval-Augmented Generation (RAG)
<!-- 
Placeholder & Writing Guidelines:
- Review seminal papers in RAG (e.g., Lewis et al., 2020; Guu et al., REALM).
- Detail standard naive RAG vs. advanced RAG patterns: Pre-retrieval, Retrieval, and Post-retrieval optimizations.
- Discuss vector representations, approximate nearest neighbor (ANN) search algorithms (HNSW, Flat L2, Cosine Similarity), and dense vs. sparse hybrid search.
-->
Retrieval-Augmented Generation (RAG) formalizes an approach to overcome parametric knowledge boundaries in LLMs by grounding generations on retrieved document corpora. While initial naive implementations relied on straightforward vector similarity matching and static prompt concatenation, recent scholarship identifies significant failure modes in retrieval noise, context redundancy, and prompt injection vulnerabilities. Advanced RAG taxonomies emphasize three modular stages: pre-retrieval chunking and enrichment, hybrid dense/sparse indexing, and post-retrieval context refinement and re-ranking.

## 2.2 Context Window Optimization
<!-- 
Placeholder & Writing Guidelines:
- Survey the evolution of LLM context lengths (from 2k/4k in original GPT models to 128k in GPT-4 and 1M+ in Gemini).
- Discuss why simply expanding the context window is computationally inefficient (quadratic $O(N^2)$ or linear attention computational costs, memory consumption during KV caching, financial pricing per million tokens).
- Summarize strategies for context optimization: summarization, filtering, prompt compression, and sparse context selection.
-->
Although frontier foundation models now advertise massive context windows exceeding one million tokens, context scaling remains fraught with severe operational drawbacks. The quadratic time and space complexity of standard self-attention mechanisms, alongside accumulating KV-cache memory burdens, causes quadratic latency spikes and prohibitive billing costs. Consequently, context window optimization—the systematic condensation of input prompts while maintaining semantic completeness—has emerged as a foundational research area.

## 2.3 Lost in the Middle Problem
<!-- 
Placeholder & Writing Guidelines:
- Examine the landmark findings of Liu et al. (2023) "Lost in the Middle: How Language Models Use Long Contexts".
- Explain the U-shaped attention distribution: decoders attend strongly to inputs at the beginning (primacy effect) and end (recency effect) of long contexts, while ignoring content located in the middle.
- Discuss reordering mechanisms, bidirectionality, and attention-aware rank restructuring as counter-measures.
-->
In their foundational study, Liu et al. (2023) demonstrated that large language models perform best when relevant information occurs at the absolute start or end of the input context. Performance systematically deteriorates when critical facts are positioned centrally within extensive contexts, regardless of total window capacity. This "Lost in the Middle" phenomenon severely impairs standard RAG systems, which typically sort passages in descending similarity order, inadvertently depositing lower-ranked or borderline chunks at the end while leaving essential supporting data stranded in the center.

## 2.4 LLMLingua and Prompt Compression
<!-- 
Placeholder & Writing Guidelines:
- Review the LLMLingua and LLMLingua-2 frameworks developed by Microsoft Research (Jiang et al., 2023; Pan et al., 2024).
- Explain information-theoretic token pruning using small language models (e.g., LLaMA-7B or XLM-RoBERTa) to compute token perplexity and mutual information with respect to the user query.
- Compare task-aware compression against extractive summarization and naive sentence truncation.
-->
LLMLingua and its successor LLMLingua-2 represent state-of-the-art prompt compression frameworks that employ compact language models to prune non-essential tokens from retrieved contexts. By calculating token-level perplexity scores conditioned on query semantics, LLMLingua removes syntactically redundant tokens, filler words, and irrelevant sentences while preserving structural and conceptual coherence. Unlike traditional extractive summarization, prompt compression operates at sub-sentence token granularity, achieving high compression ratios (up to 4x) without introducing hallucinated abstractions.

## 2.5 Multilingual Embeddings (LaBSE)
<!-- 
Placeholder & Writing Guidelines:
- Examine cross-lingual text representation models: mBERT, XLM-R, and LaBSE (Language-Agnostic BERT Sentence Embedding by Feng et al., 2020).
- Discuss how LaBSE maps 109+ languages into a shared dense vector space using dual-encoder architectures trained on translation pairs.
- Evaluate the necessity of cross-lingual representations in multilingual documents, code-switched queries, and international administrative records.
-->
Enterprise document repositories frequently span multiple languages, dialects, and translated legal documents. Standard monolingual embedding models exhibit catastrophic semantic drift when querying cross-lingual corpora. Language-Agnostic BERT Sentence Embeddings (LaBSE) overcome this bottleneck by mapping sentences across 109 languages into a unified vector space, ensuring that conceptual equivalence is preserved across linguistic boundaries without requiring pre-translation pipelines.

## 2.6 OCR for Document Processing
<!-- 
Placeholder & Writing Guidelines:
- Analyze challenges in extracting text from non-digital, scanned, or image-heavy documents (e.g., invoices, archived reports, scanned contracts).
- Review optical character recognition engines (Tesseract, EasyOCR, PaddleOCR) and modern vision-language parsing tools (e.g., Docling, Nougat).
- Highlight bounding box alignment, binarization, de-noising filters, and error recovery in downstream text pipelines.
-->
A substantial portion of historical and enterprise paperwork exists strictly as scanned raster images embedded within PDF containers. Naive text extraction utilities yield empty strings or corrupted character sequences when encountering such documents. Integrating an optical character recognition (OCR) fallback pipeline—such as Tesseract OCR with adaptive image thresholding and noise reduction—is imperative for robust text extraction prior to semantic chunking.

## 2.7 Summary
<!-- 
Placeholder & Writing Guidelines:
- Synthesize the gaps identified in current literature: absence of integrated systems that unite OCR ingestion, multilingual dense indexing, token compression, and context reordering.
- State how COF-RAG directly addresses these collective gaps into a unified framework.
-->
The surveyed literature underscores that while individual solutions exist for retrieval, OCR, prompt compression, and attention reordering, practical systems rarely integrate them into a cohesive framework. COF-RAG bridges these disparate paradigms into an end-to-end, measurable, and cost-efficient architecture capable of handling multi-format documents and mitigating attention degradation across leading LLMs.
