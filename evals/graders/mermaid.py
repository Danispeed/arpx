"""
Deterministic grader for Mermaid diagram outputs.
Each rule is binary: violation scores 0 for that dimension.
Final score is a dict of rule results plus an overall pass/fail.
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
        # mmdc not installed — skip this check, warn only
        return True, "mmdc not installed (skipping parse check)"
    except subprocess.TimeoutExpired:
        return False, "mmdc timed out"


def _node_count(diagram: str) -> int:
    """Count unique node IDs (A-Z0-9 style labels before [ or ( or { or -->)."""
    # Match node declarations like: A[...] or A(...) or A{...} or standalone A -->
    ids = re.findall(r'\b([A-Za-z0-9_]+)\s*[\[\({"\-]', diagram)
    # Exclude flowchart/graph keywords
    keywords = {"flowchart", "graph", "LR", "TD", "RL", "BT", "subgraph", "end"}
    return len({i for i in ids if i not in keywords})


def _arrow_label_lengths(diagram: str) -> list[int]:
    """Return word counts of each arrow label (text inside |...|)."""
    labels = re.findall(r'\|([^|]+)\|', diagram)
    return [len(label.strip().split()) for label in labels]


def grade(diagram: str) -> dict:
    """
    Grade a Mermaid diagram on deterministic rules.

    Returns:
        {
            "parse_ok": bool,
            "parse_note": str,
            "node_count": int,
            "node_count_ok": bool,   # <= 10
            "no_subgraph": bool,
            "no_special_chars": bool,  # no & or / outside quotes
            "arrow_labels_ok": bool,   # all labels <= 3 words
            "arrow_label_lengths": list[int],
            "hard_pass": bool,         # all hard rules pass
            "score": float,            # fraction of rules passed (0-1)
        }
    """
    parse_ok, parse_note = _check_parse(diagram)
    node_count = _node_count(diagram)
    node_count_ok = node_count <= 10
    no_subgraph = "subgraph" not in diagram.lower()

    # Check for & or / outside of quoted strings
    stripped = re.sub(r'"[^"]*"', '""', diagram)
    no_special_chars = "&" not in stripped and "/" not in stripped

    arrow_lengths = _arrow_label_lengths(diagram)
    arrow_labels_ok = all(n <= 3 for n in arrow_lengths) if arrow_lengths else True

    rules = [parse_ok, node_count_ok, no_subgraph, no_special_chars, arrow_labels_ok]
    hard_pass = all(rules)

    return {
        "parse_ok": parse_ok,
        "parse_note": parse_note,
        "node_count": node_count,
        "node_count_ok": node_count_ok,
        "no_subgraph": no_subgraph,
        "no_special_chars": no_special_chars,
        "arrow_labels_ok": arrow_labels_ok,
        "arrow_label_lengths": arrow_lengths,
        "hard_pass": hard_pass,
        "score": sum(rules) / len(rules),
    }
