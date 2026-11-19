"""
records.py -- Structured Record Detection & Handling
=====================================================
Finds structured key-value records inside documents, e.g.:

    RECORD_ID: 10492-A
    ACCOUNT HOLDER: Ali Raza
    CITY: Karachi
    ACCOUNT NUMBER: PK89SCBL0000001123456701
    BRANCH CODE: 0112
    STATUS: Verified Active
    CLEARING ZONE: South Zone-A

WHY a separate module:
  Structured records must NEVER go through chunking, LLMLingua-2
  compression or sentence reranking. Those steps are designed for
  natural language and they scramble key-value data (names get
  separated from their IBANs, fields get dropped). So records are
  pulled out of the RAW text first, kept exact, and placed at the
  top of the final context.

Detection is GENERIC (not hard-coded to this bank PDF):
  - A record starts with an ID-like ALL-CAPS key (RECORD_ID,
    CUSTOMER ID, ACCOUNT ID, ...).
  - It continues while following lines are ALL-CAPS "KEY: value".
  - It needs at least 3 fields to count as a record.

Dependencies: Python standard library only.
"""

import re

# Keys that can START a record block (normalized: upper, spaces -> _)
_RECORD_START_KEYS = {
    "RECORD_ID", "RECORD_NO", "RECORD_NUMBER", "RECORD",
    "CUSTOMER_ID", "CLIENT_ID", "ACCOUNT_ID", "ENTRY_ID",
    "EMPLOYEE_ID", "PATIENT_ID", "STUDENT_ID", "MEMBER_ID",
}

# An ALL-CAPS key followed by ":" and a value, e.g. "ACCOUNT HOLDER: Ali Raza"
# WHY all-caps only: mixed-case labels like "Module: Settlement" are
# document metadata, not record fields.
_KEY_VALUE_RE = re.compile(r"^\s*([A-Z][A-Z0-9 _/&#.-]{0,40}?)\s*:\s*(\S.*?)\s*$")

# Words in a user's query that mean "show me the records"
_RECORD_QUERY_KEYWORDS = [
    "account", "holder", "name", "city", "iban", "customer", "client",
    "record", "profile", "branch", "number", "detail", "person",
    "people", "who", "list", "all", "status", "zone",
    "complete", "full", "summary", "summarize", "everything",
    "overview", "information",
]


def _normalize_key(key: str) -> str:
    """'ACCOUNT HOLDER' -> 'ACCOUNT_HOLDER' so lookups are consistent."""
    return re.sub(r"[\s-]+", "_", key.strip().upper())


def _build_record(fields: list) -> dict:
    """
    Build a record dict from a list of (KEY, value) tuples.
    Adds convenience keys used across the app (record_id, account_holder,
    city, account_number) plus a pre-formatted text block.
    """
    lookup = {_normalize_key(k): v for k, v in fields}
    record = {
        "fields": [{"key": k, "value": v} for k, v in fields],
        "record_id": fields[0][1],
        "account_holder": lookup.get("ACCOUNT_HOLDER") or lookup.get("NAME")
                          or lookup.get("CUSTOMER_NAME") or "",
        "city": lookup.get("CITY", ""),
        "account_number": lookup.get("ACCOUNT_NUMBER") or lookup.get("IBAN") or "",
        "branch_code": lookup.get("BRANCH_CODE", ""),
        "status": lookup.get("STATUS", ""),
        "clearing_zone": lookup.get("CLEARING_ZONE", ""),
    }
    record["formatted_text"] = "\n".join(f"{k}: {v}" for k, v in fields)
    return record


