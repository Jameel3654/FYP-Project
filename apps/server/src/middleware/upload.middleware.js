/**
 * upload.middleware.js
 * Multer configuration for file uploads.
 * Accepts: PDF, images (JPG, PNG, WEBP), text files.
 */
import multer from 'multer';
import fs from 'fs';
import path from 'path';

// Upload directory
const UPLOAD_DIR = path.join(process.cwd(), '../../data/raw/');

if (!fs.existsSync(UPLOAD_DIR)) {
  fs.mkdirSync(UPLOAD_DIR, { recursive: true });
}

const storage = multer.diskStorage({
  destination: function (req, file, cb) {
    cb(null, UPLOAD_DIR);
  },
  filename: function (req, file, cb) {
    const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9);
    cb(null, uniqueSuffix + '-' + file.originalname);
  }
});

// Accept PDF, images, and text files
const ALLOWED_MIMES = [
  'application/pdf',
  'image/jpeg',
  'image/png',
  'image/webp',
  'text/plain',
];

const fileFilter = (req, file, cb) => {
  if (ALLOWED_MIMES.includes(file.mimetype)) {
    cb(null, true);
  } else {
    cb(new Error(`File type ${file.mimetype} not allowed. Accepted: PDF, JPG, PNG, WEBP, TXT`), false);
  }
};

const upload = multer({
  storage: storage,
  fileFilter: fileFilter,
  limits: {
    fileSize: 20 * 1024 * 1024 // 20MB
  }
});

export const uploadMiddleware = upload.single('document');
