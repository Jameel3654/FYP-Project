import React, { useState } from 'react';
import useQuery from '../../hooks/useQuery';
import LLMSelector from './LLMSelector';
import AnswerDisplay from './AnswerDisplay';

export default function SendToLLM({ context, documentId }) {
  const [question, setQuestion] = useState('');
  const [provider, setProvider] = useState('openai');
  const providerName = provider === 'gemini' ? 'Gemini' : 'OpenAI';
  const { submitContext, loading, answer, tokenStats, error } = useQuery();
  return (
    <section className="bg-white border border-indigo-200 rounded-xl p-4 space-y-4">
      <h3 className="font-semibold text-gray-900">Send optimized context to an LLM</h3>
      <p className="text-sm text-gray-500">Processing stays local. Select a provider and click below to send the optimized context.</p>
      <LLMSelector selected={provider} onChange={setProvider} />
      <label className="block text-sm text-gray-700">
        Question (optional)
        <textarea value={question} onChange={e => setQuestion(e.target.value)} rows={2}
          placeholder="Leave blank for a summary with the exact records"
          className="mt-1 w-full border border-gray-300 rounded-lg p-3" />
      </label>
      <button type="button" disabled={loading || !context?.trim()}
        onClick={() => submitContext(context, question, documentId, provider)}
        className="bg-indigo-600 text-white rounded-lg px-5 py-2.5 disabled:opacity-50 disabled:cursor-not-allowed">
        {loading ? 'Waiting for answer...' : `Send to ${providerName}`}
      </button>
      {error && <p role="alert" className="text-red-700 text-sm">{error}</p>}
      {answer && <AnswerDisplay result={{ answer, ...tokenStats }} />}
    </section>
  );
}