def split_records_from_text(raw_text: str) -> tuple:
    """
    Extract structured records from RAW text and return the text
    with those record lines removed.

    MUST be run on raw text (newlines intact). After cleaning, newlines
    are turned into spaces and fields can no longer be separated.

    Duplicate records (same ID, e.g. a document printed twice) are
    kept only once.

    Args:
        raw_text: Raw extracted text with original line breaks.

    Returns:
        (records, remaining_text)
          records: list[dict] (see _build_record)
          remaining_text: raw text minus the record lines
    """
    try:
        lines = raw_text.split("\n")
        records = []
        seen_ids = set()
        kept_lines = []
        i = 0

        while i < len(lines):
            match = _KEY_VALUE_RE.match(lines[i])
            if match and _normalize_key(match.group(1)) in _RECORD_START_KEYS:
                fields = [(match.group(1).strip(), match.group(2).strip())]
                j = i + 1
                # Consume following ALL-CAPS "KEY: value" lines
                while j < len(lines):
                    nxt = _KEY_VALUE_RE.match(lines[j])
                    if not nxt or _normalize_key(nxt.group(1)) in _RECORD_START_KEYS:
                        break
                    fields.append((nxt.group(1).strip(), nxt.group(2).strip()))
                    j += 1

                if len(fields) >= 3:
                    record_id = fields[0][1]
                    if record_id not in seen_ids:
                        seen_ids.add(record_id)
                        records.append(_build_record(fields))
                    # Replace the record with a blank line so the
                    # surrounding paragraphs stay separated.
                    kept_lines.append("")
                    i = j
                    continue

            kept_lines.append(lines[i])
            i += 1

        return records, "\n".join(kept_lines)

    except Exception as e:
        # Never crash the pipeline -- return text untouched
        print(f"    [WARNING] Record detection failed: {e}")
        return [], raw_text


def records_from_chunks(chunks: list) -> tuple:
    """
    Pull record chunks (chunks that START with an ID key such as
    'RECORD_ID:') out of a chunk list. Used as a fallback for inputs
    where the extractor did not detect records (e.g. direct text).

    Returns:
        (records, normal_chunks)
    """
    records = []
    normal = []
    for chunk in chunks:
        first_line = chunk.strip().split("\n", 1)[0]
        match = _KEY_VALUE_RE.match(first_line)
        if match and _normalize_key(match.group(1)) in _RECORD_START_KEYS:
            found, _ = split_records_from_text(chunk.strip())
            if found:
                records.extend(found)
                continue
        normal.append(chunk)
    return records, normal


def merge_records(primary: list, extra: list) -> list:
    """Combine two record lists, de-duplicating by record_id."""
    seen = {r["record_id"] for r in primary}
    merged = list(primary)
    for r in extra:
        if r["record_id"] not in seen:
            seen.add(r["record_id"])
            merged.append(r)
    return merged


def select_relevant_records(records: list, query: str) -> list:
    """
    Decide which records belong in the final context for this query.

    Rules (in order):
      1. If the query mentions a specific record (a name, city, ID or
         account number that appears in a record) -> return only those.
      2. Else if the query asks about records in general (account,
         name, city, IBAN, customer, ...) -> return ALL records.
      3. Else -> return no records (query is about something else).
    """
    if not records or not query:
        return []

    query_lower = query.lower()
    query_tokens = set(re.findall(r"[a-z0-9-]+", query_lower))

    # Rule 1: specific record mentioned
    specific = []
    for r in records:
        for field in r["fields"]:
            value = field["value"].lower()
            if len(value) < 3:
                continue
            # Full value in query ("ali raza", "pk89...", "10492-a")
            if value in query_lower:
                specific.append(r)
                break
            # Any name token for the holder field ("raza")
            if _normalize_key(field["key"]) in ("ACCOUNT_HOLDER", "NAME", "CUSTOMER_NAME"):
                name_tokens = {t for t in re.findall(r"[a-z]+", value) if len(t) >= 3}
                if name_tokens & query_tokens:
                    specific.append(r)
                    break
    if specific:
        return specific

    # Rule 2: general record question
    if any(kw in query_lower for kw in _RECORD_QUERY_KEYWORDS):
        return list(records)

    # Rule 3: unrelated query
    return []


def format_records_block(records: list) -> str:
    """
    Format records for the final LLM context. Exact values, one field
    per line, numbered -- the easiest format for an LLM to read.
    """
    if not records:
        return ""
    parts = [f"STRUCTURED RECORDS ({len(records)} found, exact values from document):"]
    for idx, r in enumerate(records, 1):
        parts.append(f"\n[Record {idx}]\n{r['formatted_text']}")
    return "\n".join(parts)


def format_records_summary(records: list) -> str:
    """One line per record: 'Ali Raza | Karachi | PK89...' (for console)."""
    rows = []
    for r in records:
        rows.append(" | ".join(x for x in (r["account_holder"], r["city"],
                                           r["account_number"]) if x)
                    or r["formatted_text"].replace("\n", " | "))
    return "\n".join(rows)
