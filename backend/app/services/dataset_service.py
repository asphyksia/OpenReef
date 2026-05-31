import csv
import io
import json
import logging
import random
from typing import BinaryIO

import tiktoken

logger = logging.getLogger(__name__)

MAX_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB
MAX_ROWS = 100_000
MAX_TOKENS_PER_EXAMPLE = 4096

# Tokenizer for estimation — cl100k_base is fast and reasonably accurate
# for most modern models (Qwen, Llama 3, etc.)
_ENCODING = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Count tokens in a text string using cl100k_base encoding."""
    return len(_ENCODING.encode(text))


def estimate_tokens_approx(text: str) -> int:
    """Fast approximation: ~4 chars per token for ASCII, ~2 for CJK."""
    cjk_chars = sum(1 for c in text if ord(c) > 127)
    ascii_chars = len(text) - cjk_chars
    return (ascii_chars // 4) + (cjk_chars // 2)


def validate_dataset(content: bytes, fmt: str) -> tuple[int, int, list[str]]:
    """Validate dataset from bytes. Returns (row_count, token_count, errors).

    Kept for backward compat; prefer validate_dataset_stream for large files.
    """
    errors: list[str] = []

    if len(content) > MAX_SIZE_BYTES:
        errors.append(f"Dataset exceeds maximum size of {MAX_SIZE_BYTES / (1024*1024):.0f}MB")

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        errors.append("File is not valid UTF-8")
        return (0, 0, errors)

    if fmt == "jsonl":
        return _validate_jsonl(text, errors)
    elif fmt == "csv":
        return _validate_csv_text(text, errors)
    elif fmt == "txt":
        return _validate_txt(text, errors)
    else:
        errors.append(f"Unsupported format: {fmt}")
        return (0, 0, errors)


def validate_dataset_stream(file: BinaryIO, fmt: str) -> tuple[int, int, list[str]]:
    """Validate dataset from a file-like stream (streaming, no full read).

    Reads line-by-line for validation, then seeks back to start.
    Returns (row_count, token_count, errors).
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
        return (0, 0, errors)


def _validate_jsonl(text: str, errors: list[str]) -> tuple[int, int, list[str]]:
    lines = text.strip().split("\n")
    if not lines:
        errors.append("File is empty")
        return (0, 0, errors)

    if len(lines) > MAX_ROWS:
        errors.append(f"Dataset has {len(lines)} rows (max {MAX_ROWS})")

    for i, line in enumerate(lines[:5]):
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
        return (0, 0, errors)

    # Count tokens
    total_tokens = 0
    for line in lines:
        try:
            obj = json.loads(line)
            text_content = " ".join(str(v) for v in obj.values())
            total_tokens += count_tokens(text_content)
        except (json.JSONDecodeError, Exception):
            pass

    return (len(lines), total_tokens, errors)


