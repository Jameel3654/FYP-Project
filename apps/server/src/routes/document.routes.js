/**
 * document.routes.js
 * Express routes for document management and AI pipeline.
 */
import express from 'express';
import {
  upload,
  processDocument,
  processText,
  getAll,
  getById,
  deleteDoc
} from '../controllers/document.controller.js';
import { protect } from '../middleware/auth.middleware.js';
import { uploadMiddleware } from '../middleware/upload.middleware.js';

const router = express.Router();

// Auth required for all routes
router.use(protect);

// Upload file + run pipeline (multipart form: document + query)
router.post('/upload', uploadMiddleware, upload);

// Process an existing document with a new query
router.post('/process', processDocument);

// Process direct text (no file)
router.post('/process-text', processText);

// CRUD
router.get('/', getAll);
router.get('/:id', getById);
router.delete('/:id', deleteDoc);

export default router;
