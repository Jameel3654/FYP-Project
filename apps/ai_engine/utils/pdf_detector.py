"""
pdf_detector.py
---------------
Detects whether a PDF is digital or scanned using PyMuPDF.

This module does not use OCR, LLMs, API keys, or network calls. It only checks
how much text PyMuPDF can extract from each page.

Standalone test:
    python apps/ai_engine/utils/pdf_detector.py --pdf "path/to/test.pdf"
"""

from __future__ import annotations

import argparse
from pathlib import Path

import fitz  # PyMuPDF


MIN_TEXT_CHARS_PER_PAGE = 50
DIGITAL_TEXT_PAGE_THRESHOLD = 0.80
SCANNED_BLANK_PAGE_THRESHOLD = 0.20


def _clean_page_text(text: str) -> str:
    """
    Normalize extracted page text before deciding whether a page has useful text.

    PyMuPDF can return whitespace-heavy text for pages that are visually blank or
    image-only. Collapsing whitespace gives a fairer character count.
    """
    return " ".join(text.split())


def detect_pdf_type(file_path: str) -> tuple[str, float]:
    """
    Detect whether a PDF is mostly digital text or likely scanned images.

    A page is treated as text-based when PyMuPDF extracts at least
    MIN_TEXT_CHARS_PER_PAGE non-whitespace characters. If more than 80% of pages
    are text-based, the PDF is "digital". If more than 20% are blank/image pages,
    the PDF is "scanned". Borderline files default to "scanned" because they will
    need OCR handling for reliable processing.

    Args:
        file_path: Absolute or relative path to a PDF file.

    Returns:
        A tuple: (pdf_type, confidence_percentage), where pdf_type is "digital"
        or "scanned".
    """
    pdf_path = Path(file_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF detection failed: file not found: {pdf_path}")

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"PDF detection failed: expected a .pdf file: {pdf_path}")

    try:
        document = fitz.open(pdf_path)
    except Exception as error:
        raise ValueError(f"PDF detection failed: could not open PDF: {error}") from error

    try:
        total_pages = document.page_count

        if total_pages == 0:
            raise ValueError("PDF detection failed: PDF has zero pages")

        text_pages = 0
        blank_or_image_pages = 0

        print("\nPDF detection started")
        print(f"File: {pdf_path}")
        print(f"Total pages: {total_pages}")

        for page_index in range(total_pages):
            page = document.load_page(page_index)
            extracted_text = _clean_page_text(page.get_text("text"))
            char_count = len(extracted_text)

            if char_count >= MIN_TEXT_CHARS_PER_PAGE:
                text_pages += 1
                page_label = "TEXT"
            else:
                blank_or_image_pages += 1
                page_label = "BLANK_OR_IMAGE"

            print(
                f"Page {page_index + 1}: {page_label} "
                f"({char_count} extractable characters)"
            )

        text_ratio = text_pages / total_pages
        blank_or_image_ratio = blank_or_image_pages / total_pages

        if text_ratio > DIGITAL_TEXT_PAGE_THRESHOLD:
            pdf_type = "digital"
            confidence = round(text_ratio * 100, 2)
        elif blank_or_image_ratio > SCANNED_BLANK_PAGE_THRESHOLD:
            pdf_type = "scanned"
            confidence = round(blank_or_image_ratio * 100, 2)
        else:
            pdf_type = "scanned"
            confidence = round((1 - text_ratio) * 100, 2)

        print("\nPDF detection result")
        print(f"Type: {pdf_type}")
        print(f"Confidence: {confidence}%")
        print(f"Text pages: {text_pages}/{total_pages}")
        print(f"Blank/image pages: {blank_or_image_pages}/{total_pages}\n")

        return pdf_type, confidence
    finally:
        document.close()


def _build_arg_parser() -> argparse.ArgumentParser:
    """Create the command-line parser used for standalone file testing."""
    parser = argparse.ArgumentParser(description="Detect whether a PDF is digital or scanned.")
    parser.add_argument("--pdf", required=True, help="Path to the PDF file to inspect.")
    return parser


if __name__ == "__main__":
    args = _build_arg_parser().parse_args()
    detected_type, detected_confidence = detect_pdf_type(args.pdf)
    print(f"Final result: {detected_type} ({detected_confidence}% confidence)")
