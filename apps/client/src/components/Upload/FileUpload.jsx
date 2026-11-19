// File upload + query input + pipeline results
import React, { useState, useRef } from 'react';
import useUpload from '../../hooks/useUpload';
import UploadStatus from './UploadStatus';
import PipelineResults from './PipelineResults';

const FileUpload = () => {
  const [file, setFile] = useState(null);
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState('file'); // 'file' or 'text'
  const [directText, setDirectText] = useState('');
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef(null);
  const {
    uploading, processing, progress, result, error,
    uploadAndProcess, processText, reset
  } = useUpload();

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleProcess = async () => {
    if (!query.trim()) {
      alert('Please enter a question to optimize the context for.');
      return;
    }

    if (mode === 'file') {
      if (!file) return;
      await uploadAndProcess(file, query);
    } else {
      if (!directText.trim()) return;
      await processText(directText, query);
    }
  };

  const handleReset = () => {
    setFile(null);
    setQuery('');
    setDirectText('');
    reset();
  };

  const isProcessing = uploading || processing;
  const canProcess = mode === 'file' ? (file && query.trim()) : (directText.trim() && query.trim());

  return (
    <div className="max-w-3xl mx-auto mt-4">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Process Document</h1>
        {result && (
          <button onClick={handleReset}
            className="text-sm text-indigo-600 hover:text-indigo-800 font-medium">
            Process Another
          </button>
        )}
      </div>

      {!result && (
        <>
          {/* Mode Toggle */}
          <div className="flex gap-1 bg-gray-100 rounded-lg p-1 mb-6">
            <button
              onClick={() => setMode('file')}
              className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
                mode === 'file' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
              }`}>
              Upload File
            </button>
            <button
              onClick={() => setMode('text')}
              className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
                mode === 'text' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
              }`}>
              Paste Text
            </button>
          </div>

          {/* File Upload Area */}
          {mode === 'file' && (
            <div
              className={`border-2 border-dashed rounded-xl p-10 text-center transition-colors cursor-pointer ${
                dragActive ? 'border-indigo-500 bg-indigo-50' : 'border-gray-300 bg-white hover:bg-gray-50'
              }`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              onClick={() => inputRef.current?.click()}
            >
              <input
                ref={inputRef}
                type="file"
                accept=".pdf,.txt,.jpg,.jpeg,.png,.webp"
                onChange={handleChange}
                className="hidden"
              />
              <div className="flex flex-col items-center justify-center">
                <svg className="w-10 h-10 text-gray-400 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
                <p className="text-base font-medium text-gray-700 mb-1">
                  Drop your file here or click to browse
                </p>
                <p className="text-xs text-gray-400">
                  PDF, TXT, JPG, PNG, WEBP (max 10MB)
                </p>
              </div>
            </div>
          )}

          {/* Direct Text Area */}
          {mode === 'text' && (
            <textarea
              value={directText}
              onChange={(e) => setDirectText(e.target.value)}
              placeholder="Paste your text here..."
              rows={8}
              className="w-full border border-gray-300 rounded-xl p-4 text-sm text-gray-700 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 resize-none"
            />
          )}

          {/* Selected File Info */}
          {mode === 'file' && file && !isProcessing && (
            <div className="mt-4 bg-white rounded-lg border border-gray-200 p-3 flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="p-2 bg-indigo-100 text-indigo-600 rounded">
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clipRule="evenodd" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-900">{file.name}</p>
                  <p className="text-xs text-gray-500">{(file.size / (1024 * 1024)).toFixed(2)} MB</p>
                </div>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); setFile(null); }}
                className="text-gray-400 hover:text-red-500 p-1">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          )}

          {/* Query Input */}
          <div className="mt-4">
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              Your Question
            </label>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="What do you want to know about this document?"
              className="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              onKeyDown={(e) => { if (e.key === 'Enter' && canProcess) handleProcess(); }}
            />
            <p className="text-xs text-gray-400 mt-1">
              The pipeline will optimize the document context for this specific question.
            </p>
          </div>

          {/* Error */}
          {error && (
            <div className="mt-4 p-3 bg-red-50 text-red-600 rounded-lg text-sm">
              {error}
            </div>
          )}

          {/* Processing Status */}
          {isProcessing && (
            <div className="mt-4">
              {uploading && <UploadStatus progress={progress} status="uploading" />}
              {processing && (
                <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4">
                  <div className="flex items-center gap-3">
                    <svg className="w-5 h-5 text-indigo-600 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    <div>
                      <p className="text-indigo-800 font-medium">Running AI Pipeline...</p>
                      <p className="text-indigo-600 text-xs mt-0.5">
                        CrossEncoder pruning + LLMLingua-2 compression. This may take 15-90 seconds.
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Process Button */}
          <div className="mt-5 flex justify-end">
            <button
              onClick={handleProcess}
              disabled={!canProcess || isProcessing}
              className="bg-indigo-600 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isProcessing ? 'Processing...' : 'Run Pipeline'}
            </button>
          </div>
        </>
      )}

      {/* Pipeline Results */}
      <PipelineResults result={result} />
    </div>
  );
};

export default FileUpload;
