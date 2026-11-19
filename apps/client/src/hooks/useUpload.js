// Hook for file upload + pipeline processing
import { useState } from 'react';
import api from '../services/api';

export const useUpload = () => {
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  /**
   * Upload file + run AI pipeline in one step.
   * @param {File} file - The file to upload
   * @param {string} query - The question to optimize context for
   * @param {number} topK - Number of chunks to retrieve
   */
  const uploadAndProcess = async (file, query, topK = 5) => {
    setUploading(true);
    setProcessing(false);
    setProgress(0);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append('document', file);
    formData.append('query', query);
    formData.append('top_k', String(topK));

    try {
      const res = await api.post('/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 300000, // 5 min timeout for pipeline
        onUploadProgress: (progressEvent) => {
          const pct = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setProgress(pct);
          if (pct >= 100) {
            setUploading(false);
            setProcessing(true); // File uploaded, now processing
          }
        },
      });

      setResult(res.data);
      return res.data;
    } catch (err) {
      const msg = err.response?.data?.error || err.message || 'Processing failed';
      setError(msg);
      return null;
    } finally {
      setUploading(false);
      setProcessing(false);
    }
  };

  /**
   * Process direct text (no file upload).
   */
  const processText = async (text, query, topK = 5) => {
    setProcessing(true);
    setError(null);
    setResult(null);

    try {
      const res = await api.post('/documents/process-text', {
        text, query, top_k: topK
      }, { timeout: 300000 });

      setResult(res.data);
      return res.data;
    } catch (err) {
      const msg = err.response?.data?.error || err.message || 'Processing failed';
      setError(msg);
      return null;
    } finally {
      setProcessing(false);
    }
  };

  const reset = () => {
    setUploading(false);
    setProcessing(false);
    setProgress(0);
    setResult(null);
    setError(null);
  };

  return {
    uploading, processing, progress, result, error,
    uploadAndProcess, processText, reset
  };
};

export default useUpload;
