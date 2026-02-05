# How the Document Splitting Algorithm Works

This document explains the core algorithm used to detect and split multi-document PDF files.

---

## The Problem

Legal discovery often produces PDF files containing **multiple documents concatenated together**. For example, a single PDF might contain:

- A 5-page search warrant
- A 3-page affidavit
- A 2-page return and tabulation
- A 12-page exhibit

These need to be split into separate files for proper organization and review.

---

## The Key Insight

Legal documents typically include **internal page numbering** in the format:

```
Page 1 of 5
Page 2 of 5
...
Page 5 of 5    ← This marks the END of Document 1
Page 1 of 3    ← This starts Document 2
Page 2 of 3
Page 3 of 3    ← This marks the END of Document 2
```

**The algorithm detects document boundaries by finding pages where `current_page == total_pages`** (e.g., "Page 5 of 5"). When this condition is true, we know we've reached the last page of a document.

---

## Algorithm Walkthrough

### Phase 1: Text Extraction

For each page in the PDF:

```python
page = pdf.pages[page_num]
text = page.extract_text()
```

The `pdfplumber` library extracts all text content from the page. This is the slow part—scanned documents take longer because the library must process image-based text.

### Phase 2: Pattern Matching

The extracted text is searched for page numbering patterns:

```python
PAGE_PATTERNS = [
    r'PAGE\s+(\d+)\s+OF\s+(\d+)',      # "PAGE 3 OF 5"
    r'PA\s*[GE]+\s*(\d+)\s+OF\s*(\d+)', # Handles OCR errors like "PA GE 3 OF 5"
    r'Page\s+(\d+)\s+of\s+(\d+)',      # "Page 3 of 5"
]
```

The regex captures two numbers:
- **Group 1**: Current page number within the document (e.g., `3`)
- **Group 2**: Total pages in the document (e.g., `5`)

Only the first 2000 characters of each page are searched (page numbers typically appear in headers/footers near the top).

### Phase 3: Boundary Detection

The core logic:

```python
current_page, page_total, doc_title = extract_page_info(text)

if current_page == page_total:
    # We've found the LAST page of a document!
    documents.append((current_start, page_num, doc_title))

    # The next PDF page starts a new document
    current_start = page_num + 1
```

**Visual representation:**

```
PDF Page Index:  0    1    2    3    4    5    6    7    8    9
                 |    |    |    |    |    |    |    |    |    |
Document Page:   1/5  2/5  3/5  4/5  5/5  1/3  2/3  3/3  1/4  2/4...
                                  ↑              ↑
                              BOUNDARY       BOUNDARY
                           (5/5 detected)  (3/3 detected)

Result:
  Document 1: PDF pages 0-4 (5 pages)
  Document 2: PDF pages 5-7 (3 pages)
  Document 3: PDF pages 8-... (continues)
```

### Phase 4: Title Extraction

When a boundary is detected, the algorithm also attempts to extract a document title by looking for legal keywords in the first 10 lines:

```python
keywords = ['SEARCH WARRANT', 'AFFIDAVIT', 'DISTRICT COURT',
           'SUBPOENA', 'RETURN', 'MOTION', 'COURT ORDER',
           'DECLARATION', 'EXHIBIT', 'COMPLAINT']
```

If a line contains one of these keywords and is between 10-100 characters, it's used as the document title.

### Phase 5: PDF Splitting

Once boundaries are identified, `pypdf` extracts the page ranges:

```python
for idx, (start_page, end_page, doc_title) in enumerate(documents):
    writer = PdfWriter()

    for page_idx in range(start_page, end_page + 1):
        writer.add_page(reader.pages[page_idx])

    writer.write(output_file)
```

---

## Data Flow Diagram

