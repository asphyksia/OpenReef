import csv
import io
import json


MAX_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB
MAX_ROWS = 100_000
MAX_TOKENS_PER_EXAMPLE = 4096  # rough estimate: ~4 chars per token


def validate_dataset(content: bytes, fmt: str) -> tuple[int, list[str]]:
    """Validate dataset content. Returns (row_count, errors)."""
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
        return _validate_csv(text, errors)
    elif fmt == "txt":
        return _validate_txt(text, errors)
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


def _validate_csv(text: str, errors: list[str]) -> tuple[int, list[str]]:
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
