from log_analytics.core import analyze


def test_empty_input():
    """Empty input is valid: total 0, no alert, no parse errors."""
    result = analyze([], threshold=5)
    assert result == {
        "total": 0,
        "byService": {},
        "alert": False,
        "parseErrors": 0,
    }


def test_all_errors_one_service():
    """Three ERRORs from the same service should count as 3 errors,
    grouped under that one service."""
    lines = [
        '{"ts":"x","service":"api","level":"ERROR","msg":"a"}',
        '{"ts":"x","service":"api","level":"ERROR","msg":"b"}',
        '{"ts":"x","service":"api","level":"ERROR","msg":"c"}',
    ]
    result = analyze(lines, threshold=2)
    assert result["total"] == 3
    assert result["byService"] == {"api": 3}
    assert result["alert"] is True
    assert result["parseErrors"] == 0


def test_mixed_levels_only_errors_counted():
    """INFO and WARN should be silently ignored, NOT counted as parse errors."""
    lines = [
        '{"ts":"x","service":"api","level":"INFO","msg":"a"}',
        '{"ts":"x","service":"api","level":"ERROR","msg":"b"}',
        '{"ts":"x","service":"api","level":"WARN","msg":"c"}',
    ]
    result = analyze(lines, threshold=10)
    assert result["total"] == 1
    assert result["byService"] == {"api": 1}
    assert result["parseErrors"] == 0  # INFO/WARN aren't parse errors


def test_threshold_boundary():
    """alert should fire on >= threshold, not strictly >.
    This is exactly the boundary the spec calls out."""
    lines = [
        '{"ts":"x","service":"api","level":"ERROR","msg":"a"}',
        '{"ts":"x","service":"api","level":"ERROR","msg":"b"}',
        '{"ts":"x","service":"api","level":"ERROR","msg":"c"}',
    ]

    # Threshold exactly equal to total — alert MUST fire (>=)
    result = analyze(lines, threshold=3)
    assert result["alert"] is True

    # Threshold one above total — alert must NOT fire
    result = analyze(lines, threshold=4)
    assert result["alert"] is False


def test_malformed_lines_are_counted_in_parse_errors():
    """Bad JSON, wrong shape, missing fields all increment parseErrors
    without crashing."""
    lines = [
        '{"ts":"x","service":"api","level":"ERROR","msg":"valid"}',  # ok
        'not json at all',                                            # bad JSON
        '["this","is","a","list","not","a","dict"]',                  # wrong shape
        '{"service":"api","level":"ERROR","msg":"missing ts"}',       # missing field
        '',                                                            # empty line, skip silently
        '   ',                                                         # whitespace only, skip
    ]
    result = analyze(lines, threshold=10)
    assert result["total"] == 1
    assert result["parseErrors"] == 3  # 3 malformed, empty/whitespace ignored


def test_multiple_services_counted_separately():
    """Each service gets its own counter."""
    lines = [
        '{"ts":"x","service":"api","level":"ERROR","msg":"a"}',
        '{"ts":"x","service":"orders","level":"ERROR","msg":"b"}',
        '{"ts":"x","service":"api","level":"ERROR","msg":"c"}',
        '{"ts":"x","service":"billing","level":"ERROR","msg":"d"}',
    ]
    result = analyze(lines, threshold=2)
    assert result["total"] == 4
    assert result["byService"] == {"api": 2, "orders": 1, "billing": 1}
    assert result["alert"] is True


def test_extra_fields_ignored():
    """Records with extra fields beyond the required four are still valid."""
    lines = [
        '{"ts":"x","service":"api","level":"ERROR","msg":"a","customer":"c-1","latency_ms":2001}',
    ]
    result = analyze(lines, threshold=1)
    assert result["total"] == 1
    assert result["parseErrors"] == 0


def test_no_errors_only_info():
    """All INFO records: 0 errors, no alert, no parse errors."""
    lines = [
        '{"ts":"x","service":"api","level":"INFO","msg":"a"}',
        '{"ts":"x","service":"api","level":"INFO","msg":"b"}',
    ]
    result = analyze(lines, threshold=1)
    assert result == {
        "total": 0,
        "byService": {},
        "alert": False,
        "parseErrors": 0,
    }
