/**
 * aiEngine.service.js
 * Service for communicating with the COF-RAG AI Engine (FastAPI).
 * 
 * Architecture:
 *   React (5173) -> Node.js (5000) -> this service -> FastAPI (8000)
 * 
 * Three methods:
 *   1. processFile(filePath, query)  -- send file path for processing
 *   2. processText(text, query)      -- send direct text for processing
 *   3. uploadAndProcess(filePath, query) -- upload file via multipart
 */
import axios from 'axios';
import fs from 'fs';
import FormData from 'form-data';
import dotenv from 'dotenv';

dotenv.config();

const API_URL = process.env.AI_ENGINE_URL || 'http://localhost:8000';

// Axios instance with generous timeout (pipeline can take 60-120s)
const aiEngineApi = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 300000, // 5 minutes -- models are slow on CPU
});

/**
 * Process a file that's already on the server (e.g., uploaded to uploads/).
 * Sends the file path to FastAPI which reads it directly.
 */
export const processFile = async (filePath, query, topK = 5) => {
  try {
    const response = await aiEngineApi.post('/api/process', {
      file_path: filePath,
      query,
      top_k: topK,
    });
    return response.data;
  } catch (error) {
    console.error('AI Engine process error:', error.response?.data || error.message);
    throw new Error(error.response?.data?.detail || 'Failed to process document');
  }
};

/**
 * Process direct text (no file needed).
 * For when user pastes text in the frontend instead of uploading.
 */
export const processText = async (text, query, topK = 5) => {
  try {
    const response = await aiEngineApi.post('/api/process', {
      text,
      query,
      top_k: topK,
    });
    return response.data;
  } catch (error) {
    console.error('AI Engine text process error:', error.response?.data || error.message);
    throw new Error(error.response?.data?.detail || 'Failed to process text');
  }
};

/**
 * Upload a file to FastAPI via multipart form and process it.
 * Use this when the file is on the Node.js server and needs
 * to be sent to the AI engine (different machine scenario).
 */
export const uploadAndProcess = async (filePath, query, topK = 5) => {
  try {
    const form = new FormData();
    form.append('file', fs.createReadStream(filePath));
    form.append('query', query);
    form.append('top_k', String(topK));

    const response = await axios.post(`${API_URL}/api/process/upload`, form, {
      headers: form.getHeaders(),
      timeout: 300000,
    });
    return response.data;
  } catch (error) {
    console.error('AI Engine upload error:', error.response?.data || error.message);
    throw new Error(error.response?.data?.detail || 'Failed to upload and process');
  }
};

/**
 * Health check -- verify the AI engine is running.
 */
export const healthCheck = async () => {
  try {
    const response = await aiEngineApi.get('/health');
    return response.data;
  } catch (error) {
    throw new Error('AI Engine is offline');
  }
};

// Legacy exports for backward compatibility with existing controllers
export const processDocument = processFile;
export { generateAnswer as queryDocument } from './llm.service.js';
