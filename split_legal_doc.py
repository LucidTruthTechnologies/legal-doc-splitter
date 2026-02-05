#!/usr/bin/env python3
"""
Legal Document Splitter

Automatically splits multi-document PDF files into individual documents
using page numbering pattern recognition.

Author: Created for legal discovery document processing
License: MIT
"""

import sys
import argparse
from pathlib import Path
import re
from typing import List, Tuple, Optional
import pdfplumber
from pypdf import PdfReader, PdfWriter


# ============================================================================
# CONFIGURATION
# ============================================================================

# Page numbering patterns to detect (regex patterns)
# These patterns look for "Page X of Y" variations
PAGE_PATTERNS = [
    r'PAGE\s+(\d+)\s+OF\s+(\d+)',      # "PAGE 3 OF 5"
    r'PA\s*[GE]+\s*(\d+)\s+OF\s*(\d+)', # Handles OCR errors
    r'Page\s+(\d+)\s+of\s+(\d+)',      # "Page 3 of 5"
]

# Document type keywords and their clean names
# Add your jurisdiction's specific terminology here
DOCUMENT_TYPES = {
    'search warrant': 'search_warrant',
    'affidavit': 'affidavit',
    'subpoena': 'subpoena',
    'court order': 'court_order',
    'return and tabulation': 'return_tabulation',
    'return': 'return',
    'motion': 'motion',
    'declaration': 'declaration',
    'exhibit': 'exhibit',
    'complaint': 'complaint',
    'answer': 'answer',
    'summons': 'summons',
}

# Case number patterns (customize for your jurisdiction)
CASE_PATTERNS = [
    r'tnt-?\d+-\d+',           # TNT-72-24
    r'ccu-?\d+-\d+',           # CCU-02587-2024
    r'\d+th\s+district',       # 86th District
    r'\d+-cv-\d+',             # 2024-CV-001
    r'case\s*(?:no|number)[:\s]*([a-z0-9\-]+)',  # Case No: XXX
]


# ============================================================================
# CORE FUNCTIONS
# ============================================================================

def extract_page_info(text: str, debug: bool = False) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    """
    Extract page numbering information and document title from page text.

    Args:
        text: Text content from a PDF page
        debug: If True, print debug information

    Returns:
        Tuple of (current_page, total_pages, document_title)
        Returns (None, None, None) if no page numbering found
    """
    # Search first 2000 characters (page numbers usually appear early)
    text_upper = text[:2000].upper()

    # Try each page numbering pattern
    for pattern in PAGE_PATTERNS:
        match = re.search(pattern, text_upper, re.IGNORECASE)
        if match:
            current_page = int(match.group(1))
            total_pages = int(match.group(2))

            if debug:
                print(f"    Found: Page {current_page} of {total_pages}")

            # Extract document title (usually in first few lines)
            title = extract_document_title(text)

            return (current_page, total_pages, title)

    return (None, None, None)


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
        keywords = ['SEARCH WARRANT', 'AFFIDAVIT', 'DISTRICT COURT',
                   'SUBPOENA', 'RETURN', 'MOTION', 'COURT ORDER',
                   'DECLARATION', 'EXHIBIT', 'COMPLAINT']

        if any(keyword in line_upper for keyword in keywords):
            return line_clean

    return None


