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


def _is_flat_mindmap(code: str) -> bool:
    lines = [l for l in code.splitlines() if l.strip() and not l.strip().lower().startswith("mindmap")]
    if len(lines) < 2:
        return False
    indents = [len(l) - len(l.lstrip()) for l in lines]
    return len(set(indents)) <= 1


def _flat_mindmap_to_flowchart(code: str) -> str:
    lines = [l.strip() for l in code.splitlines() if l.strip() and not l.strip().lower().startswith("mindmap")]
    if not lines:
        return _FALLBACK
    root_match = re.match(r'root\(\((.+?)\)\)', lines[0])
    root_label = root_match.group(1) if root_match else lines[0]
    result = ["flowchart TD", f'  ROOT["{root_label}"]']
    for i, node in enumerate(lines[1:], 1):
        label = re.sub(r'^root\(\((.+?)\)\)$', r'\1', node)
        label = label[:40]
        result.append(f'  N{i}["{label}"]')
        result.append(f'  ROOT --> N{i}')
    return "\n".join(result)


def _fix_mindmap(code: str) -> str:
    code = "\n".join(line.replace('\t', '    ') for line in code.splitlines())
    if _is_flat_mindmap(code):
        return _flat_mindmap_to_flowchart(code)
    return code


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
        was_flat = _is_flat_mindmap(code)
        code = _fix_mindmap(code)
        if was_flat:
            dtype = "flowchart"

    if not code.strip():
        return _FALLBACK, "fallback"

    return code, dtype if dtype != "unknown" else "fallback"
