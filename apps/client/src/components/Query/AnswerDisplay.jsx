import React from 'react';

const AnswerDisplay = ({ result }) => (
  <div className="space-y-4" aria-live="polite">
    <div className="bg-white rounded-xl border border-indigo-100 p-6">
      <h3 className="text-lg font-semibold text-indigo-900 mb-3">{result.provider === 'gemini' ? 'Gemini' : 'OpenAI'} answer</h3>
      <div className="whitespace-pre-wrap text-gray-800 leading-relaxed">{result.answer}</div>
      {result.warning && <p className="text-sm text-amber-700 mt-3">{result.warning}</p>}
    </div>
    <div className="grid grid-cols-3 gap-3">
      {[
        ['API input tokens', result.inputTokens],
        ['Answer tokens', result.outputTokens],
        ['Total tokens', result.totalTokens],
      ].map(([label, value]) => (
        <div key={label} className="rounded-lg bg-white border border-gray-200 p-3 text-center">
          <p className="text-lg font-semibold">{value == null ? 'Unavailable' : value.toLocaleString()}</p>
          <p className="text-xs text-gray-500">{label}</p>
        </div>
      ))}
    </div>
    <p className="text-xs text-gray-500">Model: {result.model}. Token counts are reported by the provider and include the question and instructions.{result.thinkingTokens > 0 ? ` Total includes ${result.thinkingTokens.toLocaleString()} thinking tokens.` : ''}</p>
  </div>
);

export default AnswerDisplay;
