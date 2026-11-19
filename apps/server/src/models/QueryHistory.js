/**
 * QueryHistory.js
 * Mongoose model for query history.
 */
import mongoose from 'mongoose';

const queryHistorySchema = new mongoose.Schema({
  userId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: true
  },
  documentId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'Document',
    required: true
  },
  question: {
    type: String,
    required: true
  },
  answer: {
    type: String
  },
  llmProvider: {
    type: String,
    enum: ['openai', 'gpt-4', 'gemini'],
    required: true
  },
  originalTokens: {
    type: Number
  },
  model: String,
  inputTokens: Number,
  outputTokens: Number,
  totalTokens: Number,
  compressedTokens: {
    type: Number
  },
  compressionRatio: {
    type: Number
  },
  costUSD: {
    type: Number
  },
  costPKR: {
    type: Number
  },
  responseTimeMs: {
    type: Number
  },
  createdAt: {
    type: Date,
    default: Date.now
  }
});

export default mongoose.model('QueryHistory', queryHistorySchema);
