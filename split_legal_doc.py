#!/usr/bin/env python3
"""
Legal Document Splitter

Automatically splits multi-document PDF files into individual documents
using multiple boundary detection methods:
1. Page numbering patterns ("Page X of Y" or standalone "Page X")
2. Document type header changes (e.g., AFFIDAVIT → SEARCH WARRANT)
3. Page number reset detection (Page 3 → Page 1)

Author: Created for legal discovery document processing
License: MIT
"""

import sys
import argparse
import gc
import json
from pathlib import Path
import re
from typing import List, Tuple, Optional, NamedTuple, Dict, Any
import pdfplumber
from pypdf import PdfReader, PdfWriter


# ============================================================================
# CONFIGURATION
# ============================================================================

# Page numbering patterns - "Page X of Y" format
PAGE_OF_PATTERNS = [
    r'PAGE\s+(\d+)\s+OF\s+(\d+)',       # "PAGE 3 OF 5"
    r'PA\s*[GE]+\s*(\d+)\s+OF\s*(\d+)', # Handles OCR errors
    r'Page\s+(\d+)\s+of\s+(\d+)',       # "Page 3 of 5"
    r'(\d+)\s+of\s+(\d+)\s+pages?',     # "3 of 5 pages"
]

# Standalone page number patterns - "Page X" without "of Y"
STANDALONE_PAGE_PATTERNS = [
    r'PAGE\s+(\d+)\s*$',                # "PAGE 3" at end of line
    r'Page\s+(\d+)\s*$',                # "Page 3" at end of line
    r'^PAGE\s+(\d+)',                   # "PAGE 3" at start of line
    r'^Page\s+(\d+)',                   # "Page 3" at start of line
    r'[-–—]\s*(\d+)\s*[-–—]',           # "- 3 -" or "— 3 —"
    r'PAGE\s+(\d+)\s*\n',               # "PAGE 3" followed by newline
    r'Page\s+(\d+)\s*\n',               # "Page 3" followed by newline
]

# Document type keywords for header detection
# These are checked in headers to detect document type changes
HEADER_DOC_TYPES = [
    'SEARCH WARRANT',
    'AFFIDAVIT',
    'SUBPOENA',
    'COURT ORDER',
    'RETURN AND TABULATION',
    'RETURN OF SERVICE',
    'MOTION',
    'DECLARATION',
    'EXHIBIT',
    'COMPLAINT',
    'ANSWER',
    'SUMMONS',
    'PETITION',
    'ORDER',
    'WARRANT',
    'NOTICE',
    'CERTIFICATE',
]

# Document type keywords and their clean names for filenames
DOCUMENT_TYPES = {
    'search warrant': 'search_warrant',
    'affidavit': 'affidavit',
    'subpoena': 'subpoena',
    'court order': 'court_order',
    'return and tabulation': 'return_tabulation',
    'return of service': 'return_of_service',
    'return': 'return',
    'motion': 'motion',
    'declaration': 'declaration',
    'exhibit': 'exhibit',
    'complaint': 'complaint',
    'answer': 'answer',
    'summons': 'summons',
    'petition': 'petition',
    'order': 'order',
    'warrant': 'warrant',
    'notice': 'notice',
    'certificate': 'certificate',
}

# Case number patterns (customize for your jurisdiction)
CASE_PATTERNS = [
    r'tnt-?\d+-\d+',           # TNT-72-24
    r'ccu-?\d+-\d+',           # CCU-02587-2024
    r'\d+th\s+district',       # 86th District
    r'\d+-cv-\d+',             # 2024-CV-001
    r'case\s*(?:no|number)[:\s]*([a-z0-9\-]+)',  # Case No: XXX
]

# Minimum characters to consider a page as having OCR text
MIN_TEXT_LENGTH = 50

# Checkpoint interval - save progress every N pages
CHECKPOINT_INTERVAL = 50


# ============================================================================
# DATA STRUCTURES
# ============================================================================

class DocumentInfo(NamedTuple):
    """Information about a detected document segment."""
    start_page: int
    end_page: int
    title: str
    has_no_ocr_pages: bool
    no_ocr_page_count: int


# ============================================================================
# CHECKPOINT FUNCTIONS
# ============================================================================

