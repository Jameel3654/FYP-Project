/**
 * query.routes.js
 * Express routes for queries.
 */
import express from 'express';
import { submitQuery, getHistory, getStats, getById } from '../controllers/query.controller.js';
import { protect } from '../middleware/auth.middleware.js';

const router = express.Router();

router.use(protect);

router.post('/', submitQuery);
router.get('/history', getHistory);
router.get('/stats', getStats);
router.get('/:id', getById);

export default router;
