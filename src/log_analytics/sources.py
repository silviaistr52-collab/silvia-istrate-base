"""
sources.py — functions that produce streams of log lines.

Two functions, both yielding strings one at a time:

    read_local_file(path)              — for local file input
    read_s3_prefix(bucket, prefix)     — for S3 input

Both are generators (they use `yield`), which means they hand back lines
one at a time as the caller asks for them, never loading the whole file
or S3 object into memory. That's how we satisfy the spec's streaming
requirement (process a 500MB file with 256MB of RAM).
"""

import boto3


def read_local_file(path):
    """Yield lines from a local JSONL file, one at a time.

    Arguments:
        path: path to a JSONL file (string or Path)

    Yields:
        Each line of the file, as a string with the trailing newline
        intact (the analyzer strips it).

    The file is opened lazily — only when the caller starts iterating —
    and closed automatically when iteration finishes (the `with` block).
    """

    # `with open(...)` guarantees the file is closed when we're done,
    # even if an exception is raised mid-read. Cleaner than try/finally.
    with open(path, encoding="utf-8") as f:

        # Iterating over a file object yields one line at a time. Python
        # handles the buffering internally — we don't have to worry about
        # reading chunks ourselves.
        for line in f:
            yield line


def read_s3_prefix(bucket, prefix, client=None):
    """Yield lines from every JSONL object under an S3 prefix, streaming.

    Arguments:
        bucket: S3 bucket name
        prefix: key prefix to read from (e.g. "logs/")
        client: optional boto3 S3 client (used for testing with mocks).
                If None, a default client is created.

    Yields:
        Each line of every matching object, as a decoded UTF-8 string.

    This is the streaming-critical function. It must work for objects
    far larger than available memory. The key line is body.iter_lines(),
    which pulls chunks from S3 as we consume them — we never hold the
    whole object in memory.
    """

    # If the caller didn't pass a client, create the default one. boto3
    # picks up credentials and region from the standard chain — env vars,
    # ~/.aws/credentials, or the IAM role attached to the ECS task.
    if client is None:
        client = boto3.client("s3")

    # ListObjectsV2 returns at most 1000 keys per call. The paginator
    # handles multi-page responses automatically, so this works whether
    # the prefix has 5 objects or 50,000.
    paginator = client.get_paginator("list_objects_v2")

    # Walk through every page of object listings.
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):

        # Each page has a "Contents" list of object summaries. Empty
        # prefixes have no Contents key at all, so .get(..., []) gives
        # us an empty list to iterate (zero iterations) instead of
        # crashing with a KeyError.
        for obj in page.get("Contents", []):

            # Fetch the object. The response's "Body" is a StreamingBody —
            # a file-like object that pulls data from S3 on demand,
            # rather than buffering the whole thing locally.
            response = client.get_object(Bucket=bucket, Key=obj["Key"])

            # iter_lines() yields one line at a time as bytes, splitting
            # on newlines. boto3 manages the underlying chunk buffering;
            # we just consume the iterator. Memory stays bounded.
            for raw_line in response["Body"].iter_lines():

                # The lines come back as bytes (b"..."), but our analyzer
                # expects plain strings. UTF-8 is the standard encoding
                # for JSON, so decode with that.
                yield raw_line.decode("utf-8")