def get_checkpoint_path(pdf_path: Path, output_dir: Path) -> Path:
    """Get the checkpoint file path for a given PDF."""
    return output_dir / f".{pdf_path.stem}.checkpoint.json"


def save_checkpoint(checkpoint_path: Path, data: Dict[str, Any]) -> None:
    """Save checkpoint data to disk."""
    try:
        with open(checkpoint_path, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save checkpoint: {e}", file=sys.stderr)


def load_checkpoint(checkpoint_path: Path) -> Optional[Dict[str, Any]]:
    """Load checkpoint data from disk."""
    if not checkpoint_path.exists():
        return None
    try:
        with open(checkpoint_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load checkpoint: {e}", file=sys.stderr)
        return None


def delete_checkpoint(checkpoint_path: Path) -> None:
    """Delete checkpoint file after successful completion."""
    try:
        if checkpoint_path.exists():
            checkpoint_path.unlink()
    except Exception:
        pass  # Ignore errors deleting checkpoint


def documents_to_list(documents: List[DocumentInfo]) -> List[Dict]:
    """Convert DocumentInfo list to JSON-serializable list."""
    return [
        {
            'start_page': d.start_page,
            'end_page': d.end_page,
            'title': d.title,
            'has_no_ocr_pages': d.has_no_ocr_pages,
            'no_ocr_page_count': d.no_ocr_page_count
        }
        for d in documents
    ]


def list_to_documents(data: List[Dict]) -> List[DocumentInfo]:
    """Convert JSON list back to DocumentInfo list."""
    return [
        DocumentInfo(
            start_page=d['start_page'],
            end_page=d['end_page'],
            title=d['title'],
            has_no_ocr_pages=d['has_no_ocr_pages'],
            no_ocr_page_count=d['no_ocr_page_count']
        )
        for d in data
    ]


# ============================================================================
# CORE FUNCTIONS
# ============================================================================

def extract_page_of_info(text: str, debug: bool = False) -> Tuple[Optional[int], Optional[int]]:
    """
    Extract "Page X of Y" numbering from page text.

    Args:
        text: Text content from a PDF page
        debug: If True, print debug information

    Returns:
        Tuple of (current_page, total_pages) or (None, None) if not found
    """
    # Search first 2000 characters and last 500 (header/footer areas)
    search_text = text[:2000] + "\n" + text[-500:] if len(text) > 2500 else text
    search_upper = search_text.upper()

    for pattern in PAGE_OF_PATTERNS:
        match = re.search(pattern, search_upper, re.IGNORECASE | re.MULTILINE)
        if match:
            current_page = int(match.group(1))
            total_pages = int(match.group(2))
            if debug:
                print(f"    Found: Page {current_page} of {total_pages}")
            return (current_page, total_pages)

    return (None, None)


def extract_standalone_page(text: str, debug: bool = False) -> Optional[int]:
    """
    Extract standalone page number (without "of Y") from page text.

    Args:
        text: Text content from a PDF page
        debug: If True, print debug information

    Returns:
        Page number if found, None otherwise
    """
    # Search header and footer areas
    search_text = text[:1000] + "\n" + text[-500:] if len(text) > 1500 else text

    for pattern in STANDALONE_PAGE_PATTERNS:
        match = re.search(pattern, search_text, re.IGNORECASE | re.MULTILINE)
        if match:
            page_num = int(match.group(1))
            # Sanity check - page numbers are usually reasonable
            if 1 <= page_num <= 9999:
                if debug:
                    print(f"    Found standalone: Page {page_num}")
                return page_num

    return None


def extract_header_doc_type(text: str, debug: bool = False) -> Optional[str]:
    """
    Extract document type from page header.

    Looks for document type keywords in the first 500 characters
    (typically the header area).

    Args:
        text: Text content from a PDF page
        debug: If True, print debug information

    Returns:
        Document type string if found, None otherwise
    """
    header_text = text[:500].upper()

    for doc_type in HEADER_DOC_TYPES:
        if doc_type in header_text:
            if debug:
                print(f"    Header type: {doc_type}")
            return doc_type

    return None


def extract_document_title(text: str) -> Optional[str]:
    """
    Extract document title from page text.

    Looks for lines containing legal document keywords in the first
    500 characters of the page.

    Args:
        text: Page text content

    Returns:
        Document title if found, None otherwise
    """
    lines = text[:500].split('\n')

    for line in lines[:10]:  # Check first 10 lines
        line_clean = line.strip()

        # Must be reasonable title length
        if len(line_clean) < 10 or len(line_clean) > 100:
            continue

        # Check if contains legal document keywords
        line_upper = line_clean.upper()
        if any(doc_type in line_upper for doc_type in HEADER_DOC_TYPES):
            return line_clean

    return None


def is_page_no_ocr(text: str) -> bool:
    """
    Check if a page has insufficient OCR text.

    Args:
        text: Extracted text from page

    Returns:
        True if page appears to have no/insufficient OCR text
    """
    if not text:
        return True
    # Strip whitespace and check length
    clean_text = text.strip()
    return len(clean_text) < MIN_TEXT_LENGTH


def analyze_pdf(pdf_path: Path, output_dir: Path = None, debug: bool = False,
                resume: bool = False) -> Optional[List[DocumentInfo]]:
    """
    Analyze a PDF file to detect document boundaries.

    Uses multiple detection methods:
    1. "Page X of Y" patterns - boundary when X == Y
    2. Standalone "Page X" - boundary when page resets to 1
    3. Header document type changes - boundary when type changes

    Supports checkpointing for crash recovery on large PDFs.

    Args:
        pdf_path: Path to PDF file
        output_dir: Directory for checkpoint file (default: same as PDF)
        debug: If True, print debug information
        resume: If True, resume from checkpoint if available

    Returns:
        List of DocumentInfo tuples for each document
        Returns None if no boundaries detected or only 1 document
    """
    if output_dir is None:
        output_dir = pdf_path.parent

    checkpoint_path = get_checkpoint_path(pdf_path, output_dir)

    if debug:
        print(f"\nAnalyzing: {pdf_path.name}")
        print("=" * 70)

    # Initialize state
    documents = []
    current_start = 0
    current_title = None
    current_no_ocr_count = 0
    prev_standalone_page = None
    prev_header_type = None
    start_page = 0

    # Check for existing checkpoint
    if resume and checkpoint_path.exists():
        checkpoint = load_checkpoint(checkpoint_path)
        if checkpoint and checkpoint.get('pdf_path') == str(pdf_path):
            print(f"  Resuming from checkpoint (page {checkpoint['last_page'] + 1})...")
            documents = list_to_documents(checkpoint.get('documents', []))
            current_start = checkpoint.get('current_start', 0)
            current_title = checkpoint.get('current_title')
            current_no_ocr_count = checkpoint.get('current_no_ocr_count', 0)
            prev_standalone_page = checkpoint.get('prev_standalone_page')
            prev_header_type = checkpoint.get('prev_header_type')
            start_page = checkpoint['last_page'] + 1
            if debug:
                print(f"  Loaded {len(documents)} documents from checkpoint")

    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pdf_pages = len(pdf.pages)

            if debug:
                print(f"Total pages: {total_pdf_pages}\n")

            if start_page >= total_pdf_pages:
                print("  Already fully processed.")
                delete_checkpoint(checkpoint_path)
                return documents if len(documents) > 1 else None

            for page_num in range(start_page, total_pdf_pages):
                # Progress indicator with checkpoint info
                docs_found = len(documents)
                print(f"\r  Scanning page {page_num + 1}/{total_pdf_pages} ({docs_found} docs found)...", end="", flush=True)

                try:
                    page = pdf.pages[page_num]
                    text = page.extract_text() or ""

                    # Memory management: flush page cache after text extraction
                    if hasattr(page, 'flush_cache'):
                        page.flush_cache()

                    # Periodic checkpoint and garbage collection
                    if page_num > 0 and page_num % CHECKPOINT_INTERVAL == 0:
                        # Save checkpoint
                        checkpoint_data = {
                            'pdf_path': str(pdf_path),
                            'total_pages': total_pdf_pages,
                            'last_page': page_num,
                            'documents': documents_to_list(documents),
                            'current_start': current_start,
                            'current_title': current_title,
                            'current_no_ocr_count': current_no_ocr_count,
                            'prev_standalone_page': prev_standalone_page,
                            'prev_header_type': prev_header_type,
                        }
                        save_checkpoint(checkpoint_path, checkpoint_data)
                        gc.collect()

                    # Track no-OCR pages
                    if is_page_no_ocr(text):
                        current_no_ocr_count += 1
                        if debug:
                            print(f"\n    Page {page_num + 1}: No OCR text detected")

                    # === METHOD 1: "Page X of Y" detection ===
                    current_page, page_total = extract_page_of_info(text, debug)

                    if current_page and page_total:
                        # Check if this is the last page of a document
                        if current_page == page_total:
                            doc_title = extract_document_title(text) or current_title or "Unknown"
                            documents.append(DocumentInfo(
                                start_page=current_start,
                                end_page=page_num,
                                title=doc_title,
                                has_no_ocr_pages=current_no_ocr_count > 0,
                                no_ocr_page_count=current_no_ocr_count
                            ))

                            if debug:
                                print(f"\n  Page {page_num + 1}: Document ends (Page {current_page} of {page_total})")
                                print(f"    Range: pages {current_start + 1}-{page_num + 1}")
                                if current_no_ocr_count > 0:
                                    print(f"    No-OCR pages: {current_no_ocr_count}")

                            # Reset for next document
                            if page_num + 1 < total_pdf_pages:
                                current_start = page_num + 1
                                current_title = None
                                current_no_ocr_count = 0
                                prev_standalone_page = None
                                prev_header_type = None

                        # Update title if found
                        if not current_title:
                            current_title = extract_document_title(text)

                        continue  # Skip other detection methods if Page X of Y found

                    # === METHOD 2: Standalone page number reset detection ===
                    standalone_page = extract_standalone_page(text, debug)

                    if standalone_page is not None:
                        # Boundary if page resets to 1 (and we had a previous page > 1)
                        if standalone_page == 1 and prev_standalone_page is not None and prev_standalone_page > 1:
                            # The PREVIOUS page was the end of a document
                            if page_num > current_start:  # Ensure we have pages to split
                                doc_title = current_title or "Unknown"
                                documents.append(DocumentInfo(
                                    start_page=current_start,
                                    end_page=page_num - 1,
                                    title=doc_title,
                                    has_no_ocr_pages=current_no_ocr_count > 0,
                                    no_ocr_page_count=current_no_ocr_count
                                ))

                                if debug:
                                    print(f"\n  Page {page_num + 1}: New document (page reset to 1)")
                                    print(f"    Previous doc range: pages {current_start + 1}-{page_num}")

                                # Reset for new document
                                current_start = page_num
                                current_title = extract_document_title(text)
                                current_no_ocr_count = 0 if not is_page_no_ocr(text) else 1
                                prev_header_type = None

                        prev_standalone_page = standalone_page

                    # === METHOD 3: Header document type change detection ===
                    header_type = extract_header_doc_type(text, debug)

                    if header_type:
                        # Boundary if document type changed
                        if prev_header_type is not None and header_type != prev_header_type:
                            # The PREVIOUS page was the end of a document
                            if page_num > current_start:
                                doc_title = current_title or prev_header_type or "Unknown"
                                documents.append(DocumentInfo(
                                    start_page=current_start,
                                    end_page=page_num - 1,
                                    title=doc_title,
                                    has_no_ocr_pages=current_no_ocr_count > 0,
                                    no_ocr_page_count=current_no_ocr_count
                                ))

                                if debug:
                                    print(f"\n  Page {page_num + 1}: New document (header changed: {prev_header_type} → {header_type})")
                                    print(f"    Previous doc range: pages {current_start + 1}-{page_num}")

                                # Reset for new document
                                current_start = page_num
                                current_title = extract_document_title(text) or header_type
                                current_no_ocr_count = 0 if not is_page_no_ocr(text) else 1
                                prev_standalone_page = standalone_page

                        prev_header_type = header_type

                        # Update title if not set
                        if not current_title:
                            current_title = extract_document_title(text) or header_type

                except Exception as e:
                    if debug:
                        print(f"\n  Error on page {page_num + 1}: {e}")
                finally:
                    # Ensure text is cleared to help GC
                    text = None

            # Clear the progress line
            print("\r" + " " * 50 + "\r", end="", flush=True)

            # Add final document if we have boundaries
            if current_start < total_pdf_pages:
                if len(documents) == 0:
                    if debug:
                        print("No document boundaries detected")
                    return None
                else:
                    documents.append(DocumentInfo(
                        start_page=current_start,
                        end_page=total_pdf_pages - 1,
                        title=current_title or "Unknown",
                        has_no_ocr_pages=current_no_ocr_count > 0,
                        no_ocr_page_count=current_no_ocr_count
                    ))

                    if debug:
                        print(f"  Final document: pages {current_start + 1}-{total_pdf_pages}")

        # Final cleanup after PDF processing
        gc.collect()

        # Delete checkpoint on successful completion
        delete_checkpoint(checkpoint_path)

    except Exception as e:
        print(f"\nError analyzing PDF: {e}", file=sys.stderr)
        print(f"  Checkpoint saved - use --resume to continue", file=sys.stderr)
        gc.collect()
        return None

    # Only return if we found multiple documents
    if len(documents) > 1:
        if debug:
            print(f"\nDetected {len(documents)} separate documents")
            no_ocr_docs = sum(1 for d in documents if d.has_no_ocr_pages)
            if no_ocr_docs > 0:
                print(f"  {no_ocr_docs} document(s) contain pages with no OCR text")
        return documents
    else:
        if debug:
            print("\nOnly 1 document detected (no split needed)")
        delete_checkpoint(checkpoint_path)  # Clean up checkpoint
        return None


def clean_filename(text: str) -> str:
    """
    Convert document title to clean filename component.

    Args:
        text: Document title or description

    Returns:
        Cleaned string suitable for filename
    """
    if not text or text == "Unknown":
        return "document"

    text_lower = text.lower()

    # Identify document type
    doc_type = "legal_document"  # default
    for keyword, clean_name in DOCUMENT_TYPES.items():
        if keyword in text_lower:
            doc_type = clean_name
            break

    # Try to extract case identifier
    for pattern in CASE_PATTERNS:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            identifier = match.group(0).lower().replace(' ', '_')
            return f"{doc_type}_{identifier}"

    return doc_type


def split_pdf(pdf_path: Path, documents: List[DocumentInfo],
              output_dir: Path, delete_original: bool = False,
              debug: bool = False) -> List[Path]:
    """
    Split PDF into separate files based on detected boundaries.

    Files are named by document type with per-type counters:
        search_warrant_001.pdf, affidavit_001.pdf, search_warrant_002.pdf

    Args:
        pdf_path: Path to input PDF
        documents: List of DocumentInfo tuples
        output_dir: Directory for output files
        delete_original: If True, delete original file after successful split
        debug: If True, print debug information

    Returns:
        List of created file paths
    """
    if debug:
        print(f"\nSplitting into {len(documents)} files...")
        print("=" * 70)

    reader = PdfReader(pdf_path)
    output_files = []

    # Track per-type counters for meaningful filenames
    type_counters: dict[str, int] = {}

    for idx, doc in enumerate(documents):
        num_pages = doc.end_page - doc.start_page + 1

        # Get clean document type name
        doc_type_clean = clean_filename(doc.title)

        # Increment per-type counter
        type_counters[doc_type_clean] = type_counters.get(doc_type_clean, 0) + 1
        type_count = type_counters[doc_type_clean]

        # Create filename: {type}_{NNN}.pdf with optional No_OCR prefix
        prefix = "No_OCR_" if doc.has_no_ocr_pages else ""
        filename = f"{prefix}{doc_type_clean}_{type_count:03d}.pdf"
        output_path = output_dir / filename

        try:
            # Create writer
            writer = PdfWriter()

            # Add pages
            for page_idx in range(doc.start_page, doc.end_page + 1):
                writer.add_page(reader.pages[page_idx])

            # Write file
            with open(output_path, "wb") as output_file:
                writer.write(output_file)

            size_kb = output_path.stat().st_size / 1024

            if debug:
                print(f"  [{idx + 1}/{len(documents)}] Created: {filename}")
                print(f"      Pages {doc.start_page + 1}-{doc.end_page + 1} ({num_pages} pages, {size_kb:.1f} KB)")
                if doc.has_no_ocr_pages:
                    print(f"      ⚠ Contains {doc.no_ocr_page_count} page(s) with no OCR text")
            else:
                status = " [No OCR]" if doc.has_no_ocr_pages else ""
                print(f"  → {filename} (pages {doc.start_page + 1}-{doc.end_page + 1}){status}")

            output_files.append(output_path)

        except Exception as e:
            print(f"  Error creating {filename}: {e}", file=sys.stderr)

    # Delete original if requested and all splits successful
    if delete_original and len(output_files) == len(documents):
        try:
            pdf_path.unlink()
            if debug:
                print(f"\nDeleted original: {pdf_path.name}")
        except Exception as e:
            print(f"Warning: Could not delete original file: {e}", file=sys.stderr)

    return output_files


# ============================================================================
# CLI INTERFACE
# ============================================================================

def main():
    """Main entry point for CLI usage."""
    parser = argparse.ArgumentParser(
        description='Split multi-document PDF files into individual documents',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s document.pdf
  %(prog)s --output-dir ./split/ document.pdf
  %(prog)s --debug --dry-run document.pdf
  %(prog)s --delete-original document.pdf
  %(prog)s --resume large_document.pdf    # Resume after crash

Boundary Detection Methods:
  1. "Page X of Y" patterns - splits when X equals Y
  2. Standalone page numbers - splits when page resets to 1
  3. Header document type - splits when type changes (e.g., AFFIDAVIT → WARRANT)

Crash Recovery:
  Progress is checkpointed every 50 pages. If the script crashes on a large
  PDF, use --resume to continue from where it left off.

For more information, see README.md and ALGORITHM.md
        """
    )

    parser.add_argument('pdf_file', type=Path,
                       help='PDF file to split')

    parser.add_argument('--output-dir', '-o', type=Path,
                       help='Output directory (default: same as input file)')

    parser.add_argument('--delete-original', action='store_true',
                       help='Delete original file after successful split')

    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without creating files')

    parser.add_argument('--resume', action='store_true',
                       help='Resume from checkpoint if previous run crashed')

    parser.add_argument('--debug', action='store_true',
                       help='Print debug information')

    args = parser.parse_args()

    # Validate input
    if not args.pdf_file.exists():
        print(f"Error: File not found: {args.pdf_file}", file=sys.stderr)
        sys.exit(1)

    if not args.pdf_file.suffix.lower() == '.pdf':
        print(f"Error: File must be a PDF: {args.pdf_file}", file=sys.stderr)
        sys.exit(1)

    # Set output directory
    output_dir = args.output_dir if args.output_dir else args.pdf_file.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # Analyze PDF
    print(f"Processing: {args.pdf_file.name}")

    documents = analyze_pdf(
        args.pdf_file,
        output_dir=output_dir,
        debug=args.debug,
        resume=args.resume
    )

    if not documents:
        if not args.debug:
            print("single document (no split needed)")
        return 0

    if not args.debug:
        print(f"{len(documents)} documents detected")
        no_ocr_count = sum(1 for d in documents if d.has_no_ocr_pages)
        if no_ocr_count > 0:
            print(f"  ⚠ {no_ocr_count} document(s) contain pages with no OCR text")

    # Dry run mode
    if args.dry_run:
        print("\nDry run mode - no files will be created\n")
        type_counters: dict[str, int] = {}
        for idx, doc in enumerate(documents):
            doc_type = clean_filename(doc.title)
            type_counters[doc_type] = type_counters.get(doc_type, 0) + 1
            type_count = type_counters[doc_type]
            prefix = "No_OCR_" if doc.has_no_ocr_pages else ""
            filename = f"{prefix}{doc_type}_{type_count:03d}.pdf"
            print(f"  Would create: {filename}")
            print(f"    Pages {doc.start_page + 1}-{doc.end_page + 1} ({doc.end_page - doc.start_page + 1} pages)")
            print(f"    Title: {doc.title[:60]}")
            if doc.has_no_ocr_pages:
                print(f"    ⚠ No OCR pages: {doc.no_ocr_page_count}")
        return 0

    # Split PDF
    output_files = split_pdf(
        args.pdf_file,
        documents,
        output_dir,
        delete_original=args.delete_original,
        debug=args.debug
    )

    if len(output_files) == len(documents):
        print(f"\n✓ Successfully created {len(output_files)} files")
        return 0
    else:
        print(f"\n⚠ Warning: Only created {len(output_files)} of {len(documents)} files",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
