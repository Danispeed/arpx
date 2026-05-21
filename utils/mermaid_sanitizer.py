import re

_FALLBACK = 'flowchart LR\n  A["Paper"] -->|explains| B["Key Ideas"]'


def _strip_fences(code: str) -> str:
    code = re.sub(r'^\s*```[a-zA-Z]*\s*\n?', '', code.strip())
    code = re.sub(r'\n?\s*```\s*$', '', code)
    return code.strip()


def _detect_type(code: str) -> str:
    first = code.strip().splitlines()[0].strip().lower()
    if first.startswith("mindmap"):
        return "mindmap"
    if first.startswith("sequencediagram"):
        return "sequenceDiagram"
    if first.startswith("flowchart") or first.startswith("graph"):
        return "flowchart"
    return "unknown"


def _strip_special_chars(code: str) -> str:
    parts = re.split(r'("(?:[^"\\]|\\.)*")', code)
    result = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            result.append(part)
        else:
            part = part.replace('&', 'and').replace('/', ' ')
            result.append(part)
    return "".join(result)


def _fix_flowchart(code: str) -> str:
    lines = code.splitlines()
    fixed = []
    for line in lines:
        if re.match(r'\s*style\s+\w+', line):
            continue
        def shorten_label(m):
            words = m.group(1).strip().split()
            return f'|{" ".join(words[:3])}|'
        line = re.sub(r'\|([^|]+)\|', shorten_label, line)
        fixed.append(line)
    return "\n".join(fixed)


def _fix_mindmap(code: str) -> str:
    return "\n".join(line.replace('\t', '    ') for line in code.splitlines())


def sanitize(mermaid_code: str) -> tuple[str, str]:
    """Returns (sanitized_code, diagram_type)."""
    if not mermaid_code or not mermaid_code.strip():
        return _FALLBACK, "fallback"

    code = _strip_fences(mermaid_code)
    dtype = _detect_type(code)
    code = _strip_special_chars(code)

    if dtype == "flowchart":
        code = _fix_flowchart(code)
    elif dtype == "mindmap":
        code = _fix_mindmap(code)

    if not code.strip():
        return _FALLBACK, "fallback"

    return code, dtype if dtype != "unknown" else "fallback"
