// Component for inputting user queries and selecting LLM
import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import useQuery from '../../hooks/useQuery';
import LLMSelector from './LLMSelector';
import AnswerDisplay from './AnswerDisplay';

const QueryInput = () => {
  const [searchParams] = useSearchParams();
  const [documentId, setDocumentId] = useState(searchParams.get('docId') || '');
  const [question, setQuestion] = useState('');
  const [llmProvider, setLlmProvider] = useState('openai');
  
  const { submitQuery, loading, answer, tokenStats, error } = useQuery();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!documentId) {
      alert("Please provide a Document ID or upload a document first.");
      return;
    }
    if (!question.trim()) return;
    
    await submitQuery(documentId, question, llmProvider);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Ask Questions</h1>
        <p className="text-gray-500">Query your uploaded documents with optimized context.</p>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Document ID</label>
            <input 
              type="text" 
              value={documentId}
              onChange={(e) => setDocumentId(e.target.value)}
              placeholder="Enter document ID or upload via 'Upload' tab"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Your Question</label>
            <textarea 
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="What would you like to know about this document?"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none min-h-[120px] resize-y"
              required
            />
          </div>

          <LLMSelector selected={llmProvider} onChange={setLlmProvider} />

          {error && (
            <div className="p-3 bg-red-50 text-red-600 rounded-lg text-sm">
              {error}
            </div>
          )}

          <div className="flex justify-end">
            <button 
              type="submit"
              disabled={loading || !question.trim()}
              className="bg-indigo-600 text-white px-8 py-2.5 rounded-lg font-medium hover:bg-indigo-700 focus:ring-4 focus:ring-indigo-200 transition-all disabled:opacity-70 flex items-center"
            >
              {loading ? (
                <>
                  <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Processing...
                </>
              ) : `Send to ${llmProvider === 'gemini' ? 'Gemini' : 'OpenAI'}`}
            </button>
          </div>
        </form>
      </div>

      {answer && tokenStats && (
        <AnswerDisplay result={{ answer, ...tokenStats }} />
      )}
    </div>
  );
};

export default QueryInput;
