// Pipeline results display component
// Shows compression stats, step timings, and final optimized context
import React, { useState } from 'react';
import SendToLLM from '../Query/SendToLLM';

const PipelineResults = ({ result }) => {
  const [showContext, setShowContext] = useState(false);

  if (!result) return null;

  const pipeline = result.pipeline;
  if (!pipeline) {
    return (
      <div className="mt-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
        <p className="text-yellow-700 font-medium">
          File uploaded but pipeline did not run.
        </p>
        {result.warning && (
          <p className="text-yellow-600 text-sm mt-1">{result.warning}</p>
        )}
      </div>
    );
  }

  const reductionPct = (pipeline.compression_ratio * 100).toFixed(1);

  return (
    <div className="mt-6 space-y-4">
      {/* Header */}
      <div className="bg-green-50 border border-green-200 rounded-lg p-4">
        <div className="flex items-center gap-2">
          <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
          </svg>
          <h3 className="text-green-800 font-semibold">Pipeline Complete</h3>
        </div>
        <p className="text-green-700 text-sm mt-1">
          {pipeline.input_words.toLocaleString()} words compressed to {pipeline.final_words.toLocaleString()} words
          ({reductionPct}% reduction) in {pipeline.total_time_seconds}s
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Input Words" value={pipeline.input_words.toLocaleString()} color="blue" />
        <StatCard label="Final Words" value={pipeline.final_words.toLocaleString()} color="green" />
        <StatCard label="Reduction" value={`${reductionPct}%`} color="purple" />
        <StatCard label="Time" value={`${pipeline.total_time_seconds}s`} color="orange" />
      </div>

      {/* Structured Records -- exact values, never compressed */}
      {pipeline.structured_records && pipeline.structured_records.length > 0 && (
        <RecordsTable records={pipeline.structured_records} total={pipeline.records_found} />
      )}

      {/* Sending is an explicit action after document processing. */}
      <SendToLLM context={pipeline.final_context} documentId={result.data?._id} />

      {/* Compression Breakdown */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h4 className="font-semibold text-gray-800 mb-3">Compression Breakdown</h4>
        <div className="space-y-2">
          {/* Visual bar */}
          <div className="flex items-center gap-2 text-sm">
            <span className="w-24 text-gray-500">Original</span>
            <div className="flex-1 bg-gray-100 rounded-full h-6 relative">
              <div className="bg-blue-500 h-6 rounded-full" style={{ width: '100%' }} />
              <span className="absolute inset-0 flex items-center justify-center text-white text-xs font-medium">
                {pipeline.input_words.toLocaleString()} words
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <span className="w-24 text-gray-500">Stage 1</span>
            <div className="flex-1 bg-gray-100 rounded-full h-6 relative">
              <div className="bg-indigo-500 h-6 rounded-full"
                style={{ width: `${Math.max(5, (pipeline.stage1_words / pipeline.input_words) * 100)}%` }} />
              <span className="absolute inset-0 flex items-center justify-center text-xs font-medium"
                style={{ color: (pipeline.stage1_words / pipeline.input_words) > 0.3 ? 'white' : '#4338ca' }}>
                {pipeline.stage1_words.toLocaleString()} words (CrossEncoder)
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <span className="w-24 text-gray-500">Stage 2</span>
            <div className="flex-1 bg-gray-100 rounded-full h-6 relative">
              <div className="bg-green-500 h-6 rounded-full"
                style={{ width: `${Math.max(5, (pipeline.stage2_words / pipeline.input_words) * 100)}%` }} />
              <span className="absolute inset-0 flex items-center justify-center text-xs font-medium"
                style={{ color: (pipeline.stage2_words / pipeline.input_words) > 0.15 ? 'white' : '#059669' }}>
                {pipeline.stage2_words.toLocaleString()} words (LLMLingua-2)
              </span>
            </div>
          </div>
        </div>
        <p className="text-xs text-gray-500 mt-2">
          Method: {pipeline.compression_method} | Strategy: {pipeline.chunking_strategy} |
          Chunks: {pipeline.chunks_retrieved}/{pipeline.chunks_created} selected
        </p>
      </div>

      {/* Step Timings */}
      {pipeline.steps && pipeline.steps.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h4 className="font-semibold text-gray-800 mb-3">Pipeline Steps</h4>
          <div className="space-y-1.5">
            {pipeline.steps.map((step, i) => (
              <div key={i} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 bg-indigo-100 text-indigo-700 rounded-full flex items-center justify-center text-xs font-bold">
                    {i + 1}
                  </span>
                  <span className="text-gray-700">{step.step}</span>
                </div>
                <span className="text-gray-500 font-mono">{step.elapsed_seconds}s</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Final Context (collapsible) */}
      <div className="bg-white rounded-lg border border-gray-200">
        <button
          onClick={() => setShowContext(!showContext)}
          className="w-full p-4 flex items-center justify-between text-left hover:bg-gray-50 transition-colors"
        >
          <h4 className="font-semibold text-gray-800">
            Optimized Context ({pipeline.final_words} words, {pipeline.sentence_count} sentences)
          </h4>
          <svg className={`w-5 h-5 text-gray-400 transition-transform ${showContext ? 'rotate-180' : ''}`}
            fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        {showContext && (
          <div className="px-4 pb-4">
            <div className="bg-gray-50 rounded-lg p-3 text-sm text-gray-700 leading-relaxed max-h-96 overflow-y-auto whitespace-pre-wrap">
              {pipeline.final_context}
            </div>
            <p className="text-xs text-gray-400 mt-2">
              This optimized context is ready to send to any LLM (GPT-4, Gemini, etc.)
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

const StatCard = ({ label, value, color }) => {
  const colors = {
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    green: 'bg-green-50 text-green-700 border-green-200',
    purple: 'bg-purple-50 text-purple-700 border-purple-200',
    orange: 'bg-orange-50 text-orange-700 border-orange-200',
  };

  return (
    <div className={`rounded-lg border p-3 text-center ${colors[color]}`}>
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-xs mt-0.5 opacity-75">{label}</p>
    </div>
  );
};

// Table of structured records. Columns come from the record fields, so
// any record layout (bank, HR, medical...) is displayed correctly.
const RecordsTable = ({ records, total }) => {
  const columns = [];
  records.forEach((r) => {
    (r.fields || []).forEach((f) => {
      if (!columns.includes(f.key)) columns.push(f.key);
    });
  });
  const valueOf = (r, key) => {
    const field = (r.fields || []).find((f) => f.key === key);
    return field ? field.value : '';
  };

  return (
    <div className="bg-white rounded-lg border border-emerald-200 p-4">
      <h4 className="font-semibold text-gray-800 mb-1">
        Structured Records ({records.length}{total && total !== records.length ? ` of ${total}` : ''})
      </h4>
      <p className="text-xs text-gray-500 mb-3">
        Exact values from the document -- these are never compressed or reworded.
      </p>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="bg-emerald-50 text-emerald-800">
              <th className="px-3 py-2 text-left font-semibold">#</th>
              {columns.map((c) => (
                <th key={c} className="px-3 py-2 text-left font-semibold whitespace-nowrap">{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {records.map((r, i) => (
              <tr key={r.record_id || i} className="border-t border-gray-100">
                <td className="px-3 py-2 text-gray-400">{i + 1}</td>
                {columns.map((c) => (
                  <td key={c} className="px-3 py-2 text-gray-800 font-mono whitespace-nowrap">
                    {valueOf(r, c)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default PipelineResults;
