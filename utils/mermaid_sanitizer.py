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


def _clean_mindmap_label(text: str) -> str:
    text = re.sub(r'^root\(\((.+?)\)\)$', r'\1', text.strip())
    text = re.sub(r'^\(\((.+?)\)\)$', r'\1', text)
    text = re.sub(r'^\((.+?)\)$', r'\1', text)
    text = re.sub(r'^\[(.+?)\]$', r'\1', text)
    return text[:40]


def _mindmap_to_flowchart(code: str) -> str:
    lines = [l for l in code.splitlines() if l.strip() and not l.strip().lower().startswith("mindmap")]
    if not lines:
        return _FALLBACK

    raw_indents = [len(l) - len(l.lstrip()) for l in lines]
    min_indent = min(raw_indents)
    indent_unit = 2

    # Infer indent unit from smallest non-zero step
    steps = sorted(set(i - min_indent for i in raw_indents if i > min_indent))
    if steps:
        indent_unit = steps[0] or 2

    nodes = []
    for i, (line, raw_indent) in enumerate(zip(lines, raw_indents)):
        label = _clean_mindmap_label(line)
        level = (raw_indent - min_indent) // indent_unit
        nodes.append((f'N{i}', label, level))

    result = ["flowchart TD"]
    for node_id, label, _ in nodes:
        result.append(f'  {node_id}["{label}"]')

    for i, (node_id, _, level) in enumerate(nodes):
        if level == 0:
            continue
        for j in range(i - 1, -1, -1):
            parent_id, _, parent_level = nodes[j]
            if parent_level < level:
                result.append(f'  {parent_id} --> {node_id}')
                break

    return "\n".join(result)


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
        # streamlit_mermaid mindmap rendering is unreliable — always convert to flowchart
        code = _mindmap_to_flowchart(code)
        dtype = "flowchart"

    if not code.strip():
        return _FALLBACK, "fallback"

    return code, dtype if dtype != "unknown" else "fallback"
