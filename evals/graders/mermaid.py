"""
Deterministic grader for Mermaid diagram outputs.
Each rule is binary: violation scores 0 for that dimension.
Final score is a dict of rule results plus an overall pass/fail.
Type-aware: applies different rules for mindmap vs flowchart/sequenceDiagram.
"""

import re
import subprocess
import tempfile


def _check_parse(diagram: str) -> tuple[bool, str]:
    """Run mmdc to check if the diagram is syntactically valid."""
    try:
        with tempfile.NamedTemporaryFile(suffix=".mmd", mode="w", delete=False) as tmp:
            tmp.write(diagram)
            tmp_path = tmp.name

        result = subprocess.run(
            ["mmdc", "-i", tmp_path, "-o", "/dev/null"],
            capture_output=True,
            timeout=10,
        )
        ok = result.returncode == 0
        return ok, result.stderr.decode().strip() if not ok else ""
    except FileNotFoundError:
        return True, "mmdc not installed (skipping parse check)"
    except subprocess.TimeoutExpired:
        return False, "mmdc timed out"


def _detect_type(diagram: str) -> str:
    first = diagram.strip().splitlines()[0].strip().lower()
    if first.startswith("mindmap"):
        return "mindmap"
    if first.startswith("sequencediagram"):
        return "sequenceDiagram"
    if first.startswith("flowchart") or first.startswith("graph"):
        return "flowchart"
    return "unknown"


def _node_count(diagram: str) -> int:
    """Count unique node IDs (A-Z0-9 style labels before [ or ( or { or -->)."""
    ids = re.findall(r'\b([A-Za-z0-9_]+)\s*[\[\({"\-]', diagram)
    keywords = {"flowchart", "graph", "LR", "TD", "RL", "BT", "subgraph", "end"}
    return len({i for i in ids if i not in keywords})


def _arrow_label_lengths(diagram: str) -> list[int]:
    """Return word counts of each arrow label (text inside |...|)."""
    labels = re.findall(r'\|([^|]+)\|', diagram)
    return [len(label.strip().split()) for label in labels]


def _mindmap_item_count(diagram: str) -> int:
    """Count non-empty content lines after the mindmap declaration."""
    lines = diagram.strip().splitlines()
    items = [l for l in lines[1:] if l.strip()]
    return len(items)


def _mindmap_has_root(diagram: str) -> bool:
    """Check that second line contains root((...)) syntax."""
    lines = diagram.strip().splitlines()
    if len(lines) < 2:
        return False
    return "root((" in lines[1]


def _mindmap_has_depth(diagram: str) -> bool:
    """Verify at least 3 indent levels exist (root + branch + leaf)."""
    lines = diagram.strip().splitlines()[1:]
    indent_levels = set()
    for line in lines:
        stripped = line.lstrip()
        if stripped:
            indent = len(line) - len(stripped)
            indent_levels.add(indent)
    return len(indent_levels) >= 3


def grade(diagram: str) -> dict:
    """
    Grade a Mermaid diagram on deterministic rules.
    Detects diagram type and applies type-specific rules.

    Returns dict with:
        - diagram_type: str
        - parse_ok, parse_note: bool, str
        - type-specific fields
        - hard_pass: bool (all rules pass)
        - score: float (fraction of rules passed, 0-1)
    """
    dtype = _detect_type(diagram)
    parse_ok, parse_note = _check_parse(diagram)

    stripped = re.sub(r'"[^"]*"', '""', diagram)
    no_special_chars = "&" not in stripped and "/" not in stripped

    if dtype == "mindmap":
        item_count = _mindmap_item_count(diagram)
        item_count_ok = 3 <= item_count <= 15
        has_root = _mindmap_has_root(diagram)
        has_depth = _mindmap_has_depth(diagram)

        rules = [parse_ok, item_count_ok, has_root, has_depth, no_special_chars]
        return {
            "diagram_type": "mindmap",
            "parse_ok": parse_ok,
            "parse_note": parse_note,
            "item_count": item_count,
            "item_count_ok": item_count_ok,
            "has_root": has_root,
            "has_depth": has_depth,
            "no_special_chars": no_special_chars,
            "hard_pass": all(rules),
            "score": sum(rules) / len(rules),
        }
    else:
        node_count = _node_count(diagram)
        node_count_ok = node_count <= 10
        no_subgraph = "subgraph" not in diagram.lower()
        arrow_lengths = _arrow_label_lengths(diagram)
        arrow_labels_ok = all(n <= 3 for n in arrow_lengths) if arrow_lengths else True

        rules = [parse_ok, node_count_ok, no_subgraph, no_special_chars, arrow_labels_ok]
        return {
            "diagram_type": dtype,
            "parse_ok": parse_ok,
            "parse_note": parse_note,
            "node_count": node_count,
            "node_count_ok": node_count_ok,
            "no_subgraph": no_subgraph,
            "no_special_chars": no_special_chars,
            "arrow_labels_ok": arrow_labels_ok,
            "arrow_label_lengths": arrow_lengths,
            "hard_pass": all(rules),
            "score": sum(rules) / len(rules),
        }
