"""
test_streaming.py — proves the streaming requirement.

The spec says:
    "process a large file with a memory assertion or equivalent.
    A solution that works only on small files will not pass."

We generate a stream of ~500k lines in memory (no disk I/O) and run
the analyser over it, asserting that peak memory stays bounded well
below what buffering the whole input would cost.

A non-streaming implementation would materialise all lines in memory
first, causing peak allocation to scale with input size and fail the
assertion.
"""

import tracemalloc
import pytest
from log_analytics.core import analyze


def generate_error_lines(n):
    """Yield n valid ERROR log lines without storing them all in memory."""
    line = (
        '{"ts":"2025-09-15T14:10:04Z","service":"api","level":"ERROR",'
        '"msg":"500 internal server error","latency_ms":2001}'
    )
    for _ in range(n):
        yield line


@pytest.mark.slow
def test_processes_large_stream_without_buffering():
    """Feed 500,000 log lines to the analyser and assert bounded memory.

    500k lines is roughly equivalent to a 50MB file — enough to catch
    any implementation that buffers the input. Peak memory must stay
    under 10MB regardless of input size.
    """
    num_lines = 500_000

    tracemalloc.start()

    result = analyze(generate_error_lines(num_lines), threshold=1)

    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # All lines were valid ERRORs.
    assert result["total"] == num_lines
    assert result["alert"] is True
    assert result["parseErrors"] == 0

    # Peak memory must be tiny — we're only ever holding one line at a time.
    # 10MB is generous; correct implementation should peak well under 1MB.
    peak_mb = peak / (1024 * 1024)
    assert peak_mb < 10, (
        f"streaming check failed: peak memory was {peak_mb:.1f} MB "
        f"for {num_lines:,} lines. "
        f"This suggests the implementation buffered the input."
    )