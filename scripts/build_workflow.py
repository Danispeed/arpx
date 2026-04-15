#!/usr/bin/env python3
"""Compile ARPX prompt YAML into the n8n workflow JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(
        "PyYAML is required. Install it with: python3 -m pip install pyyaml"
    ) from exc


ROOT = Path(__file__).resolve().parent.parent
PROMPTS_PATH = ROOT / "n8n_workflows" / "prompts.yaml"
WORKFLOW_PATH = ROOT / "n8n_workflows" / "arpx-mvp.json"


def require_key(obj: dict[str, Any], key: str, parent: str) -> Any:
    if key not in obj:
        raise ValueError(f"Missing required key '{parent}.{key}'")
    return obj[key]


def require_string(obj: dict[str, Any], key: str, parent: str) -> str:
    value = require_key(obj, key, parent)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Expected non-empty string for '{parent}.{key}'")
    return value.strip()


def require_list_of_strings(obj: dict[str, Any], key: str, parent: str) -> list[str]:
    value = require_key(obj, key, parent)
    if not isinstance(value, list) or not value:
        raise ValueError(f"Expected non-empty list for '{parent}.{key}'")
    for i, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"Expected string at '{parent}.{key}[{i}]'")
    return [item.strip() for item in value]


def load_prompts(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError("prompts.yaml must contain a top-level mapping")
    return data


def format_constraints(constraints: list[str]) -> str:
    lines = ["Shared constraints:"] + [f"- {item}" for item in constraints]
    return "\n".join(lines)


def format_level_bands(level_bands: dict[str, Any]) -> str:
    if not isinstance(level_bands, dict) or not level_bands:
        raise ValueError("Expected non-empty mapping for 'explainer.level_bands'")

    lines = ["Level adaptation policy:"]
    for band_name, band_value in level_bands.items():
        if not isinstance(band_value, dict):
            raise ValueError(f"Expected mapping for 'explainer.level_bands.{band_name}'")
        band_range = require_string(band_value, "range", f"explainer.level_bands.{band_name}")
        guidance = require_string(
            band_value, "guidance", f"explainer.level_bands.{band_name}"
        )
        lines.append(f"- Levels {band_range} ({band_name}): {guidance}")
    lines.append("Always use the provided user level to choose depth and vocabulary.")
    return "\n".join(lines)


def build_system_prompts(prompts: dict[str, Any]) -> tuple[str, str]:
    shared = require_key(prompts, "shared", "root")
    if not isinstance(shared, dict):
        raise ValueError("Expected mapping for 'shared'")
    constraints = require_list_of_strings(shared, "constraints", "shared")
    constraints_text = format_constraints(constraints)

    explainer = require_key(prompts, "explainer", "root")
    if not isinstance(explainer, dict):
        raise ValueError("Expected mapping for 'explainer'")
    explainer_system = require_string(explainer, "system", "explainer")
    level_policy = format_level_bands(require_key(explainer, "level_bands", "explainer"))

    mermaid = require_key(prompts, "mermaid", "root")
    if not isinstance(mermaid, dict):
        raise ValueError("Expected mapping for 'mermaid'")
    mermaid_system = require_string(mermaid, "system", "mermaid")

    compiled_explainer = "\n\n".join([explainer_system, constraints_text, level_policy])
    compiled_mermaid = "\n\n".join([mermaid_system, constraints_text])
    return compiled_explainer, compiled_mermaid


def get_user_templates(prompts: dict[str, Any]) -> tuple[str, str]:
    explainer = require_key(prompts, "explainer", "root")
    mermaid = require_key(prompts, "mermaid", "root")
    if not isinstance(explainer, dict) or not isinstance(mermaid, dict):
        raise ValueError("'explainer' and 'mermaid' must be mappings")
    explainer_user = require_string(
        explainer, "user_template_expression", "explainer"
    )
    mermaid_user = require_string(mermaid, "user_template_expression", "mermaid")
    return explainer_user, mermaid_user


def render_json_body(
    *,
    system_prompt: str,
    user_expression: str,
    temperature: float,
    max_completion_tokens: int,
) -> str:
    system_quoted = json.dumps(system_prompt, ensure_ascii=True)
    return (
        "={{ { messages: [ "
        f"{{ role: \"system\", content: {system_quoted} }}, "
        f"{{ role: \"user\", content: {user_expression} }} "
        f"], temperature: {temperature}, max_completion_tokens: {max_completion_tokens} "
        "} }}"
    )


def find_node(workflow: dict[str, Any], node_name: str) -> dict[str, Any]:
    nodes = workflow.get("nodes")
    if not isinstance(nodes, list):
        raise ValueError("Workflow JSON must have a 'nodes' list")
    for node in nodes:
        if isinstance(node, dict) and node.get("name") == node_name:
            return node
    raise ValueError(f"Could not find node named '{node_name}'")


def inject_prompts(prompts: dict[str, Any], workflow: dict[str, Any]) -> None:
    explainer_system, mermaid_system = build_system_prompts(prompts)
    explainer_user, mermaid_user = get_user_templates(prompts)

    explainer_node = find_node(workflow, "ExplainerAgent")
    mermaid_node = find_node(workflow, "MermaidAgent")

    for node_name, node in [("ExplainerAgent", explainer_node), ("MermaidAgent", mermaid_node)]:
        params = node.get("parameters")
        if not isinstance(params, dict):
            raise ValueError(f"Node '{node_name}' is missing parameters")
        if params.get("specifyBody") != "json":
            raise ValueError(f"Node '{node_name}' must use JSON body mode")

    explainer_node["parameters"]["jsonBody"] = render_json_body(
        system_prompt=explainer_system,
        user_expression=explainer_user,
        temperature=0.5,
        max_completion_tokens=1200,
    )
    mermaid_node["parameters"]["jsonBody"] = render_json_body(
        system_prompt=mermaid_system,
        user_expression=mermaid_user,
        temperature=0.3,
        max_completion_tokens=900,
    )


def load_workflow(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Workflow JSON root must be an object")
    return data


def write_workflow(path: Path, workflow: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(workflow, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    prompts = load_prompts(PROMPTS_PATH)
    workflow = load_workflow(WORKFLOW_PATH)
    inject_prompts(prompts, workflow)
    write_workflow(WORKFLOW_PATH, workflow)
    print(f"Compiled prompts from {PROMPTS_PATH} into {WORKFLOW_PATH}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
