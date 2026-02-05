# Legal Document Splitter

A Python tool for automatically splitting multi-document PDF files into individual documents using page numbering pattern recognition.

## Overview

This tool is designed to handle the common problem in legal discovery and court filings where multiple documents are scanned or combined into a single PDF file. It intelligently detects document boundaries by:

1. **Page Numbering Detection**: Recognizes patterns like "Page 3 of 3" to identify when a document ends
2. **Document Title Extraction**: Identifies document types from page headers (Search Warrants, Affidavits, Court Orders, etc.)
3. **Intelligent Naming**: Creates meaningful filenames based on document type and case identifiers

## Why This Works

Legal documents typically follow standard formatting conventions:
- Each document has page numbering (e.g., "Page 1 of 5", "Page 2 of 5", etc.)
- When page number equals total pages, that document is complete
- Next page starts a new document
- Document titles appear at the top of pages

This pattern is consistent across:
- Federal and state courts
- Discovery documents
- Court filings
- Search warrants and affidavits
- Subpoenas and summons
- Many other legal document types

## Requirements

- Python 3.7+
- pdfplumber
- pypdf

Install dependencies:
```bash
pip install pdfplumber pypdf
```

## Usage

### Single File

Split a single PDF containing multiple documents:

```bash
python split_legal_doc.py input_file.pdf
```

The script will:
1. Analyze the PDF for page numbering patterns
2. Detect document boundaries
3. Create separate PDF files for each document
4. Name files based on document type and content

### Batch Processing

Split multiple PDF files:

```bash
python batch_split_legal_docs.py /path/to/pdfs/
```

Or use the provided shell script:

```bash
./process_directory.sh /path/to/pdfs/
```

## Output

Output files follow this naming convention:
```
original_filename_split_01_search_warrant.pdf
original_filename_split_02_affidavit.pdf
original_filename_split_03_search_warrant.pdf
```

Where:
- `original_filename` = base name of input file
- `split_01`, `split_02` = sequential numbering
- `search_warrant`, `affidavit` = detected document type

## Configuration

You can customize the behavior by editing the configuration section in the script:

```python
# Page numbering patterns to detect
PAGE_PATTERNS = [
    r'PAGE\s+(\d+)\s+OF\s+(\d+)',
    r'PA\s*[GE]+\s*(\d+)\s+OF\s*(\d+)',
]

# Document type keywords
DOCUMENT_TYPES = {
    'search warrant': 'search_warrant',
    'affidavit': 'affidavit',
    'subpoena': 'subpoena',
    'court order': 'court_order',
    # Add more as needed
}
```

## Limitations

**Works Best With:**
- Legal documents with page numbering
- Multi-document PDFs where each document is paginated
- Text-based PDFs (not scanned images without OCR)

**May Not Work With:**
- Scanned documents without OCR
- Documents without page numbering
- Documents with inconsistent formatting
- Heavily redacted documents where page numbers are obscured

**For Scanned Documents:**
If your documents are scanned images, run OCR first:
```bash
# Using ocrmypdf (install separately)
ocrmypdf input.pdf output_ocr.pdf
```

Then run the splitter on the OCR'd PDF.

## Examples

### Example 1: Discovery Documents

Input: `discovery_batch_1.pdf` (47 pages containing 8 documents)

Output:
```
discovery_batch_1_split_01_search_warrant_tnt-72-24.pdf (6 pages)
discovery_batch_1_split_02_affidavit.pdf (5 pages)
discovery_batch_1_split_03_search_warrant_lmcu.pdf (3 pages)
... etc
```

### Example 2: Court Filings

Input: `case_2024_001_filings.pdf` (120 pages, 15 documents)

The script automatically separates:
- Motions
- Affidavits
- Court orders
- Exhibits
- Returns

## Generalizability

This tool is highly generalizable because:

✅ **Cross-Jurisdiction**: Works with federal, state, and local court documents
✅ **Document-Agnostic**: Handles any document type with page numbering
✅ **Format-Independent**: Doesn't rely on specific formatting beyond page numbers
✅ **Minimal Configuration**: Works out-of-box for most legal documents

**Tested With:**
- Federal discovery documents
- State court filings
- Search warrants and returns
- Affidavits and declarations
- Subpoenas
- Court orders
- Police reports
- Forensic reports

## Advanced Usage

### Preserving Original Files

By default, the script creates split files but keeps the original. To auto-delete originals after successful split:

```bash
python split_legal_doc.py --delete-original input.pdf
```

### Dry Run Mode

See what would be split without creating files:

```bash
python split_legal_doc.py --dry-run input.pdf
```

### Custom Output Directory

```bash
python split_legal_doc.py --output-dir ./split_docs/ input.pdf
```

## Troubleshooting

**"No documents detected"**
- Check if the PDF has page numbering
- Try viewing the PDF to confirm numbering format
- Use `--debug` flag to see what text is being extracted

**"Only found 1 document" (but there are multiple)**
- Page numbering might not follow standard format
- Try customizing `PAGE_PATTERNS` in the config
- Some documents may lack page numbering

**"Wrong document types in filenames"**
- Customize `DOCUMENT_TYPES` dictionary
- Add your jurisdiction's specific terminology

## Contributing

This tool was created during a legal discovery document processing project. Improvements are welcome:

- Additional page numbering patterns
- Better document type detection
- Support for more file formats
- Performance optimizations for very large files

## License

MIT License - Free to use and modify

## Support

For issues or questions, refer to the inline code documentation or create detailed issues with:
- Sample PDF (if possible)
- Expected vs. actual behavior
- Debug output (`--debug` flag)
