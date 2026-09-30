"""Mermaid handling for the journey diagram.

`sanitize` is Camille's sanitizeMermaidCode (reasoningEngine.js, the fuller of its two copies),
run on every diagram the Visual Designer returns. `from_spec` is new: when no model is
available (or the Designer fails) it draws the flow spec itself, in the same node grammar and
class palette the Designer is asked to use, so the blueprint always has a diagram.
"""
from __future__ import annotations

import re

# The class palette the Visual Designer prompt prescribes (reasoningEngine.js).
CLASS_DEFS = (
    "classDef decision fill:#ff9800,stroke:#e65100,stroke-width:3px,color:#000",
    "classDef action fill:#2196f3,stroke:#1565c0,stroke-width:2px,color:#fff",
    "classDef email fill:#4caf50,stroke:#2e7d32,stroke-width:2px,color:#fff",
    "classDef startEnd fill:#00bcd4,stroke:#006064,stroke-width:3px,color:#fff",
    "classDef check fill:#9c27b0,stroke:#6a1b9a,stroke-width:2px,color:#fff",
    "classDef wait fill:#607d8b,stroke:#37474f,stroke-width:2px,color:#fff",
    "classDef suppress fill:#f44336,stroke:#c62828,stroke-width:2px,color:#fff",
)


def sanitize(code):
    """Fix the syntax errors models commonly make before the diagram reaches the renderer."""
    if not code or not isinstance(code, str):
        return code
    s = code
    # Triple parentheses for circle nodes -> double: ((("Label"))) -> (("Label"))
    s = re.sub(r'\(\(\(("(?:[^"\\]|\\.)*")\)\)\)', r"((\1))", s)
    s = re.sub(r"\(\(\(([^()]*)\)\)\)", r"((\1))", s)
    # Inline :::className (classes belong in `class` lines at the bottom)
    s = re.sub(r"\]:::[\w]+", "]", s)
    s = re.sub(r"\):::[\w]+", ")", s)
    s = re.sub(r"\}:::[\w]+", "}", s)
    # Four or more parentheses
    s = re.sub(r"\({4,}", "((", s)
    s = re.sub(r"\){4,}", "))", s)
    # `end` used as a node id (reserved) -> endNode, in declarations and edge targets
    s = re.sub(r"(?:^|\n)\s*end\s*(\[|\(|\{)",
               lambda m: re.sub(r"end\s*(\[|\(|\{)", r"endNode\1", m.group(0), count=1), s, flags=re.M)
    s = re.sub(r"--> end(?:\s|$)", "--> endNode\n", s, flags=re.M)
    s = re.sub(r"-->(\|[^|]*\|)\s*end(?:\s|$)", r"-->\1 endNode\n", s, flags=re.M)
    # A stray semicolon after the graph declaration
    s = re.sub(r"^(graph\s+(?:TD|TB|LR|RL|BT))\s*;", r"\1", s, count=1, flags=re.M)
    # A one-line reply with literal \n sequences
    if "\n" not in s and "\\n" in s:
        s = s.replace("\\n", "\n")
    # Markdown fences that leaked into the code
    s = re.sub(r"^```mermaid\s*", "", s, flags=re.M)
    s = re.sub(r"^```\s*$", "", s, flags=re.M)
    # Mismatched or extra brackets: ["Label"]] -> ["Label"], ["Label"} -> ["Label"]
    s = re.sub(r'\["([^"]*)"\]\]', r'["\1"]', s)
    s = re.sub(r'\["([^"]*)"\}', r'["\1"]', s)
    return s.strip()


# ------------------------------------------------------------------ spec -> diagram -----

_DRAWN = {"Email", "Decision", "UpdateRecord", "CreateRecord", "Assignment", "GetRecords", "Loop"}


def _label(text: str, width: int = 30) -> str:
    """A node label: quotes made safe, wrapped across lines with <br/> (the Designer's rule:
    roughly 25-35 characters per line)."""
    raw = str(text or "").replace('"', "'").replace("`", "'")
    # Mermaid entity codes, so label text can never be read as markup or syntax.
    raw = raw.replace("#", "#35;").replace("<", "#lt;").replace(">", "#gt;")
    words = re.sub(r"\s+", " ", raw).strip().split(" ")
    lines: list[str] = []
    line = ""
    for w in words:
        if line and len(line) + 1 + len(w) > width:
            lines.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
    if line:
        lines.append(line)
    return "<br/>".join(lines[:4]) or "Step"


