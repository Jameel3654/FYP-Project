/**
 * query.controller.js
 * Controller for handling document queries.
 */
import QueryHistory from '../models/QueryHistory.js';
import Document from '../models/Document.js';
import { generateAnswer, LLMError } from '../services/llm.service.js';

export const submitQuery = async (req, res) => {
  try {
    const { documentId, question = '', llmProvider = 'openai', context } = req.body;

    if (!['openai', 'gpt-4', 'gemini'].includes(llmProvider)) {
      return res.status(400).json({ success: false, error: 'Unsupported provider. Select OpenAI or Gemini.' });
    }
    let optimizedContext = context;
    if (documentId) {
      if (!/^[a-f\d]{24}$/i.test(documentId)) return res.status(400).json({ success: false, error: 'Invalid document ID' });
      // A caller cannot use another user's saved document.
      const document = await Document.findOne({ _id: documentId, userId: req.user._id });
      if (!document) return res.status(404).json({ success: false, error: 'Document not found' });
      if (document.status !== 'ready') return res.status(409).json({ success: false, error: 'Process this document first.' });
      optimizedContext = document.pipelineResult?.finalContext;
    }

    const startTime = Date.now();
    
    // Send the optimized context to the selected provider for this action.
    const aiResponse = await generateAnswer({ context: optimizedContext, question, provider: llmProvider });
    
    const responseTimeMs = Date.now() - startTime;

    const { answer, tokenStats, model, provider } = aiResponse;

    // Save to QueryHistory
    let historyId;
    let warning;
    if (documentId) {
      try {
        const queryHistory = await QueryHistory.create({
          userId: req.user._id,
          documentId,
          question: question || 'Summarize the processed document',
          answer,
          llmProvider: provider,
          model,
          inputTokens: tokenStats.inputTokens,
          outputTokens: tokenStats.outputTokens,
          totalTokens: tokenStats.totalTokens,
          responseTimeMs
        });
        historyId = queryHistory._id;
      } catch {
        warning = 'The answer was generated, but history could not be saved.';
      }
    }

    res.status(200).json({
      success: true,
      data: {
        answer,
        tokenStats,
        model,
        provider,
        responseTimeMs,
        historyId,
        warning,
      }
    });
  } catch (error) {
    res.status(error instanceof LLMError ? error.status : 500).json({
      success: false, error: error instanceof LLMError ? error.message : 'Unable to answer this document question.'
    });
  }
};

export const getHistory = async (req, res) => {
  try {
    const history = await QueryHistory.find({ userId: req.user._id })
      .sort({ createdAt: -1 })
      .limit(50)
      .populate('documentId', 'originalName');
      
    res.status(200).json({ success: true, data: history });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
};

export const getStats = async (req, res) => {
  try {
    const stats = await QueryHistory.aggregate([
      { $match: { userId: req.user._id } },
      {
        $group: {
          _id: null,
          totalQueries: { $sum: 1 },
          totalCostUSD: { $sum: '$costUSD' },
          totalCostPKR: { $sum: '$costPKR' },
          avgCompressionRatio: { $avg: '$compressionRatio' }
        }
      }
    ]);

    const result = stats.length > 0 ? stats[0] : { totalQueries: 0, totalCostUSD: 0, totalCostPKR: 0, avgCompressionRatio: 0 };
    delete result._id;

    res.status(200).json({ success: true, data: result });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
};

export const getById = async (req, res) => {
  try {
    const history = await QueryHistory.findOne({ _id: req.params.id, userId: req.user._id })
      .populate('documentId', 'originalName');
      
    if (!history) {
      return res.status(404).json({ success: false, error: 'Query history not found' });
    }
    res.status(200).json({ success: true, data: history });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
};
