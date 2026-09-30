"""Cleaning and checking the segment SQL before it goes to Data Cloud."""
from __future__ import annotations

import re

from .dataset import DMO

# Statements a segment query must never contain. (REPLACE is left out: it's also a string
# function; CREATE OR REPLACE is caught by CREATE.)
_WRITE_WORDS = ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "MERGE", "CREATE", "TRUNCATE", "GRANT", "REVOKE")


def _outside_strings(sql: str):
    """(index, char, inside_single_quotes) for every character; '' is an escaped quote."""
    inside = False
    i = 0
    while i < len(sql):
        c = sql[i]
        if c == "'":
            if inside and i + 1 < len(sql) and sql[i + 1] == "'":
                yield i, c, True
                yield i + 1, "'", True
                i += 2
                continue
            inside = not inside
            yield i, c, True
        else:
            yield i, c, inside
        i += 1


def _mask_strings(sql: str) -> str:
    """The SQL with single-quoted string contents blanked, for keyword checks."""
    return "".join(" " if inside and c != "'" else c for _, c, inside in _outside_strings(sql))


def _double_quoted_values_to_single(sql: str) -> str:
    """Data Cloud reads "Opted In" as a column name (the query fails with "unknown column");
    a value in double quotes is meant as a string, so it becomes 'Opted In'."""
    out: list[str] = []
    inside_single = False
    i = 0
    while i < len(sql):
        c = sql[i]
        if c == "'":
            if inside_single and i + 1 < len(sql) and sql[i + 1] == "'":
                out.append("''")
                i += 2
                continue
            inside_single = not inside_single
            out.append(c)
        elif c == '"' and not inside_single:
            end = sql.find('"', i + 1)
            if end < 0:
                out.append(c)
            else:
                out.append("'" + sql[i + 1:end].replace("'", "''") + "'")
                i = end
        else:
            out.append(c)
        i += 1
    return "".join(out)


def sanitize(sql: str) -> str:
    """Camille's sanitizeSQL, plus: markdown fences and a trailing semicolon removed, the FROM
    fix applied only to a table name (never to a column in EXTRACT(... FROM col) and the like),
    and double-quoted values turned into single-quoted strings."""
    if not sql or not isinstance(sql, str):
        return sql
    s = sql.strip()
    s = re.sub(r"^```(?:sql)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```$", "", s).strip()
    s = s.rstrip().rstrip(";").rstrip()
    # Camille: American vs British spelling, quoted identifiers, old / suffix-less DMO names.
    s = re.sub(r"\bspecialty__c\b", "speciality__c", s, flags=re.IGNORECASE)
    s = re.sub(r'"(\w+__c)"', r"\1", s)
    s = re.sub(r'"(\w+__dlm)"', r"\1", s)
    s = re.sub(r"\bhcp_segmentation_data(__dlm)?\b", DMO, s, flags=re.IGNORECASE)
    s = re.sub(r"\bhcp_segmentation_dummy_dataset_camille\b(?!__dlm)", DMO, s, flags=re.IGNORECASE)
    # Camille: the FROM clause always names the DMO.
    s = re.sub(r"\bFROM\s+(?!\w+__c\b)[A-Za-z0-9_]+", f"FROM {DMO}", s, count=1, flags=re.IGNORECASE)
    return _double_quoted_values_to_single(s)


_COMPARISON = re.compile(
    r"(?:\b[A-Za-z0-9_]+\.)?\b([A-Za-z0-9_]+__c)\s*(=|\bIN\b)\s*(\((?:\s*'(?:[^']|'')*'\s*,?)+\)|'(?:[^']|'')*')",
    re.IGNORECASE)


def unknown_values(sql: str, prof: dict) -> list[str]:
    """Warnings for `column = 'value'` / `column IN (...)` on a text column whose value the data
    doesn't have (Data Cloud matches strings exactly), e.g. speciality__c = 'Cardiology' when no
    HCP has that speciality: the condition can only ever match nobody."""
    known = {c["name"].lower(): (c["name"], c["values"]) for c in prof["columns"] if c["kind"] == "text" and c.get("values")}
    out: list[str] = []
    for m in _COMPARISON.finditer(sql or ""):
        col = known.get(m.group(1).lower())
        if not col:
            continue
        name, values = col
        for raw in re.findall(r"'((?:[^']|'')*)'", m.group(3)):
            v = raw.replace("''", "'")
            if v in values:
                continue
            shown = ", ".join(values[:12]) + (", …" if len(values) > 12 else "")
            msg = f"'{v}' isn't a value of {name} in the dataset, so that condition matches no HCPs (its values: {shown})."
            if msg not in out:
                out.append(msg)
    return out


def problems(sql: str) -> list[str]:
    """Why this SQL can't be a Data Cloud segment, in words the Tester Agent can act on."""
    if not sql or not str(sql).strip():
        return ["The SQL is empty."]
    masked = _mask_strings(sql)
    out: list[str] = []
    if not re.match(r"\s*(SELECT|WITH)\b", masked, flags=re.IGNORECASE):
        out.append("The SQL must be a single SELECT query.")
    if ";" in masked:
        out.append("The SQL must be one statement (no semicolons).")
    found = [w for w in _WRITE_WORDS if re.search(rf"\b{w}\b", masked, flags=re.IGNORECASE)]
    if found:
        out.append(f"The SQL must only read data (found {', '.join(found)}).")
    head = re.search(r"\bSELECT\b(.*?)\bFROM\b", masked, flags=re.IGNORECASE | re.DOTALL)
    select_list = head.group(1) if head else ""
    if not re.search(r"(?<![A-Za-z0-9_])hcp_id__c\b", select_list):
        out.append("The SELECT clause must include hcp_id__c.")
    if not re.search(r"\bKQ_hcp_id__c\b", select_list):
        out.append("The SELECT clause must include KQ_hcp_id__c alongside hcp_id__c.")
    if not re.search(rf"\bFROM\s+{DMO}\b", masked, flags=re.IGNORECASE):
        out.append(f"The query must select FROM {DMO}.")
    return out
