#!/usr/bin/env python3
"""
Batch Legal Document Splitter

Process an entire directory of PDF files, splitting multi-document PDFs.

Author: Created for legal discovery document processing
License: MIT
"""

import sys
import argparse
from pathlib import Path
from typing import List
from split_legal_doc import analyze_pdf, split_pdf


def find_pdf_files(directory: Path, recursive: bool = False) -> List[Path]:
    """
    Find all PDF files in a directory.

    Args:
        directory: Directory to search
        recursive: If True, search subdirectories

    Returns:
        List of PDF file paths
    """
    if recursive:
        return list(directory.rglob("*.pdf"))
    else:
        return list(directory.glob("*.pdf"))


def process_directory(directory: Path, output_dir: Path = None,
                     delete_originals: bool = False,
                     recursive: bool = False,
                     skip_split: bool = True) -> dict:
    """
    Process all PDF files in a directory.

    Args:
        directory: Input directory
        output_dir: Output directory (default: same as input)
        delete_originals: Delete original files after split
        recursive: Search subdirectories
        skip_split: Skip files with '_split_' in name

    Returns:
        Dictionary with statistics
    """
    # Find all PDFs
    pdf_files = find_pdf_files(directory, recursive)

    # Filter out already-split files if requested
    if skip_split:
        pdf_files = [f for f in pdf_files if '_split_' not in f.name]

    if not pdf_files:
        print(f"No PDF files found in {directory}")
        return {'total': 0, 'split': 0, 'single': 0, 'errors': 0}

    print(f"Found {len(pdf_files)} PDF files to process\n")
    print("=" * 70)

    stats = {
        'total': len(pdf_files),
        'split': 0,
        'single': 0,
        'errors': 0,
        'files_created': 0
    }

    for pdf_file in sorted(pdf_files):
        print(f"\nProcessing: {pdf_file.name}")

        try:
            # Analyze PDF
            documents = analyze_pdf(pdf_file)

            if not documents:
                print("  → single document (no split needed)")
                stats['single'] += 1
                continue

            # Multiple documents detected
            print(f"  → {len(documents)} documents detected")

            # Determine output directory
            out_dir = output_dir if output_dir else pdf_file.parent

            # Split PDF
            output_files = split_pdf(
                pdf_file,
                documents,
                out_dir,
                delete_original=delete_originals
            )

            stats['split'] += 1
            stats['files_created'] += len(output_files)

        except Exception as e:
            print(f"ERROR: {e}")
            stats['errors'] += 1

    return stats


def main():
    """Main entry point for batch processing."""
    parser = argparse.ArgumentParser(
        description='Batch split multi-document PDF files in a directory',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/pdfs/
  %(prog)s --recursive --output-dir ./split/ /path/to/pdfs/
  %(prog)s --delete-originals /path/to/pdfs/

This will process all PDF files in the directory and split any that
contain multiple documents (detected by page numbering).
        """
    )

    parser.add_argument('directory', type=Path,
                       help='Directory containing PDF files')

    parser.add_argument('--output-dir', '-o', type=Path,
                       help='Output directory (default: same as input)')

    parser.add_argument('--recursive', '-r', action='store_true',
                       help='Search subdirectories recursively')

    parser.add_argument('--delete-originals', action='store_true',
                       help='Delete original files after successful split')

    parser.add_argument('--include-split', action='store_true',
                       help='Process files with "_split_" in name (default: skip)')

    args = parser.parse_args()

    # Validate input
    if not args.directory.exists():
        print(f"Error: Directory not found: {args.directory}", file=sys.stderr)
        sys.exit(1)

    if not args.directory.is_dir():
        print(f"Error: Not a directory: {args.directory}", file=sys.stderr)
        sys.exit(1)

    # Create output directory if specified
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)

    # Process directory
    print(f"Processing: {args.directory}")
    print(f"Recursive: {args.recursive}")
    print(f"Output: {args.output_dir or 'same as input'}")
    print()

    stats = process_directory(
        args.directory,
        output_dir=args.output_dir,
        delete_originals=args.delete_originals,
        recursive=args.recursive,
        skip_split=not args.include_split
    )

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total files processed:    {stats['total']}")
    print(f"Files split:              {stats['split']}")
    print(f"Single documents (skip):  {stats['single']}")
    print(f"Errors:                   {stats['errors']}")
    print(f"New files created:        {stats['files_created']}")
    print("=" * 70)

    return 0 if stats['errors'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
