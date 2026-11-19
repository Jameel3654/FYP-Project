// Hook for document query operations
import { useState } from 'react';
import api from '../services/api';

export const useQuery = () => {
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState(null);
  const [tokenStats, setTokenStats] = useState(null);
  const [error, setError] = useState(null);

  const send = async (payload) => {
    setLoading(true);
    setError(null);
    setAnswer(null);
    setTokenStats(null);
    
    try {
      const res = await api.post('/query', payload, { timeout: 100000 });
      const data = res.data.data;
      
      setAnswer(data.answer);
      setTokenStats({
        ...data.tokenStats,
        model: data.model,
        provider: data.provider,
        warning: data.warning,
      });
      
      return res.data;
    } catch (err) {
      setError(err.response?.data?.error || err.response?.data?.message || 'Could not get an LLM answer. Please try again.');
      return null;
    } finally {
      setLoading(false);
    }
  };

  const submitQuery = (documentId, question, llmProvider = 'openai') =>
    send({ documentId, question, llmProvider });
  const submitContext = (context, question = '', documentId, llmProvider = 'openai') =>
    send({ ...(documentId ? { documentId } : { context }), question, llmProvider });
  return { loading, answer, tokenStats, error, submitQuery, submitContext };
};

export default useQuery;
