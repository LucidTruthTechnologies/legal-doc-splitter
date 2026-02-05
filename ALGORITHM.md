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

## Three Detection Methods

The algorithm uses **three independent methods** to detect document boundaries. If any method detects a boundary, the split occurs.

### Method 1: "Page X of Y" Pattern

**How it works:** Legal documents often include "Page 1 of 5", "Page 2 of 5", etc. When we find a page where X equals Y (e.g., "Page 5 of 5"), we know we've reached the **last page** of that document.

**Patterns detected:**
```
PAGE 3 OF 5
Page 3 of 5
PA GE 3 OF 5    (handles OCR errors)
3 of 5 pages
```

**Boundary condition:** `current_page == total_pages`

**Example:**
```
PDF Page:  1    2    3    4    5    6    7    8
Content:   1/5  2/5  3/5  4/5  5/5  1/3  2/3  3/3
                              ↑              ↑
                          BOUNDARY       BOUNDARY
```

---

### Method 2: Standalone Page Number Reset

**How it works:** Some documents only show "Page 1", "Page 2", etc. (without "of Y"). When the page number **resets to 1** after being higher, a new document has started.

**Patterns detected:**
```
PAGE 3
Page 3
- 3 -
— 3 —
```

**Boundary condition:** `current_page == 1 AND previous_page > 1`

**Example:**
```
PDF Page:  1    2    3    4    5    6    7
Content:   1    2    3    4    1    2    3
                         ↑
                     BOUNDARY
                (Page 4 → Page 1 = new document)
```

**Note:** The boundary is placed *before* Page 1, so Document 1 ends at PDF page 4, and Document 2 starts at PDF page 5.

---

### Method 3: Header Document Type Change

**How it works:** Legal documents typically have a consistent header identifying the document type (e.g., "AFFIDAVIT" or "SEARCH WARRANT"). When this header **changes**, a new document has begun.

**Document types tracked:**
```
SEARCH WARRANT, AFFIDAVIT, SUBPOENA, COURT ORDER,
RETURN AND TABULATION, MOTION, DECLARATION, EXHIBIT,
COMPLAINT, ANSWER, SUMMONS, PETITION, ORDER, WARRANT,
NOTICE, CERTIFICATE
```

**Boundary condition:** `current_header_type != previous_header_type`

**Example:**
```
PDF Page:  1          2          3          4          5
Header:    AFFIDAVIT  AFFIDAVIT  AFFIDAVIT  WARRANT    WARRANT
                                            ↑
                                        BOUNDARY
                        (AFFIDAVIT → WARRANT = new document)
```

---

## No-OCR Page Detection

**Problem:** Some PDF pages contain scanned images without OCR text, or the OCR failed. These pages have little or no extractable text.

**How it works:** If a page has fewer than 50 characters of text, it's flagged as a "no-OCR" page.

**Output behavior:** Documents containing no-OCR pages are prefixed with `No_OCR_` in the filename:
```
No_OCR_discovery_split_03_exhibit.pdf
```

This makes it easy to identify documents that may need:
- Manual review
- Re-scanning
- OCR processing

---

## Algorithm Walkthrough

### Step 1: Initialize State

```python
current_start = 0          # PDF page where current document begins
current_title = None       # Title of current document
current_no_ocr_count = 0   # Pages with no OCR in current document
prev_standalone_page = None # Previous standalone page number
prev_header_type = None    # Previous document type header
```

### Step 2: For Each PDF Page

```
For page_num in range(total_pages):

    1. Extract text from page

    2. Check if page has no OCR (< 50 chars)
       → If yes, increment no_ocr_count

    3. Try Method 1: "Page X of Y"
       → If found and X == Y: record boundary, reset state
       → Continue to next page (skip other methods)

    4. Try Method 2: Standalone page number
       → If found and page == 1 and prev_page > 1:
         record boundary, reset state

    5. Try Method 3: Header document type
       → If found and type != prev_type:
         record boundary, reset state
```

### Step 3: Finalize

After scanning all pages, add the final document (from `current_start` to end of PDF).

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      INPUT PDF                               │
│                   (multi-document)                           │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   FOR EACH PAGE                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────┐                                        │
│  │ Extract Text    │                                        │
│  └────────┬────────┘                                        │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────┐     Yes    ┌──────────────────┐       │
│  │ Text < 50 chars?├───────────►│ Mark as No-OCR   │       │
│  └────────┬────────┘            └──────────────────┘       │
│           │ No                                              │
│           ▼                                                  │
│  ┌─────────────────┐     Yes    ┌──────────────────┐       │
│  │ "Page X of Y"?  ├───────────►│ X == Y?          │       │
│  └────────┬────────┘            └────────┬─────────┘       │
│           │ No                           │ Yes              │
│           │                              ▼                  │
│           │                     ┌──────────────────┐       │
│           │                     │ RECORD BOUNDARY  │       │
│           │                     └──────────────────┘       │
│           ▼                                                  │
│  ┌─────────────────┐     Yes    ┌──────────────────┐       │
│  │ "Page X" only?  ├───────────►│ X==1 & prev>1?   │       │
│  └────────┬────────┘            └────────┬─────────┘       │
│           │ No                           │ Yes              │
│           │                              ▼                  │
│           │                     ┌──────────────────┐       │
│           │                     │ RECORD BOUNDARY  │       │
│           │                     └──────────────────┘       │
│           ▼                                                  │
│  ┌─────────────────┐     Yes    ┌──────────────────┐       │
│  │ Header type?    ├───────────►│ Type changed?    │       │
│  └────────┬────────┘            └────────┬─────────┘       │
│           │ No                           │ Yes              │
│           │                              ▼                  │
│           │                     ┌──────────────────┐       │
│           │                     │ RECORD BOUNDARY  │       │
│           │                     └──────────────────┘       │
│           │                                                  │
│           ▼                                                  │
│       [Next Page]                                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   SPLIT PDF                                  │
│            at recorded boundaries                            │
│                                                              │
│  Add "No_OCR_" prefix to filenames                          │
│  if document contains no-OCR pages                          │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   OUTPUT FILES                               │
│                                                              │
│  search_warrant_001.pdf                                     │
│  affidavit_001.pdf                                          │
│  No_OCR_exhibit_001.pdf  ← flagged for review               │
│  return_tabulation_001.pdf                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Method Priority

