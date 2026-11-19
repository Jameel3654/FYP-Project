"""
extractor.py -- Universal Text Extraction Module
==================================================
Extracts clean text from ANY supported input type:
  PATH A: digital_pdf  -> PyMuPDF (fast, high quality)
  PATH B: scanned_pdf  -> PyMuPDF render + Tesseract OCR
  PATH C: image        -> Pillow preprocessing + Tesseract OCR
  PATH D: text_file    -> Direct UTF-8 read
  PATH E: direct_text  -> Already text, just clean and normalize

Every path includes text cleaning:
  - Fix broken hyphenated words across lines
  - Remove page numbers, headers, footers
  - Normalize whitespace and paragraph structure
  - Remove very short noise lines

Quality score: ratio of real English words to total tokens.
Language hint: basic detection using common English word frequency.

Usage:
  python -m core.extractor --file "path/to/file" --type digital_pdf
  python -m core.extractor --file "path/to/file"          (auto-detect)

Dependencies:
  pip install PyMuPDF pytesseract Pillow
  + Tesseract OCR installed on Windows for scanned/image paths
"""

import argparse
import os
import re
import sys
import string


# -- Common English words for language detection -----------------------
# If over 20% of words match this set, text is likely English
_COMMON_EN_WORDS = {
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
    "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
    "this", "but", "his", "by", "from", "they", "we", "say", "her",
    "she", "or", "an", "will", "my", "one", "all", "would", "there",
    "their", "what", "so", "up", "out", "if", "about", "who", "get",
    "which", "go", "me", "when", "make", "can", "like", "time", "no",
    "just", "him", "know", "take", "people", "into", "year", "your",
    "good", "some", "could", "them", "see", "other", "than", "then",
    "now", "look", "only", "come", "its", "over", "think", "also",
    "back", "after", "use", "two", "how", "our", "work", "first",
    "well", "way", "even", "new", "want", "because", "any", "these",
    "give", "day", "most", "us", "is", "are", "was", "were", "been",
    "has", "had", "did", "does", "may", "might", "shall", "should",
    "must", "need", "used", "each", "very", "more", "many", "such",
    "data", "model", "system", "method", "results", "based", "using",
    "paper", "proposed", "performance", "approach", "information",
}


# =====================================================================
# PATH A: Digital PDF Extraction (PyMuPDF)
# =====================================================================
def _extract_digital_pdf(file_path: str) -> dict:
    """
    Extract text from a digital PDF using PyMuPDF.
    PyMuPDF reads the actual text layer -- fast and accurate.

    IMPORTANT: Structured records (RECORD_ID blocks) are extracted
    from the RAW text BEFORE any cleaning, because cleaning destroys
    the newline structure needed to match record fields.
    """
    try:
        import pymupdf
    except ImportError:
        raise ImportError("PyMuPDF not installed. Run: pip install PyMuPDF")

    doc = pymupdf.open(file_path)
    all_pages_raw = []

    print(f"\n  Extracting text from {len(doc)} pages...")

    for page_num in range(len(doc)):
        page = doc[page_num]
        raw_text = page.get_text("text")

        if raw_text.strip():
            all_pages_raw.append(raw_text)
            print(f"    Page {page_num + 1}: {len(raw_text.split())} words (raw)")
        else:
            print(f"    Page {page_num + 1}: [no text - image page]")

    doc.close()

    # Step 1: Work on RAW text (newlines intact) -- pull out structured
    # records and strip layout noise BEFORE cleaning joins lines together.
    raw_full = "\n\n".join(all_pages_raw)
    records, raw_full = _preprocess_raw_text(raw_full)
    if records:
        print(f"    Structured records extracted: {len(records)} (kept exact)")

    # Step 2: Clean the remaining narrative text
    full_text = _clean_pdf_text(raw_full)
    full_text = _final_cleanup(full_text)

    return {
        "text": full_text,
        "word_count": len(full_text.split()),
        "char_count": len(full_text),
        "extraction_method": "pymupdf",
        "quality_score": _calculate_quality(full_text),
        "language_hint": _detect_language(full_text),
        "structured_records": records,
    }


