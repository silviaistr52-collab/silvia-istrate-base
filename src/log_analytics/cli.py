import json
import sys

import click

from log_analytics.core import analyze
from log_analytics.sources import read_local_file, read_s3_prefix


@click.command()
@click.option(
    "--bucket",
    help="S3 bucket name. Required if --file is not given.",
)
@click.option(
    "--prefix",
    default="",
    help="S3 key prefix. Defaults to empty (whole bucket).",
)
@click.option(
    "--file",
    "file_path",
    help="Path to a local JSONL file. Mutually exclusive with --bucket.",
)
@click.option(
    "--threshold",
    type=int,
    default=10,
    show_default=True,
    help="Alert when total errors >= threshold.",
)
def main(bucket, prefix, file_path, threshold):
    """Analyze JSONL log files for ERROR records."""

    # Validate input — exactly one of --bucket or --file must be given.
    if bool(bucket) == bool(file_path):
        click.echo("error: provide exactly one of --bucket or --file", err=True)
        sys.exit(1)

    # Pick the right reader. Both produce iterables of strings, so analyze()
    # doesn't need to know which source we picked.
    try:
        if file_path:
            lines = read_local_file(file_path)
        else:
            lines = read_s3_prefix(bucket, prefix)

        result = analyze(lines, threshold)

    except FileNotFoundError as e:
        click.echo(f"error: file not found: {e.filename}", err=True)
        sys.exit(1)
    except Exception as e:
        # Generic catch-all. Don't leak stack traces.
        click.echo(f"error: {e}", err=True)
        sys.exit(1)

    # Print the result as pretty-printed JSON to stdout.
    click.echo(json.dumps(result, indent=2))

    # Exit code 2 if alert fired, 0 otherwise.
    sys.exit(2 if result["alert"] else 0)


if __name__ == "__main__":
    main()