The three detection methods are checked in order:

1. **"Page X of Y"** — highest priority, most reliable
2. **Standalone page reset** — checked if Method 1 doesn't match
3. **Header type change** — checked if Methods 1 & 2 don't match

If Method 1 finds a match on a page, Methods 2 and 3 are **skipped** for that page. This prevents false positives when multiple signals might occur on the same page.

---

## State Variables

| Variable | Type | Purpose |
|----------|------|---------|
| `current_start` | int | PDF page index where current document begins |
| `current_title` | str | Title of current document |
| `current_no_ocr_count` | int | Number of no-OCR pages in current document |
| `prev_standalone_page` | int | Previous standalone page number (for reset detection) |
| `prev_header_type` | str | Previous document type header (for change detection) |
| `documents` | list | Accumulated list of detected documents |

---

## DocumentInfo Structure

Each detected document is stored as:

```python
class DocumentInfo(NamedTuple):
    start_page: int        # PDF page index (0-based) where document starts
    end_page: int          # PDF page index (0-based) where document ends
    title: str             # Detected document title
    has_no_ocr_pages: bool # True if any page had no OCR text
    no_ocr_page_count: int # Number of pages with no OCR text
```

---

## Output Filename Format

Files are named by document type with **per-type counters**:

```
[No_OCR_]{document_type}_{NNN}.pdf
```

Where `NNN` is a 3-digit counter that increments **per document type**, not globally.

Examples:
```
search_warrant_001.pdf      ← First search warrant
affidavit_001.pdf           ← First affidavit
search_warrant_002.pdf      ← Second search warrant
No_OCR_exhibit_001.pdf      ← First exhibit (has no-OCR pages)
return_tabulation_001.pdf   ← First return
```

This naming scheme produces meaningful, organized filenames where:
- Documents of the same type are grouped together when sorted
- Each type maintains its own sequential numbering
- The `No_OCR_` prefix flags documents needing manual review

---

## Edge Cases

### 1. No Boundaries Detected

If none of the three methods detect any boundaries, the function returns `None` and reports "single document (no split needed)".

### 2. Only One Document Detected

If boundaries result in only one document, no split is performed.

### 3. All Pages Are No-OCR

The algorithm still attempts to split based on any patterns found. If the entire PDF has no readable text, it will be treated as a single document.

### 4. Mixed Detection Methods

Different documents in the same PDF can be detected by different methods. For example:
- Documents 1-2 detected by "Page X of Y"
- Document 3 detected by header change
- Document 4 detected by page number reset

### 5. Final Document Without Explicit End

If the PDF ends without a final boundary marker, all remaining pages are included in the last document.

---

## Extending the Algorithm

### Adding New Page Number Patterns

Edit `PAGE_OF_PATTERNS` or `STANDALONE_PAGE_PATTERNS`:

```python
PAGE_OF_PATTERNS = [
    r'PAGE\s+(\d+)\s+OF\s+(\d+)',
    r'(\d+)\s*/\s*(\d+)',           # Add: "3/5" format
]

STANDALONE_PAGE_PATTERNS = [
    r'PAGE\s+(\d+)\s*$',
    r'\[(\d+)\]',                   # Add: "[3]" format
]
```

### Adding Document Type Keywords

Edit `HEADER_DOC_TYPES`:

```python
HEADER_DOC_TYPES = [
    'SEARCH WARRANT',
    'AFFIDAVIT',
    'GRAND JURY SUBPOENA',  # Add jurisdiction-specific types
    'ARREST WARRANT',
]
```

### Adjusting No-OCR Threshold

Edit `MIN_TEXT_LENGTH`:

```python
MIN_TEXT_LENGTH = 50  # Increase for stricter detection
```

---

## Performance Considerations

| Factor | Impact |
|--------|--------|
| PDF page count | Linear — each page scanned once |
| Text extraction | Slowest operation (pdfplumber) |
| Pattern matching | Fast — limited to header/footer regions |
| Scanned documents | Significantly slower than native PDFs |

For a 500-page scanned document, expect 5-15 minutes processing time.

---

## Summary

The algorithm detects document boundaries using three methods:

| Method | Signal | Boundary When |
|--------|--------|---------------|
| Page X of Y | "Page 5 of 5" | X equals Y |
| Standalone page | "Page 1" after "Page 3" | Resets to 1 |
| Header type | "AFFIDAVIT" → "WARRANT" | Type changes |

Documents with pages containing no OCR text are flagged with a `No_OCR_` filename prefix for manual review.