```
┌─────────────────┐
│   Input PDF     │
│  (multi-doc)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  For each page: │
│  extract_text() │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Search for      │
│ "Page X of Y"   │
│ patterns        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     No      ┌─────────────────┐
│ current_page == ├────────────►│ Continue to     │
│ total_pages?    │             │ next page       │
└────────┬────────┘             └─────────────────┘
         │ Yes
         ▼
┌─────────────────┐
│ Record boundary │
│ (start, end,    │
│  title)         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Set next page   │
│ as new doc      │
│ start           │
└────────┬────────┘
         │
         ▼ (after all pages)
┌─────────────────┐
│ Split PDF at    │
│ recorded        │
│ boundaries      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Output: N       │
│ separate PDFs   │
└─────────────────┘
```

---

## State Variables

The algorithm maintains these state variables while scanning:

| Variable | Purpose |
|----------|---------|
| `current_start` | PDF page index where the current document begins |
| `current_title` | Title of the current document (if detected) |
| `documents` | List of `(start_page, end_page, title)` tuples |

---

## Output Filename Generation

Files are named using this pattern:

```
{original_filename}_split_{sequence}_{document_type}.pdf
```

Example: `discovery_batch_split_01_search_warrant.pdf`

The `document_type` is derived from:
1. Matching keywords in the title (e.g., "search warrant" → `search_warrant`)
2. Optionally including case numbers (e.g., `affidavit_tnt-72-24.pdf`)

---

## Edge Cases

### 1. No Page Numbering Detected

If no "Page X of Y" patterns are found, the algorithm returns `None` and reports "single document (no split needed)".

### 2. Only One Document Detected

If boundaries are found but result in only one document, no split is performed.

### 3. Final Document Without Explicit End

If the PDF ends without a final "Page X of X" marker, the algorithm includes all remaining pages in the last document:

```python
if current_start < total_pages:
    documents.append((current_start, total_pages - 1, current_title))
```

### 4. OCR Errors

The pattern `PA\s*[GE]+\s*(\d+)\s+OF\s*(\d+)` handles common OCR errors where spaces appear in "PAGE" (e.g., "PA GE 3 OF 5").

### 5. Pages Without Numbering

Pages that don't match any pattern are silently included in the current document. This handles:
- Cover pages
- Exhibits without page numbers
- Scanned images without OCR text

---

## Performance Considerations

| Factor | Impact |
|--------|--------|
| **PDF page count** | Linear - each page must be scanned |
| **Text extraction** | Slowest part - pdfplumber is thorough but slow |
| **Scanned documents** | Significantly slower than native text PDFs |
| **Pattern matching** | Fast - only first 2000 chars searched |

For a 500-page scanned document, expect processing times of 5-15 minutes depending on complexity.

---

## Limitations

1. **Requires "Page X of Y" format** - Documents without this numbering won't be split
2. **OCR quality dependent** - Poor scans may not extract page numbers correctly
3. **Sequential processing** - Each page is processed one at a time
4. **No machine learning** - Pure pattern matching, won't adapt to unusual formats

---

## Extending the Algorithm

### Adding New Page Number Patterns

Edit `PAGE_PATTERNS` in `split_legal_doc.py`:

```python
PAGE_PATTERNS = [
    r'PAGE\s+(\d+)\s+OF\s+(\d+)',
    r'Page\s+(\d+)\s+of\s+(\d+)',
    r'(\d+)\s*/\s*(\d+)',           # Add: "3/5" format
    r'Page\s+(\d+),\s+(\d+)\s+total', # Add: "Page 3, 5 total"
]
```

### Adding Document Type Keywords

Edit `DOCUMENT_TYPES` to add jurisdiction-specific terminology:

```python
DOCUMENT_TYPES = {
    'search warrant': 'search_warrant',
    'arrest warrant': 'arrest_warrant',  # Add new types
    'grand jury subpoena': 'grand_jury_subpoena',
}
```

---

## Summary

The algorithm works by:

1. **Scanning** each PDF page for text
2. **Searching** for "Page X of Y" patterns
3. **Detecting boundaries** when `X == Y` (last page of a document)
4. **Recording** the page ranges and titles
5. **Splitting** the PDF at those boundaries

The key insight is that **the last page of each document reveals its boundary** through its page numbering.