# =====================================================================
# PATH B: Scanned PDF Extraction (PyMuPDF render + Tesseract OCR)
# =====================================================================
def _extract_scanned_pdf(file_path: str) -> dict:
    """
    Extract text from a scanned PDF by rendering each page as a
    high-res image and running Tesseract OCR.
    """
    try:
        import pymupdf
    except ImportError:
        raise ImportError("PyMuPDF not installed. Run: pip install PyMuPDF")

    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        raise ImportError(
            "OCR dependencies missing. Run: pip install pytesseract Pillow\n"
            "Also install Tesseract: https://github.com/UB-Mannheim/tesseract/wiki"
        )

    _configure_tesseract()

    doc = pymupdf.open(file_path)
    all_pages_text = []

    print(f"\n  OCR processing {len(doc)} scanned pages...")

    for page_num in range(len(doc)):
        page = doc[page_num]

        # Render at 300 DPI for good OCR quality
        zoom = 300 / 72
        matrix = pymupdf.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=matrix)

        img = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
        img = _preprocess_image_for_ocr(img)

        try:
            raw_text = pytesseract.image_to_string(img, lang="eng")
            cleaned = _clean_ocr_text(raw_text)
            all_pages_text.append(cleaned)
            word_count = len(cleaned.split())
            print(f"    Page {page_num + 1}: {word_count} words (OCR)")
        except Exception as e:
            print(f"    Page {page_num + 1}: [OCR failed - {e}]")

    doc.close()

    full_text = "\n\n".join(all_pages_text)
    full_text = _final_cleanup(full_text)

    return {
        "text": full_text,
        "word_count": len(full_text.split()),
        "char_count": len(full_text),
        "extraction_method": "tesseract",
        "quality_score": _calculate_quality(full_text),
        "language_hint": _detect_language(full_text),
    }


