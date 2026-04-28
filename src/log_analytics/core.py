"""
core.py — log analysis logic.

The analyze() function takes any iterable of strings (where each string is
one JSON-encoded log line) and returns a summary dict. It doesn't care
whether the lines came from a file, S3, or a list — that's the job of
the reader functions in sources.py.
"""

import json


def analyze(lines, threshold):
    """Read log lines, count ERROR records, return a summary dict.

    Arguments:
        lines: any iterable of strings (each string is one JSONL record)
        threshold: alert fires when total errors >= this number

    Returns:
        A dict with keys: total, byService, alert, parseErrors.

    Behaviour:
        - Malformed lines (bad JSON, wrong shape, missing fields) are
          counted in parseErrors and skipped.
        - Records with level != "ERROR" are silently ignored (they're
          not malformed, just not what we care about).
        - Empty input returns total=0, alert=False, parseErrors=0.
    """

    # Running totals — we update these as we walk through the lines.
    total = 0
    by_service = {}
    parse_errors = 0

    # Iterate one line at a time. Because `lines` is consumed lazily,
    # this loop uses constant memory regardless of how many lines there
    # are or how big the source file is.
    for line in lines:

        # Strip whitespace and skip blank lines. JSONL files often end
        # with a trailing newline, which produces an empty final line —
        # that's not malformed, just empty.
        line = line.strip()
        if not line:
            continue

        # Try to parse the line as JSON. If parsing fails, count it as
        # a parse error and move on. We catch the specific exception —
        # not a bare `except` — so genuine bugs (NameError, etc.) still
        # surface instead of being silently swallowed.
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            parse_errors += 1
            continue

        # The line parsed, but is it the right shape? It needs to be a
        # dict (a JSON object), not a list, number, or string.
        if not isinstance(record, dict):
            parse_errors += 1
            continue

        # And it needs to contain all four required fields. If any are
        # missing, treat the record as malformed.
        required_fields = ("ts", "service", "level", "msg")
        if not all(key in record for key in required_fields):
            parse_errors += 1
            continue

        # The record is well-formed. But we only count ERROR records —
        # INFO, WARN, DEBUG etc. are normal records we silently skip.
        # Note: this is NOT a parse error. The line was perfectly valid;
        # it just wasn't an error log.
        if record["level"] != "ERROR":
            continue

        # We have an ERROR. Count it in the totals.
        service = record["service"]
        total += 1

        # Increment the per-service counter. dict.get(key, 0) returns
        # the current count or 0 if we haven't seen this service before.
        by_service[service] = by_service.get(service, 0) + 1

    # After the loop, decide whether to alert. We do this once at the
    # end rather than recomputing on every line.
    return {
        "total": total,
        "byService": by_service,
        "alert": total >= threshold,
        "parseErrors": parse_errors,
    }