/**
 * Document.js
 * Mongoose model for documents with pipeline results.
 * 
 * Stores both the uploaded file metadata AND the full
 * pipeline processing results (compression stats, final context, etc.)
 */
import mongoose from 'mongoose';

const pipelineStepSchema = new mongoose.Schema({
  step: String,
  elapsed_seconds: Number,
  details: mongoose.Schema.Types.Mixed,
}, { _id: false });

const pipelineResultSchema = new mongoose.Schema({
  inputType: String,
  inputWords: Number,
  chunksCreated: Number,
  chunksRetrieved: Number,
  chunkingStrategy: String,
  stage1Words: Number,
  stage2Words: Number,
  compressionRatio: Number,
  compressionMethod: String,
  finalContext: String,
  finalWords: Number,
  sentenceCount: Number,
  totalTimeSeconds: Number,
  steps: [pipelineStepSchema],
  query: String,
}, { _id: false });

const documentSchema = new mongoose.Schema({
  userId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: true
  },
  originalName: {
    type: String,
    required: true
  },
  fileName: {
    type: String,
    required: true
  },
  filePath: {
    type: String,
    required: true
  },
  fileSize: {
    type: Number
  },
  mimeType: {
    type: String
  },
  status: {
    type: String,
    enum: ['uploaded', 'processing', 'ready', 'error'],
    default: 'uploaded'
  },
  error: {
    type: String
  },
  pipelineResult: pipelineResultSchema,
  uploadedAt: {
    type: Date,
    default: Date.now
  }
});

export default mongoose.model('Document', documentSchema);
