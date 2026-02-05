"""
Example Configuration

Copy this file to config.py and customize for your jurisdiction/use case.
Then modify split_legal_doc.py to import from config.py instead of
using the default configuration.
"""

# ============================================================================
# PAGE NUMBERING PATTERNS
# ============================================================================

# Add patterns specific to your jurisdiction or document format
# These are regular expressions that capture (page_number, total_pages)
PAGE_PATTERNS = [
    # Standard formats
    r'PAGE\s+(\d+)\s+OF\s+(\d+)',      # "PAGE 3 OF 5"
    r'Page\s+(\d+)\s+of\s+(\d+)',      # "Page 3 of 5"
    r'P\.\s*(\d+)\s+of\s+(\d+)',       # "P. 3 of 5"

    # OCR-tolerant (handles OCR errors)
    r'PA\s*[GE]+\s*(\d+)\s+OF\s*(\d+)',

    # Hyphenated format
    r'PAGE\s+(\d+)-(\d+)',             # "PAGE 3-5"

    # With forward slash
    r'PAGE\s+(\d+)/(\d+)',             # "PAGE 3/5"

    # Add your custom patterns here
    # Example for foreign language:
    # r'PÁGINA\s+(\d+)\s+DE\s+(\d+)',  # Spanish
]


# ============================================================================
# DOCUMENT TYPE KEYWORDS
# ============================================================================

# Map document type phrases to clean filename components
# Key = phrase to search for (lowercase)
# Value = clean name for filename
DOCUMENT_TYPES = {
    # Standard legal documents
    'search warrant': 'search_warrant',
    'warrant': 'warrant',
    'affidavit': 'affidavit',
    'declaration': 'declaration',
    'subpoena': 'subpoena',
    'summons': 'summons',

    # Court documents
    'court order': 'court_order',
    'order': 'order',
    'judgment': 'judgment',
    'decree': 'decree',
    'opinion': 'opinion',

    # Pleadings
    'complaint': 'complaint',
    'answer': 'answer',
    'motion': 'motion',
    'petition': 'petition',
    'response': 'response',
    'reply': 'reply',

    # Discovery
    'interrogatories': 'interrogatories',
    'requests for admission': 'requests_for_admission',
    'requests for production': 'requests_for_production',
    'deposition': 'deposition',

    # Exhibits and attachments
    'exhibit': 'exhibit',
    'attachment': 'attachment',
    'appendix': 'appendix',

    # Returns
    'return and tabulation': 'return_tabulation',
    'return': 'return',
    'tabulation': 'tabulation',

    # Other
    'notice': 'notice',
    'memorandum': 'memorandum',
    'brief': 'brief',
    'certificate': 'certificate',

    # Add your custom document types here
}


# ============================================================================
# CASE NUMBER PATTERNS
# ============================================================================

# Regular expressions to extract case numbers/identifiers
# These will be used in filenames to distinguish documents
CASE_PATTERNS = [
    # Common case number formats
    r'case\s*(?:no|number|#)[:\s]*([a-z0-9\-]+)',  # "Case No: 2024-CV-001"
    r'\d+-cv-\d+',                                   # "2024-CV-001" (civil)
    r'\d+-cr-\d+',                                   # "2024-CR-001" (criminal)

    # District court patterns
    r'\d+th\s+district',                            # "86th District"
    r'\d+th\s+judicial\s+district',                 # "86th Judicial District"

    # Agency-specific patterns (customize for your jurisdiction)
    r'tnt-?\d+-\d+',                                # "TNT-72-24"
    r'ccu-?\d+-\d+',                                # "CCU-02587-2024"

    # Add your jurisdiction's patterns here
    # Examples:
    # r'[A-Z]{2}\d{2}-\d{4}',                       # "AB12-2024"
    # r'docket\s*(?:no|#)[:\s]*(\d+)',              # "Docket No: 12345"
]


# ============================================================================
# EXTRACTION SETTINGS
# ============================================================================

# How much text to analyze for page numbering (in characters)
PAGE_NUMBER_SEARCH_LENGTH = 2000

# How much text to analyze for document title (in characters)
TITLE_SEARCH_LENGTH = 500

# Maximum title length (characters)
MAX_TITLE_LENGTH = 100

# Minimum title length (characters)
MIN_TITLE_LENGTH = 10


# ============================================================================
# OUTPUT SETTINGS
# ============================================================================

# Filename template
# Available placeholders: {base_name}, {index}, {doc_type}, {case_id}
FILENAME_TEMPLATE = "{base_name}_split_{index:02d}_{doc_type}.pdf"

# Alternative templates:
# FILENAME_TEMPLATE = "{doc_type}_{case_id}_{index:02d}.pdf"
# FILENAME_TEMPLATE = "{base_name}_{index:03d}_{doc_type}_{case_id}.pdf"


# ============================================================================
# PROCESSING OPTIONS
# ============================================================================

# Skip files with this pattern in the name (prevents re-processing)
SKIP_PATTERN = "_split_"

# Minimum pages for a valid document (set to 0 to allow single-page docs)
MIN_DOCUMENT_PAGES = 1

# Log level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL = "INFO"