class _Builder:
    def __init__(self) -> None:
        self.nodes: list[str] = []
        self.edges: list[str] = []
        self.classes: dict[str, list[str]] = {}
        self._n = 0
        self._seen_edges: set[tuple[str, str, str]] = set()

    def new_id(self, prefix: str) -> str:
        self._n += 1
        return f"{prefix}{self._n}"

    def node(self, nid: str, shape: str, label: str, cls: str) -> None:
        text = _label(label)
        if shape == "circle":
            self.nodes.append(f'    {nid}(("{text}"))')
        elif shape == "diamond":
            self.nodes.append(f'    {nid}{{"{text}"}}')
        else:
            self.nodes.append(f'    {nid}["{text}"]')
        self.classes.setdefault(cls, []).append(nid)

    def edge(self, a: str, b: str, label: str = "") -> None:
        key = (a, b, label)
        if key in self._seen_edges:
            return
        self._seen_edges.add(key)
        if label:
            self.edges.append(f'    {a} -->|"{_label(label, 40)}"| {b}')
        else:
            self.edges.append(f"    {a} --> {b}")

    def chain(self, elements, after: str) -> str:
        els = [e for e in (elements or []) if isinstance(e, dict) and e.get("type") in _DRAWN]
        ids = [self.new_id("step") for _ in els]
        for i, el in enumerate(els):
            nid = ids[i]
            nxt = ids[i + 1] if i + 1 < len(els) else after
            kind = el.get("type")
            label = el.get("label") or el.get("name") or kind
            if kind == "Decision":
                self.node(nid, "diamond", label, "decision")
                for rule in el.get("rules") or []:
                    if not isinstance(rule, dict):
                        continue
                    first = self.chain(rule.get("elements"), nxt)
                    self.edge(nid, first, rule.get("label") or rule.get("name") or "Yes")
                first = self.chain(el.get("defaultElements"), nxt)
                self.edge(nid, first, "Default outcome")
            elif kind == "Loop":
                self.node(nid, "rect", f"For each: {label}", "action")
                inner = self.chain(el.get("loopElements"), nid)
                if inner != nid:
                    self.edge(nid, inner, "Next item")
                self.edge(nid, nxt, "Done")
            else:
                cls = "email" if kind == "Email" else "action"
                self.node(nid, "rect", label, cls)
                self.edge(nid, nxt)
        return ids[0] if ids else after


def from_spec(spec: dict) -> str:
    """Draw a Salesforce flow spec as Mermaid: entry, the immediate path, and each scheduled
    path as its own branch from the entry (Salesforce's structure: scheduled paths are
    parallel branches from the start)."""
    spec = spec or {}
    b = _Builder()
    trigger = f"{spec.get('triggerEvent') or 'CreateAndUpdate'} {spec.get('triggerObject') or 'Contact'}"
    b.node("startNode", "circle", f"Campaign Entry: Record Triggered {trigger}", "startEnd")
    b.node("exitNode", "circle", "Exit Campaign", "startEnd")
    first = b.chain(spec.get("immediateElements"), "exitNode")
    b.edge("startNode", first, "Run immediately" if spec.get("scheduledPaths") else "")
    for idx, path in enumerate(spec.get("scheduledPaths") or []):
        if not isinstance(path, dict):
            continue
        pid = f"path{idx + 1}"
        when = f"{path.get('duration', '')} {path.get('unit', '')}".strip()
        b.node(pid, "rect", f"{path.get('label') or f'Scheduled path {idx + 1}'}" + (f" (after {when})" if when else ""), "wait")
        b.edge("startNode", pid, "Scheduled path")
        b.edge(pid, b.chain(path.get("elements"), "exitNode"))
    lines = ["graph TD", *b.nodes, "", *b.edges, "", *(f"    {c}" for c in CLASS_DEFS)]
    for cls, ids in b.classes.items():
        lines.append(f"    class {','.join(ids)} {cls}")
    return "\n".join(lines)
