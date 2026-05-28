import csv
import io
import json
from typing import BinaryIO

MAX_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB
MAX_ROWS = 100_000
MAX_TOKENS_PER_EXAMPLE = 4096  # rough estimate: ~4 chars per token


def validate_dataset(content: bytes, fmt: str) -> tuple[int, list[str]]:
    """Validate dataset from bytes. Returns (row_count, errors).

    Kept for backward compat; prefer validate_dataset_stream for large files.
    """
    errors: list[str] = []

    if len(content) > MAX_SIZE_BYTES:
        errors.append(f"Dataset exceeds maximum size of {MAX_SIZE_BYTES / (1024*1024):.0f}MB")

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        errors.append("File is not valid UTF-8")
        return (0, errors)

    if fmt == "jsonl":
        return _validate_jsonl(text, errors)
    elif fmt == "csv":
        return _validate_csv_text(text, errors)
    elif fmt == "txt":
        return _validate_txt(text, errors)
    else:
        errors.append(f"Unsupported format: {fmt}")
        return (0, errors)


def validate_dataset_stream(file: BinaryIO, fmt: str) -> tuple[int, list[str]]:
    """Validate dataset from a file-like stream (streaming, no full read).

    Reads line-by-line for validation, then seeks back to start.
    Returns (row_count, errors).
    """
    errors: list[str] = []

    if fmt == "jsonl":
        return _validate_jsonl_stream(file, errors)
    elif fmt == "csv":
        return _validate_csv_stream(file, errors)
    elif fmt == "txt":
        return _validate_txt_stream(file, errors)
    else:
        errors.append(f"Unsupported format: {fmt}")
        return (0, errors)


def _validate_jsonl(text: str, errors: list[str]) -> tuple[int, list[str]]:
    lines = text.strip().split("\n")
    if not lines:
        errors.append("File is empty")
        return (0, errors)

    if len(lines) > MAX_ROWS:
        errors.append(f"Dataset has {len(lines)} rows (max {MAX_ROWS})")

    for i, line in enumerate(lines[:5]):  # check first 5 lines for structure
        try:
            obj = json.loads(line)
            if not isinstance(obj, dict):
                errors.append(f"Line {i+1}: expected a JSON object")
                break
            if len(obj) < 1:
                errors.append(f"Line {i+1}: object is empty")
                break
        except json.JSONDecodeError as e:
            errors.append(f"Line {i+1}: invalid JSON - {e}")
            break

    if errors:
        return (0, errors)
    return (len(lines), errors)


def _validate_jsonl_stream(file: BinaryIO, errors: list[str]) -> tuple[int, list[str]]:
    """Validate first 1000 JSONL rows deeply, count all rows.

    Deep structural validation on first N lines, then trust row count.
    """
    row_count = 0
    max_lines_to_validate = 1000

    for line_num, raw_line in enumerate(file, start=1):
        try:
            line = raw_line.decode("utf-8").strip()
        except UnicodeDecodeError:
            errors.append(f"Line {line_num}: file is not valid UTF-8")
            file.seek(0)
            return (0, errors)
        if not line:
            continue
        row_count += 1

        if row_count > MAX_ROWS:
            errors.append(f"Dataset has more than {MAX_ROWS} rows")
            break

        if line_num <= max_lines_to_validate:
            try:
                obj = json.loads(line)
                if not isinstance(obj, dict):
                    errors.append(f"Line {line_num}: expected a JSON object")
                    break
                if len(obj) < 1:
                    errors.append(f"Line {line_num}: object is empty")
                    break
            except json.JSONDecodeError as e:
                errors.append(f"Line {line_num}: invalid JSON - {e}")
                break

    if row_count == 0:
        errors.append("File is empty")

    if errors:
        file.seek(0)
        return (0, errors)
    file.seek(0)
    return (row_count, errors)


def _validate_csv_text(text: str, errors: list[str]) -> tuple[int, list[str]]:
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        errors.append("File is empty")
        return (0, errors)
    if len(rows) > MAX_ROWS:
        errors.append(f"Dataset has {len(rows)} rows (max {MAX_ROWS})")
    if len(rows[0]) < 1:
        errors.append("CSV has no columns")
    if errors:
        return (0, errors)
    return (len(rows) - 1, errors)  # subtract header


def _validate_csv_stream(file: BinaryIO, errors: list[str]) -> tuple[int, list[str]]:
    """Validate CSV by streaming, counting rows without loading full file."""
    first_line = file.readline()
    if not first_line:
        errors.append("File is empty")
        file.seek(0)
        return (0, errors)

    try:
        first_line_text = first_line.decode("utf-8")
    except UnicodeDecodeError:
        errors.append("File is not valid UTF-8")
        file.seek(0)
        return (0, errors)

    first_row_reader = csv.reader(io.StringIO(first_line_text))
    first_row = next(first_row_reader, [])
    if len(first_row) < 1:
        errors.append("CSV has no columns")
        file.seek(0)
        return (0, errors)

    row_count = 0
    for raw_line in file:
        try:
            line = raw_line.decode("utf-8").rstrip("\r\n")
        except UnicodeDecodeError:
            errors.append("File is not valid UTF-8")
            break
        if not line:
            continue
        row_count += 1
        if row_count > MAX_ROWS:
            errors.append(f"Dataset has more than {MAX_ROWS} rows")
            break

    if row_count == 0:
        errors.append("File is empty")

    file.seek(0)
    return (row_count, errors)


def _validate_txt(text: str, errors: list[str]) -> tuple[int, list[str]]:
    lines = text.strip().split("\n")
    if not lines:
        errors.append("File is empty")
        return (0, errors)
    if len(lines) > MAX_ROWS:
        errors.append(f"Dataset has {len(lines)} rows (max {MAX_ROWS})")
    for i, line in enumerate(lines[:1]):
        if len(line) > MAX_TOKENS_PER_EXAMPLE * 4:
            errors.append(f"Line {i+1}: exceeds estimated token limit")
    if errors:
        return (0, errors)
    return (len(lines), errors)


def _validate_txt_stream(file: BinaryIO, errors: list[str]) -> tuple[int, list[str]]:
    """Validate TXT by streaming, counting lines without loading full file."""
    row_count = 0
    first_line_checked = False

    for _ in file:
        raw_line = _
        try:
            line = raw_line.decode("utf-8").rstrip("\n\r")
        except UnicodeDecodeError:
            errors.append("File is not valid UTF-8")
            break
        if not line:
            continue
        row_count += 1

        if row_count > MAX_ROWS:
            errors.append(f"Dataset has more than {MAX_ROWS} rows")
            break

        if not first_line_checked:
            if len(line) > MAX_TOKENS_PER_EXAMPLE * 4:
                errors.append(f"Line 1: exceeds estimated token limit")
                break
            first_line_checked = True

    if errors:
        file.seek(0)
        return (0, errors)
    file.seek(0)
    return (row_count, errors)