# =====================================================================
# PATH C: Image Extraction (Pillow + Tesseract OCR)
# =====================================================================
def _extract_image(file_path: str) -> dict:
    """
    Extract text from a standalone image using Tesseract OCR.
    Preprocesses the image for better accuracy.
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        raise ImportError(
            "OCR dependencies missing. Run: pip install pytesseract Pillow\n"
            "Also install Tesseract: https://github.com/UB-Mannheim/tesseract/wiki"
        )

    _configure_tesseract()

    print(f"\n  Processing image for OCR...")

    img = Image.open(file_path)
    print(f"    Original size: {img.size[0]}x{img.size[1]} pixels")

    img = _preprocess_image_for_ocr(img)

    try:
        raw_text = pytesseract.image_to_string(img, lang="eng")
        cleaned = _clean_ocr_text(raw_text)
        word_count = len(cleaned.split())
        print(f"    Words extracted: {word_count}")
    except Exception as e:
        raise RuntimeError(f"OCR failed on image: {e}")

    full_text = _final_cleanup(cleaned)

    return {
        "text": full_text,
        "word_count": len(full_text.split()),
        "char_count": len(full_text),
        "extraction_method": "tesseract",
        "quality_score": _calculate_quality(full_text),
        "language_hint": _detect_language(full_text),
    }


# =====================================================================
# PATH D: Text File Extraction (UTF-8 read)
# =====================================================================
def _extract_text_file(file_path: str) -> dict:
    """
    Read a plain text file with encoding fallback.
    Tries UTF-8 first, falls back to latin-1.
    """
    print(f"\n  Reading text file...")

    text = None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        print(f"    Encoding: UTF-8")
    except UnicodeDecodeError:
        pass

    if text is None:
        try:
            with open(file_path, "r", encoding="latin-1") as f:
                text = f.read()
            print(f"    Encoding: latin-1 (fallback)")
        except Exception as e:
            raise IOError(f"Cannot read text file: {e}")

    # Clean encoding artifacts
    text = text.replace("\x00", "")
    text = text.replace("\ufeff", "")
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\r", "\n", text)

    full_text = _final_cleanup(text)
    word_count = len(full_text.split())
    print(f"    Words read: {word_count}")

    return {
        "text": full_text,
        "word_count": word_count,
        "char_count": len(full_text),
        "extraction_method": "direct",
        "quality_score": _calculate_quality(full_text),
        "language_hint": _detect_language(full_text),
    }


# =====================================================================
# PATH E: Direct Text (already text, just clean)
# =====================================================================
def _extract_direct_text(raw_text: str) -> dict:
    """
    Process directly pasted text -- no file reading needed.
    This is the fastest path: just clean and normalize.

    Cleaning steps:
      1. Strip leading/trailing whitespace
      2. Remove zero-width characters and unicode noise
      3. Normalize multiple spaces to single space
      4. Normalize multiple newlines to double newline
    """
    print(f"\n  Processing direct text input...")

    text = raw_text

    # Remove zero-width and special unicode characters
    # These sneak in from web copy-paste and break tokenizers
    text = re.sub(r"[\u200b\u200c\u200d\ufeff\u00ad]", "", text)

    # Normalize whitespace
    text = re.sub(r"[ \t]+", " ", text)     # multiple spaces -> single
    text = re.sub(r"\r\n", "\n", text)       # Windows line endings
    text = re.sub(r"\r", "\n", text)         # Old Mac line endings
    text = re.sub(r"\n{3,}", "\n\n", text)   # 3+ newlines -> double

    text = text.strip()

    word_count = len(text.split())
    print(f"    Words: {word_count}")
    print(f"    Characters: {len(text)}")

    return {
        "text": text,
        "word_count": word_count,
        "char_count": len(text),
        "extraction_method": "direct",
        "quality_score": _calculate_quality(text),
        "language_hint": _detect_language(text),
    }


# =====================================================================
# Shared Helpers
# =====================================================================

def _configure_tesseract():
    """Set Tesseract path for Windows if not on PATH."""
    import pytesseract
    import shutil

    tesseract_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"C:\Users\MM COMPUTERS\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
    ]

    for path in tesseract_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            return

    if shutil.which("tesseract") is None:
        print(
            "\n  [WARNING] Tesseract OCR not found!\n"
            "  Download: https://github.com/UB-Mannheim/tesseract/wiki\n"
            "  Install to: C:\\Program Files\\Tesseract-OCR\\\n"
        )


def _preprocess_image_for_ocr(img):
    """
    Preprocess image for better OCR: grayscale, contrast boost, upscale.
    """
    from PIL import ImageEnhance

    if img.mode != "L":
        img = img.convert("L")

    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.5)

    if img.width < 1000:
        scale = 1000 / img.width
        new_size = (int(img.width * scale), int(img.height * scale))
        img = img.resize(new_size)

    return img


def _clean_pdf_text(text: str) -> str:
    """
    Clean raw text from digital PDF extraction.
    Fixes hyphenation, DOIs, URLs, citation noise, and short lines.
    """
    # Strip spaces/tabs/CR around newlines FIRST.
    # WHY: PyMuPDF emits lines like "text  \n  \n". The blank line holds
    # spaces, so it was never detected as a paragraph break and whole
    # pages got merged into one giant line.
    text = text.replace("\r", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)

    # Fix hyphenated words split across lines: "com-\nputer" -> "computer"
    text = re.sub(r"(\w+)-\s*\n\s*(\w+)", r"\1\2", text)

    # Single newlines -> space (but preserve double newlines = paragraphs)
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)

    # Fix spaced hyphens from broken words: "cross - encoder" -> "cross-encoder"
    text = re.sub(r"(\w+)\s+-\s+(\w+)", r"\1-\2", text)

    # Remove DOI artifacts: "10.18653/v1/D18-1259" or "18653 / v1 / D18 - 1259"
    text = re.sub(r"\d+\.\d+/[^\s]+", "", text)
    text = re.sub(r"\d{4,}/\s*v\d+\s*/\s*[A-Z]\d+-\d+", "", text)
    text = re.sub(r"\d{5}\s*/\s*v\d\s*/\s*[A-Z]\d+\s*-\s*\d+", "", text)

    # Remove URLs
    text = re.sub(r"https?://\S+", "", text)

    # Remove standalone page numbers
    text = re.sub(r"^\s*\d{1,4}\s*$", "", text, flags=re.MULTILINE)

    # Collapse multiple spaces
    text = re.sub(r"[ \t]+", " ", text)

    # Remove lines that are mostly numbers or special characters
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped == "":
            cleaned_lines.append("")
            continue
        # Count actual English words vs total tokens
        word_count = len(re.findall(r"[a-zA-Z]{2,}", stripped))
        total_count = len(stripped.split())
        if total_count == 0:
            continue
        # Keep lines with enough real words (>50% English words)
        if word_count / max(total_count, 1) > 0.5:
            if len(stripped.split()) >= 4 or len(stripped) > 40:
                cleaned_lines.append(stripped)

    return "\n".join(cleaned_lines)


def _clean_ocr_text(text: str) -> str:
    """Clean OCR output which has more noise than PDF text."""
    text = "".join(
        c for c in text if c in string.printable or c in "\n\r\t"
    )

    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and len(stripped) > 2:
            alpha_ratio = sum(1 for c in stripped if c.isalpha()) / len(stripped)
            if alpha_ratio > 0.3:
                cleaned_lines.append(stripped)

    text = "\n".join(cleaned_lines)
    text = re.sub(r"[ \t]+", " ", text)

    return text


# =====================================================================
# RAW text preprocessing (runs BEFORE cleaning, newlines intact)
# =====================================================================
# Lines that are pure layout markers -- never content
_RAW_NOISE_LINE_RE = re.compile(
    r"^\s*(\[PAGE\s*\d+\]|Document ID\s*:.*|End of (File|Document)\s*:.*|"
    r"Page\s+\d+(\s+of\s+\d+)?)\s*$",
    re.IGNORECASE,
)

# Common Roman-Urdu function words. A sentence is treated as Roman Urdu
# only if it has 3+ DIFFERENT words from this set and they make up 15%+
# of the sentence -- so normal English sentences are never removed.
_ROMAN_URDU_WORDS = {
    "hai", "hain", "mein", "aur", "ka", "ki", "ke", "ko", "yeh", "woh",
    "raha", "rahi", "rahe", "gaya", "gaye", "gayi", "kiya", "kiye", "taake",
    "aap", "ya", "sakein", "sakte", "mojood", "mukhtalif", "liye", "nahi",
    "bhi", "kar", "karein", "wala", "wali", "par", "agar", "lekin", "kya",
}


def _remove_broken_table_runs(lines: list, min_run: int = 6) -> list:
    """
    Remove runs of many consecutive very short lines.

    WHY: Tables, chart axes and figure labels come out of PDFs as one
    fragment per line ("Recor", "Accou", "Ali Raz", "70", "72" ...).
    Six or more such lines in a row are never readable prose.
    Real headings are single short lines followed by prose, so they
    are not affected.
    """
    def is_fragment(line: str) -> bool:
        s = line.strip()
        return bool(s) and len(s.split()) <= 3 and not s.endswith((".", "?", "!"))

    result = []
    i = 0
    while i < len(lines):
        if is_fragment(lines[i]):
            j = i
            while j < len(lines) and (is_fragment(lines[j]) or not lines[j].strip()):
                j += 1
            run = [l for l in lines[i:j] if l.strip()]
            if len(run) >= min_run:
                result.append("")      # keep paragraph separation
                i = j
                continue
        result.append(lines[i])
        i += 1
    return result


def _preprocess_raw_text(raw_text: str) -> tuple:
    """
    Prepare RAW PDF text before cleaning.

    Steps (order matters):
      1. Pull out structured records (RECORD_ID blocks) -- exact values.
      2. Remove layout marker lines ([PAGE 3], Document ID:, End of File:).
      3. Remove broken table/figure fragments (6+ tiny lines in a row).

    Returns:
        (records, cleaned_raw_text)
    """
    records = []
    try:
        from core.records import split_records_from_text
    except ImportError:
        try:
            from records import split_records_from_text
        except ImportError:
            split_records_from_text = None

    if split_records_from_text is not None:
        records, raw_text = split_records_from_text(raw_text)
    else:
        print("    [WARNING] records module not found -- record detection skipped")

    try:
        lines = raw_text.replace("\r", "").split("\n")
        # Marker lines become blank lines so paragraphs stay separated
        lines = ["" if _RAW_NOISE_LINE_RE.match(l) else l for l in lines]

        # arXiv side stamps: "arXiv:2501.16214v1 [cs.CL] 27 Jan 2025"
        lines = [re.sub(r"(arXiv:\S+\s*)?\[cs\.[A-Z]{2}\]\s*\d{1,2}\s+\w{3}\s+\d{4}", "", l)
                 for l in lines]

        # Running headers/footers: short lines repeated on 3+ pages
        # (paper title, journal name, "Confidential" ...). They break
        # sentences in the middle when pages are joined.
        counts = {}
        for l in lines:
            key = l.strip().lower()
            if 8 <= len(key) and len(key.split()) <= 15:
                counts[key] = counts.get(key, 0) + 1
        repeated = {k for k, c in counts.items() if c >= 3}
        if repeated:
            lines = [l if l.strip().lower() not in repeated else "" for l in lines]
            print(f"    Removed {len(repeated)} repeated header/footer lines")

        before = len([l for l in lines if l.strip()])
        lines = _remove_broken_table_runs(lines)
        after = len([l for l in lines if l.strip()])
        if before - after > 0:
            print(f"    Removed {before - after} table/figure fragment lines")
        raw_text = "\n".join(lines)
    except Exception as e:
        print(f"    [WARNING] Raw preprocessing failed: {e} -- continuing")

    return records, raw_text


def _is_roman_urdu(sentence: str) -> bool:
    """
    True if a sentence is mostly Roman Urdu (see _ROMAN_URDU_WORDS).
    Short lines (headings) need 2 distinct Urdu words at 25%+ density;
    longer sentences need 3 distinct words at 15%+ density.
    """
    words = re.findall(r"[a-z]+", sentence.lower())
    if len(words) < 4:
        return False
    hits = [w for w in words if w in _ROMAN_URDU_WORDS]
    ratio = len(hits) / len(words)
    if len(words) <= 10:
        return len(set(hits)) >= 2 and ratio >= 0.25
    return len(set(hits)) >= 3 and ratio >= 0.15


def _remove_roman_urdu_sentences(text: str) -> str:
    """
    Drop Roman-Urdu sentences (e.g. tester notes like "Yeh raha complete
    20 pages ka dummy document text") while keeping English sentences in
    the same paragraph.
    """
    out_paragraphs = []
    for para in text.split("\n"):
        if not para.strip():
            out_paragraphs.append(para)
            continue
        sentences = re.split(r"(?<=[.!?:])\s+", para)
        kept = [s for s in sentences if not _is_roman_urdu(s)]
        out_paragraphs.append(" ".join(kept))
    return "\n".join(out_paragraphs)


def _dedupe_paragraphs(text: str) -> str:
    """
    Remove repeated paragraphs (normalized, case-insensitive).
    WHY: Some PDFs contain the same pages twice (e.g. a document
    exported twice into one file). Duplicates waste tokens and make
    retrieval return the same text two times.
    """
    seen = set()
    out = []
    for para in text.split("\n"):
        norm = re.sub(r"\s+", " ", para.strip().lower())
        if norm and len(norm) > 30:
            if norm in seen:
                continue
            seen.add(norm)
        out.append(para)
    return "\n".join(out)


def _remove_references_section(text: str) -> str:
    """
    Remove the References/Bibliography section from academic papers.
    These are author lists and paper titles that add noise, not content.
    Only cuts if the marker appears in the second half of the document
    (to avoid cutting a mention of "references" in the body text).
    """
    stop_markers = [
        "\nreferences\n",
        "\nbibliography\n",
        "\nworks cited\n",
        "\nreference\n",
        "\ncitations\n",
        "\nreferences ",
        "\nbibliography ",
    ]
    text_lower = text.lower()
    earliest_cut = len(text)

    for marker in stop_markers:
        idx = text_lower.rfind(marker)  # rfind = last occurrence
        if idx != -1 and idx > len(text) * 0.5:
            # Only cut if references are in second half of document
            earliest_cut = min(earliest_cut, idx)

    if earliest_cut < len(text):
        return text[:earliest_cut].strip()
    return text


def _clean_document_noise(text: str) -> str:
    """
    Remove document-level noise while PRESERVING structured records.

    Removes:
      - Page markers: [PAGE 1], [PAGE 20]
      - Document ID lines: Document ID: DOC-xxx
      - Standalone metadata labels (Status:, Module:, etc.)
      - Urdu/Roman Urdu footer phrases
      - Lines under 5 words that are not record fields

    PRESERVES these record field patterns:
      ACCOUNT HOLDER, CITY, ACCOUNT NUMBER, RECORD_ID,
      BRANCH CODE, STATUS (when part of a record)
    """
    # Remove page markers
    text = re.sub(r'\[PAGE\s*\d+\]', '', text, flags=re.IGNORECASE)

    # Remove Document ID lines
    text = re.sub(r'Document ID\s*:\s*DOC-[\w-]+', '', text, flags=re.IGNORECASE)

    # Standalone metadata labels to REMOVE (not record fields)
    noise_labels = re.compile(
        r'^\s*(Module|Layer|Stage|Domain|Cluster ID|Node Reference|'
        r'Subsystem|Scope|Category|Protocol|Audit Reference|'
        r'Classification|Sector|Priority Level|Alert Code|'
        r'Region Tag|Compliance Flag)\s*:.*$',
        re.IGNORECASE
    )

    # NOTE: Roman-Urdu text is removed at SENTENCE level in
    # _remove_roman_urdu_sentences() -- a phrase list here used to wipe
    # entire English paragraphs (e.g. "ground truth" in research papers).

    lines = text.split('\n')
    clean_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        stripped_lower = stripped.lower()

        # Check if this line is a preserved record field
        is_record_field = any(
            p in stripped_lower for p in [
                'account holder', 'account number', 'record_id',
                'record id', 'branch code', 'clearing zone', 'city:',
            ]
        )
        # Also preserve lines with IBAN patterns
        if re.search(r'PK\d{2}[A-Z]{4}\d+', stripped, re.IGNORECASE):
            is_record_field = True

        # Always keep record fields
        if is_record_field:
            clean_lines.append(stripped)
            continue

        # Remove noise metadata labels
        if noise_labels.match(stripped):
            continue

        # Remove very short non-record lines (under 5 words)
        if len(stripped.split()) < 5:
            continue

        clean_lines.append(stripped)

    return '\n'.join(clean_lines)


def _final_cleanup(text: str) -> str:
    """
    Final cleanup for ALL extraction paths.
    Removes references, document noise, and normalizes whitespace.
    """
    # Remove references/bibliography section (if present)
    text = _remove_references_section(text)

    # Remove Roman-Urdu sentences (keeps English sentences around them)
    text = _remove_roman_urdu_sentences(text)

    # Remove document noise (page markers, metadata labels, short lines)
    text = _clean_document_noise(text)

    # Remove duplicated paragraphs (documents that repeat their pages)
    text = _dedupe_paragraphs(text)

    # Normalize multiple newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)
    return text.strip()


def _calculate_quality(text: str) -> float:
    """
    Quality score = ratio of real words (2+ chars, mostly letters) to total.
    0.85+ = excellent, 0.70+ = good, 0.50+ = fair, below = poor.
    """
    words = text.split()
    if len(words) == 0:
        return 0.0

    real_words = 0
    for word in words:
        clean = word.strip(string.punctuation)
        if len(clean) >= 2:
            letter_count = sum(1 for c in clean if c.isalpha())
            if len(clean) > 0 and letter_count / len(clean) >= 0.5:
                real_words += 1

    return round(real_words / len(words), 2)


def _detect_language(text: str) -> str:
    """
    Basic language detection using common English words.
    If over 15% of words are common English -> "en", else "unknown".
    """
    words = text.lower().split()
    if len(words) < 10:
        return "unknown"

    # Sample first 500 words for speed
    sample = words[:500]
    en_count = sum(1 for w in sample if w.strip(string.punctuation) in _COMMON_EN_WORDS)
    en_ratio = en_count / len(sample)

    return "en" if en_ratio > 0.15 else "unknown"


# =====================================================================
# Main extraction function -- the public API
# =====================================================================

def extract_text(input_data: str, input_type: str) -> dict:
    """
    Extract clean text from any supported input type.

    This is the MAIN function -- call this from the pipeline.

    Args:
        input_data: File path OR raw text string.
        input_type: One of "digital_pdf", "scanned_pdf", "image",
                    "text_file", "direct_text"

    Returns:
        dict with keys:
            - text: str
            - word_count: int
            - char_count: int
            - extraction_method: str
            - quality_score: float (0.0 to 1.0)
            - language_hint: "en" or "unknown"
    """
    print(f"\n{'=' * 60}")
    print(f"  TEXT EXTRACTION")
    print(f"{'=' * 60}")

    if input_type == "direct_text":
        print(f"  Input: Direct text ({len(input_data)} chars)")
    else:
        print(f"  File: {os.path.basename(input_data)}")
    print(f"  Type: {input_type}")

    # Route to the correct extraction path
    if input_type == "digital_pdf":
        result = _extract_digital_pdf(input_data)
    elif input_type == "scanned_pdf":
        result = _extract_scanned_pdf(input_data)
    elif input_type == "image":
        result = _extract_image(input_data)
    elif input_type == "text_file":
        result = _extract_text_file(input_data)
    elif input_type == "direct_text":
        result = _extract_direct_text(input_data)
    else:
        raise ValueError(
            f"Unknown input type: '{input_type}'. "
            f"Expected: digital_pdf, scanned_pdf, image, text_file, direct_text"
        )

    # Print summary
    quality_label = (
        "Excellent" if result["quality_score"] >= 0.85 else
        "Good" if result["quality_score"] >= 0.70 else
        "Fair" if result["quality_score"] >= 0.50 else
        "Poor"
    )
    print(f"\n  --- Extraction Summary ---")
    print(f"  Method:    {result['extraction_method']}")
    print(f"  Words:     {result['word_count']:,}")
    print(f"  Chars:     {result['char_count']:,}")
    print(f"  Quality:   {result['quality_score']} ({quality_label})")
    print(f"  Language:  {result['language_hint']}")

    # Ensure structured_records is always present
    if "structured_records" not in result:
        result["structured_records"] = []
    if result["structured_records"]:
        print(f"  Records:   {len(result['structured_records'])} structured records found")

    print(f"{'=' * 60}\n")

    return result


# -- CLI entry point ---------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="COF-RAG Text Extractor -- extracts text from any input type"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Path to file to extract text from")
    group.add_argument("--text", help="Direct text string to process")
    parser.add_argument(
        "--type", required=False, default=None,
        choices=["digital_pdf", "scanned_pdf", "image", "text_file", "direct_text"],
        help="Input type (auto-detected if not provided)"
    )
    args = parser.parse_args()

    # Determine input and type
    if args.text:
        input_data = args.text
        input_type = "direct_text"
    else:
        input_data = args.file
        input_type = args.type

    # Auto-detect type if not provided
    if input_type is None:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from utils.file_detector import detect_input_type
        detection = detect_input_type(input_data)
        input_type = detection["input_type"]

    try:
        result = extract_text(input_data, input_type)

        print("\n--- TEXT PREVIEW (first 500 chars) ---")
        print(result["text"][:500])
        print(f"\n--- End ({result['word_count']} words, "
              f"quality: {result['quality_score']}) ---")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)
