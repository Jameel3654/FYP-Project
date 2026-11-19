/**
 * document.controller.js
 * Controller for document upload and AI pipeline processing.
 * 
 * Flow:
 *   1. User uploads file + enters query from React
 *   2. Multer saves file to disk
 *   3. We forward file path + query to FastAPI AI Engine
 *   4. AI Engine returns optimized context + compression stats
 *   5. We save results to MongoDB and send back to React
 */
import Document from '../models/Document.js';
import * as aiEngine from '../services/aiEngine.service.js';
import fs from 'fs';

/**
 * Upload a document AND run the AI pipeline.
 * POST /api/documents/upload
 * 
 * Expects multipart form with:
 *   - document: the file (PDF, image, text)
 *   - query: the question to optimize context for
 *   - top_k: number of chunks to retrieve (optional, default 5)
 */
export const upload = async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ success: false, error: 'No file uploaded' });
    }

    const query = req.body.query || '';
    const topK = parseInt(req.body.top_k) || 5;

    // Create Document record in MongoDB
    const document = await Document.create({
      userId: req.user._id,
      originalName: req.file.originalname,
      fileName: req.file.filename,
      filePath: req.file.path,
      fileSize: req.file.size,
      mimeType: req.file.mimetype,
      status: 'processing'
    });

    // If no query provided, just save and return
    if (!query) {
      document.status = 'uploaded';
      await document.save();
      return res.status(201).json({
        success: true,
        data: document,
        message: 'File uploaded. Send a query to /api/documents/process to run the pipeline.'
      });
    }

    // Run AI pipeline via FastAPI
    try {
      const result = await aiEngine.processFile(document.filePath, query, topK);

      // Update document with pipeline results
      document.status = 'ready';
      document.pipelineResult = {
        inputType: result.input_type,
        inputWords: result.input_words,
        chunksCreated: result.chunks_created,
        chunksRetrieved: result.chunks_retrieved,
        chunkingStrategy: result.chunking_strategy,
        stage1Words: result.stage1_words,
        stage2Words: result.stage2_words,
        compressionRatio: result.compression_ratio,
        compressionMethod: result.compression_method,
        finalContext: result.final_context,
        finalWords: result.final_words,
        sentenceCount: result.sentence_count,
        totalTimeSeconds: result.total_time_seconds,
        steps: result.steps,
        query: query,
      };
      await document.save();

      res.status(201).json({
        success: true,
        data: document,
        pipeline: result,
      });
    } catch (aiError) {
      document.status = 'error';
      document.error = aiError.message;
      await document.save();
      
      // Still return the document, but with error status
      res.status(201).json({
        success: true,
        data: document,
        pipeline: null,
        warning: `File uploaded but pipeline failed: ${aiError.message}. Is the AI Engine running on port 8000?`
      });
    }
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
};

/**
 * Process a previously uploaded document with a new query.
 * POST /api/documents/process
 * Body: { documentId, query, top_k }
 */
export const processDocument = async (req, res) => {
  try {
    const { documentId, query, top_k } = req.body;

    if (!documentId || !query) {
      return res.status(400).json({
        success: false,
        error: 'documentId and query are required'
      });
    }

    const document = await Document.findOne({
      _id: documentId,
      userId: req.user._id
    });

    if (!document) {
      return res.status(404).json({ success: false, error: 'Document not found' });
    }

    // Run AI pipeline
    document.status = 'processing';
    await document.save();

    const result = await aiEngine.processFile(
      document.filePath,
      query,
      top_k || 5
    );

    // Save results
    document.status = 'ready';
    document.pipelineResult = {
      inputType: result.input_type,
      inputWords: result.input_words,
      chunksCreated: result.chunks_created,
      chunksRetrieved: result.chunks_retrieved,
      chunkingStrategy: result.chunking_strategy,
      stage1Words: result.stage1_words,
      stage2Words: result.stage2_words,
      compressionRatio: result.compression_ratio,
      compressionMethod: result.compression_method,
      finalContext: result.final_context,
      finalWords: result.final_words,
      sentenceCount: result.sentence_count,
      totalTimeSeconds: result.total_time_seconds,
      steps: result.steps,
      query: query,
    };
    await document.save();

    res.status(200).json({ success: true, data: document, pipeline: result });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
};

/**
 * Process direct text (no file upload needed).
 * POST /api/documents/process-text
 * Body: { text, query, top_k }
 */
export const processText = async (req, res) => {
  try {
    const { text, query, top_k } = req.body;

    if (!text || !query) {
      return res.status(400).json({
        success: false,
        error: 'text and query are required'
      });
    }

    const result = await aiEngine.processText(text, query, top_k || 5);
    res.status(200).json({ success: true, pipeline: result });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
};

export const getAll = async (req, res) => {
  try {
    const documents = await Document.find({ userId: req.user._id })
      .sort({ uploadedAt: -1 })
      .select('-pipelineResult.finalContext'); // Don't send full context in list
    res.status(200).json({ success: true, data: documents });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
};

export const getById = async (req, res) => {
  try {
    const document = await Document.findOne({
      _id: req.params.id,
      userId: req.user._id
    });
    if (!document) {
      return res.status(404).json({ success: false, error: 'Document not found' });
    }
    res.status(200).json({ success: true, data: document });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
};

export const deleteDoc = async (req, res) => {
  try {
    const document = await Document.findOne({
      _id: req.params.id,
      userId: req.user._id
    });
    if (!document) {
      return res.status(404).json({ success: false, error: 'Document not found' });
    }

    // Delete file from disk
    if (fs.existsSync(document.filePath)) {
      fs.unlinkSync(document.filePath);
    }

    await Document.deleteOne({ _id: req.params.id });
    res.status(200).json({ success: true, data: {} });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
};