def _validate_jsonl_stream(file: BinaryIO, errors: list[str]) -> tuple[int, int, list[str]]:
    """Validate JSONL by streaming with byte limit enforcement and random sampling.

    - Accumulates bytes read and aborts if MAX_SIZE_BYTES is exceeded (Fix 9)
    - Validates rows distributed throughout the file via random sampling,
      not just the first N rows (Fix 10)
    - Counts tokens by sampling every Nth row for speed
    """
    row_count = 0
    bytes_read = 0
    max_validations = 1000  # Max rows to structurally validate
    validations_done = 0
    sample_interval = 10  # count tokens on every 10th row for speed
    sampled_tokens = 0
    sampled_rows = 0
    has_cjk = False
    validation_seed = random.randint(0, 1000)  # Random starting point for validation

    for line_num, raw_line in enumerate(file, start=1):
        bytes_read += len(raw_line)
        if bytes_read > MAX_SIZE_BYTES:
            errors.append(f"Dataset exceeds maximum size of {MAX_SIZE_BYTES / (1024*1024):.0f}MB")
            file.seek(0)
            return (0, 0, errors)

        try:
            line = raw_line.decode("utf-8").strip()
        except UnicodeDecodeError:
            errors.append(f"Line {line_num}: file is not valid UTF-8")
            file.seek(0)
            return (0, 0, errors)
        if not line:
            continue
        row_count += 1

        # Check for CJK characters (affects token ratio)
        if not has_cjk and any(ord(c) > 127 for c in line):
            has_cjk = True

        if row_count > MAX_ROWS:
            errors.append(f"Dataset has more than {MAX_ROWS} rows")
            break

        # Random sampling validation: validate rows distributed throughout the file
        # Uses a hash-based approach to select rows evenly across the entire stream
        should_validate = (validations_done < max_validations and
                          ((row_num + validation_seed) % max(1, MAX_ROWS // max_validations) == 0))
        if should_validate:
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
            validations_done += 1

        # Sample tokens every Nth row
        if row_count % sample_interval == 0:
            try:
                obj = json.loads(line)
                text_content = " ".join(str(v) for v in obj.values())
                sampled_tokens += count_tokens(text_content)
                sampled_rows += 1
            except (json.JSONDecodeError, Exception):
                pass

    if row_count == 0:
        errors.append("File is empty")

    if errors:
        file.seek(0)
        return (0, 0, errors)

    # Extrapolate total tokens from sample
    if sampled_rows > 0:
        avg_tokens_per_row = sampled_tokens / sampled_rows
        total_tokens = int(avg_tokens_per_row * row_count)
    else:
        # Fallback: rough estimate from bytes read
        chars_per_token = 2 if has_cjk else 4
        total_tokens = bytes_read // chars_per_token

    file.seek(0)
    return (row_count, total_tokens, errors)


def _validate_csv_text(text: str, errors: list[str]) -> tuple[int, int, list[str]]:
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        errors.append("File is empty")
        return (0, 0, errors)
    if len(rows) > MAX_ROWS:
        errors.append(f"Dataset has {len(rows)} rows (max {MAX_ROWS})")
    if len(rows[0]) < 1:
        errors.append("CSV has no columns")
    if errors:
        return (0, 0, errors)

    # Count tokens
    total_tokens = 0
    for row in rows[1:]:  # skip header
        text_content = " ".join(row)
        total_tokens += count_tokens(text_content)

    return (len(rows) - 1, total_tokens, errors)


def _validate_csv_stream(file: BinaryIO, errors: list[str]) -> tuple[int, int, list[str]]:
    """Validate CSV by streaming, counting rows and estimating tokens."""
    first_line = file.readline()
    if not first_line:
        errors.append("File is empty")
        file.seek(0)
        return (0, 0, errors)

    try:
        first_line_text = first_line.decode("utf-8")
    except UnicodeDecodeError:
        errors.append("File is not valid UTF-8")
        file.seek(0)
        return (0, 0, errors)

    first_row_reader = csv.reader(io.StringIO(first_line_text))
    first_row = next(first_row_reader, [])
    if len(first_row) < 1:
        errors.append("CSV has no columns")
        file.seek(0)
        return (0, 0, errors)

    row_count = 0
    bytes_read = len(first_line)
    sampled_tokens = 0
    sampled_rows = 0
    sample_interval = 10

    for raw_line in file:
        bytes_read += len(raw_line)
        if bytes_read > MAX_SIZE_BYTES:
            errors.append(f"Dataset exceeds maximum size of {MAX_SIZE_BYTES / (1024*1024):.0f}MB")
            break
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

        if row_count % sample_interval == 0:
            try:
                row = list(csv.reader(io.StringIO(line)))[0]
                text_content = " ".join(row)
                sampled_tokens += count_tokens(text_content)
                sampled_rows += 1
            except Exception:
                pass

    if row_count == 0:
        errors.append("File is empty")

    if errors:
        file.seek(0)
        return (0, 0, errors)

    if sampled_rows > 0:
        avg_tokens_per_row = sampled_tokens / sampled_rows
        total_tokens = int(avg_tokens_per_row * row_count)
    else:
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        total_tokens = file_size // 4

    file.seek(0)
    return (row_count, total_tokens, errors)


def _validate_txt(text: str, errors: list[str]) -> tuple[int, int, list[str]]:
    lines = text.strip().split("\n")
    if not lines:
        errors.append("File is empty")
        return (0, 0, errors)
    if len(lines) > MAX_ROWS:
        errors.append(f"Dataset has {len(lines)} rows (max {MAX_ROWS})")

    for i, line in enumerate(lines[:1]):
        token_count = count_tokens(line)
        if token_count > MAX_TOKENS_PER_EXAMPLE:
            errors.append(f"Line {i+1}: exceeds estimated token limit ({token_count} > {MAX_TOKENS_PER_EXAMPLE})")

    if errors:
        return (0, 0, errors)

    total_tokens = sum(count_tokens(line) for line in lines)
    return (len(lines), total_tokens, errors)


def _validate_txt_stream(file: BinaryIO, errors: list[str]) -> tuple[int, int, list[str]]:
    """Validate TXT by streaming, counting lines and estimating tokens."""
    row_count = 0
    bytes_read = 0
    first_line_checked = False
    sampled_tokens = 0
    sampled_rows = 0
    sample_interval = 10

    for raw_line in file:
        bytes_read += len(raw_line)
        if bytes_read > MAX_SIZE_BYTES:
            errors.append(f"Dataset exceeds maximum size of {MAX_SIZE_BYTES / (1024*1024):.0f}MB")
            break
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
            token_count = count_tokens(line)
            if token_count > MAX_TOKENS_PER_EXAMPLE:
                errors.append(f"Line 1: exceeds estimated token limit ({token_count} > {MAX_TOKENS_PER_EXAMPLE})")
                break
            first_line_checked = True

        if row_count % sample_interval == 0:
            sampled_tokens += count_tokens(line)
            sampled_rows += 1

    if errors:
        file.seek(0)
        return (0, 0, errors)

    if sampled_rows > 0:
        avg_tokens_per_row = sampled_tokens / sampled_rows
        total_tokens = int(avg_tokens_per_row * row_count)
    else:
        total_tokens = bytes_read // 4

    file.seek(0)
    return (row_count, total_tokens, errors)
