// Component displaying upload and processing status
import React from 'react';

const UploadStatus = ({ progress, status }) => {
  const getStatusText = () => {
    switch(status) {
      case 'uploading': return `Uploading... ${progress}%`;
      case 'processing': return 'Extracting text and generating embeddings...';
      case 'complete': return 'Ready!';
      default: return 'Processing...';
    }
  };

  return (
    <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
      <div className="flex justify-between items-center mb-2">
        <span className="text-sm font-medium text-indigo-700">{getStatusText()}</span>
        <span className="text-sm font-medium text-gray-500">{progress}%</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
        <div 
          className="bg-indigo-600 h-2.5 rounded-full transition-all duration-300 ease-out"
          style={{ width: `${progress}%` }}
        ></div>
      </div>
      {status === 'processing' && (
        <p className="text-xs text-gray-500 mt-3 flex items-center">
          <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-indigo-500" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          This might take a minute for large documents...
        </p>
      )}
    </div>
  );
};

export default UploadStatus;
