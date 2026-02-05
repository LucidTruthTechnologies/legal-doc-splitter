# Usage Examples

Quick reference for common use cases.

## Installation

```bash
cd legal-doc-splitter
pip install -r requirements.txt
```

## Single File Processing

### Basic usage
```bash
python split_legal_doc.py discovery_documents.pdf
```

### With debug output
```bash
python split_legal_doc.py --debug discovery_documents.pdf
```

### Dry run (see what would happen without creating files)
```bash
python split_legal_doc.py --dry-run discovery_documents.pdf
```

### Custom output directory
```bash
python split_legal_doc.py --output-dir ./split_docs/ discovery_documents.pdf
```

### Delete original after split
```bash
python split_legal_doc.py --delete-original discovery_documents.pdf
```

## Batch Processing

### Process entire directory
```bash
python batch_split_legal_docs.py /path/to/legal_docs/
```

### Process directory recursively (including subdirectories)
```bash
python batch_split_legal_docs.py --recursive /path/to/legal_docs/
```

### With custom output directory
```bash
python batch_split_legal_docs.py --output-dir ./split/ /path/to/legal_docs/
```

### Delete originals after processing
```bash
python batch_split_legal_docs.py --delete-originals /path/to/legal_docs/
```

## Real-World Scenarios

### Scenario 1: Processing discovery documents

You receive a USB drive with 50 PDF files, some containing multiple documents:

```bash
# Process all files in the directory
cd /media/usb/discovery_2024/
python /path/to/batch_split_legal_docs.py .

# Result: Multi-document files split, single-document files untouched
```

### Scenario 2: Organizing court filings

You have a folder of scanned court filings that need to be separated:

```bash
# First, verify what would happen (dry run)
python split_legal_doc.py --dry-run court_filings_batch1.pdf

# If looks good, process for real
python split_legal_doc.py court_filings_batch1.pdf
```

### Scenario 3: Preparing documents for review

Split documents and organize into a review folder:

```bash
# Create output directory
mkdir -p ~/Documents/case_review/split_docs/

# Process all PDFs
python batch_split_legal_docs.py \
    --output-dir ~/Documents/case_review/split_docs/ \
    ~/Downloads/discovery_files/
```

### Scenario 4: Processing scanned documents

If documents are scanned images without OCR:

```bash
# First, run OCR (requires ocrmypdf)
ocrmypdf input_scanned.pdf output_ocr.pdf

# Then split
python split_legal_doc.py output_ocr.pdf
```

### Scenario 5: Debug mode for troubleshooting

When a file isn't splitting correctly:

```bash
# Run with debug output to see what's detected
python split_legal_doc.py --debug problematic_file.pdf

# This will show:
# - Page numbering patterns found
# - Document boundaries detected
# - Document titles extracted
```

## Integration with Other Tools

### Using with Claude Code

From your terminal:

```bash
# Let Claude Code help you customize the tool
claude "help me modify legal-doc-splitter to handle documents from California courts"
```

### Shell script wrapper

Create a simple wrapper script for your workflow:

```bash
#!/bin/bash
# my_discovery_processor.sh

INPUT_DIR="$1"
OUTPUT_DIR="${INPUT_DIR}/split"

mkdir -p "$OUTPUT_DIR"

python /path/to/legal-doc-splitter/batch_split_legal_docs.py \
    --output-dir "$OUTPUT_DIR" \
    "$INPUT_DIR"

echo "Done! Split files are in: $OUTPUT_DIR"
```

Usage:
```bash
./my_discovery_processor.sh ~/Downloads/new_discovery/
```

### Automated processing

Process new files automatically using a cron job or file watcher:

```bash
# Add to crontab (runs every hour)
0 * * * * /path/to/batch_split_legal_docs.py ~/incoming_discovery/

# Or use a file watcher (requires inotifywait)
inotifywait -m -e close_write ~/incoming_discovery/ |
while read path action file; do
    if [[ "$file" == *.pdf ]]; then
        python split_legal_doc.py "$path$file"
    fi
done
```

## Customization Examples

### Adding new document types

Edit `split_legal_doc.py` and add to `DOCUMENT_TYPES`:

```python
DOCUMENT_TYPES = {
    # ... existing types ...
    'bill of costs': 'bill_of_costs',
    'fee petition': 'fee_petition',
    'settlement agreement': 'settlement_agreement',
}
```

### Adding new case number patterns

For California superior court case numbers:

```python
CASE_PATTERNS = [
    # ... existing patterns ...
    r'\d{2}-[A-Z]{2}-\d{5}',  # "24-CV-12345" format
    r'[A-Z]{3}\d{6}',          # "LAW123456" format
]
```

### Custom page numbering patterns

For documents with unusual formats:

```python
PAGE_PATTERNS = [
    # ... existing patterns ...
    r'Página\s+(\d+)\s+de\s+(\d+)',  # Spanish format
    r'(\d+)\s*\/\s*(\d+)',            # "3 / 5" format
]
```

## Troubleshooting

### "No documents detected"

**Solution**: Check if PDF has page numbering

```bash
# Extract text from first few pages to verify
python -c "
import pdfplumber
with pdfplumber.open('file.pdf') as pdf:
    for i in range(min(3, len(pdf.pages))):
        print(f'=== Page {i+1} ===')
        print(pdf.pages[i].extract_text()[:500])
"
```

### "Only 1 document found" but there are multiple

**Solution**: Page numbering might not follow standard format. Use debug mode:

```bash
python split_legal_doc.py --debug file.pdf
```

Look at the debug output to see what page numbering (if any) is detected.

### Script runs out of memory

**Solution**: For very large PDFs (>1000 pages), process in smaller chunks or use a machine with more RAM. The tool loads the entire PDF into memory.

### Wrong document types in filenames

**Solution**: Customize `DOCUMENT_TYPES` dictionary for your specific terminology.

## Performance Tips

- **Large files**: Process one at a time rather than batch processing many large files
- **Batch processing**: Use `--recursive` only if needed (faster without)
- **Memory**: Close other applications when processing very large PDFs
- **Storage**: Ensure sufficient disk space (split files are approximately same size as original)