def analyze_pdf(pdf_path: Path, debug: bool = False) -> Optional[List[Tuple[int, int, str]]]:
    """
    Analyze a PDF file to detect document boundaries.

    Args:
        pdf_path: Path to PDF file
        debug: If True, print debug information

    Returns:
        List of tuples (start_page, end_page, title) for each document
        Returns None if no page numbering detected or only 1 document
    """
    if debug:
        print(f"\nAnalyzing: {pdf_path.name}")
        print("=" * 70)

    documents = []
    current_start = 0
    current_title = None

    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)

            if debug:
                print(f"Total pages: {total_pages}\n")

            for page_num in range(total_pages):
                # Progress indicator (always show so user knows it's working)
                print(f"\r  Scanning page {page_num + 1}/{total_pages}...", end="", flush=True)

                try:
                    page = pdf.pages[page_num]
                    text = page.extract_text() or ""

                    current_page, page_total, doc_title = extract_page_info(text, debug)

                    if current_page and page_total:
                        # Check if this is the last page of a document
                        if current_page == page_total:
                            documents.append((
                                current_start,
                                page_num,
                                doc_title or "Unknown"
                            ))

                            if debug:
                                print(f"  Page {page_num + 1}: Document ends")
                                print(f"    Range: pages {current_start + 1}-{page_num + 1}")

                            # Next page starts new document
                            if page_num + 1 < total_pages:
                                current_start = page_num + 1
                                current_title = None

                        if doc_title and not current_title:
                            current_title = doc_title

                except Exception as e:
                    if debug:
                        print(f"  Error on page {page_num + 1}: {e}")

            # Clear the progress line
            print("\r" + " " * 40 + "\r", end="", flush=True)

            # Add final document if we have boundaries
            if current_start < total_pages:
                if len(documents) == 0:
                    # No page numbering detected
                    if debug:
                        print("No page numbering patterns detected")
                    return None
                else:
                    documents.append((
                        current_start,
                        total_pages - 1,
                        current_title or "Unknown"
                    ))

                    if debug:
                        print(f"  Final document: pages {current_start + 1}-{total_pages}")

    except Exception as e:
        print(f"Error analyzing PDF: {e}", file=sys.stderr)
        return None

    # Only return if we found multiple documents
    if len(documents) > 1:
        if debug:
            print(f"\nDetected {len(documents)} separate documents")
        return documents
    else:
        if debug:
            print("\nOnly 1 document detected (no split needed)")
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


def split_pdf(pdf_path: Path, documents: List[Tuple[int, int, str]],
              output_dir: Path, delete_original: bool = False,
              debug: bool = False) -> List[Path]:
    """
    Split PDF into separate files based on detected boundaries.

    Args:
        pdf_path: Path to input PDF
        documents: List of (start_page, end_page, title) tuples
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
    base_name = pdf_path.stem
    output_files = []

    for idx, (start_page, end_page, doc_title) in enumerate(documents):
        num_pages = end_page - start_page + 1

        # Create filename
        doc_type_clean = clean_filename(doc_title)
        filename = f"{base_name}_split_{idx + 1:02d}_{doc_type_clean}.pdf"
        output_path = output_dir / filename

        try:
            # Create writer
            writer = PdfWriter()

            # Add pages
            for page_idx in range(start_page, end_page + 1):
                writer.add_page(reader.pages[page_idx])

            # Write file
            with open(output_path, "wb") as output_file:
                writer.write(output_file)

            size_kb = output_path.stat().st_size / 1024

            if debug:
                print(f"  [{idx + 1}/{len(documents)}] Created: {filename}")
                print(f"      Pages {start_page + 1}-{end_page + 1} ({num_pages} pages, {size_kb:.1f} KB)")
            else:
                print(f"  → {filename} (pages {start_page + 1}-{end_page + 1})")

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

For more information, see README.md
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

    documents = analyze_pdf(args.pdf_file, debug=args.debug)

    if not documents:
        if not args.debug:
            print("single document (no split needed)")
        return 0

    if not args.debug:
        print(f"{len(documents)} documents detected")

    # Dry run mode
    if args.dry_run:
        print("\nDry run mode - no files will be created\n")
        for idx, (start, end, title) in enumerate(documents):
            doc_type = clean_filename(title)
            filename = f"{args.pdf_file.stem}_split_{idx + 1:02d}_{doc_type}.pdf"
            print(f"  Would create: {filename}")
            print(f"    Pages {start + 1}-{end + 1} ({end - start + 1} pages)")
            print(f"    Title: {title[:60]}")
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
