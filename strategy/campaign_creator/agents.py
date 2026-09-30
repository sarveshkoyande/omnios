"""The seven blueprint agents (Camille's reasoningEngine.js), streamed.

Each agent writes a free-text thinking block, a `---JSON_START---` line, then one JSON object;
`run` streams the text to the caller as it arrives and returns the parsed result. Prompts are
Camille's, with two changes: the Architect and the Flow QA Tester no longer carry one sample
campaign's Day 1-16 touchpoint list as the checklist to enforce (they check against the
touchpoints the requirements describe, and must not add others), and the Architect accepts
the current spec plus a refinement request, so a refinement edits the journey instead of
redrawing it.

Every agent also has a fallback built from the approved Campaign Briefing Document, used when
no model is configured or a call fails -- the OmniOS rule that an LLM call site degrades,
never hard-fails. Fallback output is plain and literal: it restates the brief's journey as a
flow; it does not invent logic the brief doesn't state.
"""
from __future__ import annotations

import json
import re
from typing import Callable

from . import llm, mermaid
from .briefing import NOT_SPECIFIED, normalize_briefing

ANALYST = "Document Analyst"
ARCHITECT = "Salesforce Architect"
QA = "Flow QA Tester"
DESIGNER = "Visual Designer"
TESTER = "Tester Agent"
VALIDATOR = "Flow Validator"
WRITER = "Technical Writer"
ROSTER = (ANALYST, ARCHITECT, QA, DESIGNER, TESTER, VALIDATOR, WRITER)

SUPPORTED_ELEMENTS = """## SUPPORTED ELEMENT TYPES
- Decision: { type: "Decision", name: "UniqueName", rules: [{ name, label, condition: {field, operator, value}, elements }], defaultElements: [] }
- Email: { type: "Email", name: "UniqueName", label, recipient, subject, body }
- UpdateRecord: { type: "UpdateRecord", name, label, object, assignments: {FieldName: Value} }
- CreateRecord: { type: "CreateRecord", name, label, object, assignments: {FieldName: Value} }
- Assignment: { type: "Assignment", name, label, assignments: [{field, value, operator}] }"""

_DESIGN_EXAMPLE = """graph TD
    startNode(("Campaign Entry:<br/>Record Triggered Contact"))
    exitNode(("Exit Campaign"))
    day1Email["Day 1: Send Specialty-Specific<br/>Educational Email"]
    day3Check{"Day 3: Check Email<br/>Open & Delivery Status"}
    day3Reminder["Day 3: Send Specialty<br/>Reminder Email"]
    reminderCheck{"Reminder Opened?"}
    day5Check{"Day 5: Check Engagement<br/>Click & Open Status"}
    day5Clinical["Day 5: Route to<br/>Clinical Content"]
    day5Final["Day 5: Send Final<br/>Touch Email"]
    day6Verify{"Day 6: Verify Consent<br/>Eligibility & Frequency"}
    day6Study["Day 6: Send Clinical<br/>Study Email"]
    day6Suppress["Day 6: Suppress<br/>Failed Compliance"]
    day8Check{"Day 8: Check Clinical<br/>Email Engagement"}
    day8Reminder["Day 8: Send Clinical<br/>Reminder Email"]
    day9CTA{"Day 9: Check CTA<br/>Click Status"}
    day9Followup["Day 9: Send CTA<br/>Follow-up Email"]
    day10Webinar["Day 10: Send Webinar<br/>Invitation Email"]
    day10RegCheck{"Day 10: Check<br/>Registration Status"}
    day14Reg{"Day 14: Registration<br/>Confirmed?"}
    day14Reminder["Day 14: Send Registration<br/>Reminder"]
    day16Final{"Day 16: Final<br/>Registration Check"}
    conversion["Conversion:<br/>Mark as Converted"]

    startNode --> day1Email
    day1Email --> day3Check
    day3Check -->|"Opened"| day5Check
    day3Check -->|"Not Opened"| day3Reminder
    day3Reminder --> reminderCheck
    reminderCheck -->|"Opened"| day5Check
    reminderCheck -->|"Not Opened"| exitNode
    day5Check -->|"Clicked or Opened"| day5Clinical
    day5Check -->|"No Engagement"| day5Final
    day5Final --> exitNode
    day5Clinical --> day6Verify
    day6Verify -->|"Valid"| day6Study
    day6Verify -->|"Failed"| day6Suppress
    day6Suppress --> exitNode
    day6Study --> day8Check
    day8Check -->|"Opened"| day9CTA
    day8Check -->|"Not Opened"| day8Reminder
    day8Reminder --> day9CTA
    day9CTA -->|"CTA Clicked"| day10Webinar
    day9CTA -->|"Not Clicked"| day9Followup
    day9Followup -->|"Clicked"| day10Webinar
    day9Followup -->|"Not Clicked"| exitNode
    day10Webinar --> day10RegCheck
    day10RegCheck -->|"Clicked"| day14Reg
    day10RegCheck -->|"Not Clicked"| exitNode
    day14Reg -->|"Registered"| conversion
    day14Reg -->|"Not Registered"| day14Reminder
    day14Reminder --> day16Final
    day16Final -->|"Registered"| conversion
    day16Final -->|"Not Registered"| exitNode
    conversion --> exitNode

    classDef decision fill:#ff9800,stroke:#e65100,stroke-width:3px,color:#000
    classDef action fill:#2196f3,stroke:#1565c0,stroke-width:2px,color:#fff
    classDef email fill:#4caf50,stroke:#2e7d32,stroke-width:2px,color:#fff
    classDef startEnd fill:#00bcd4,stroke:#006064,stroke-width:3px,color:#fff
    classDef check fill:#9c27b0,stroke:#6a1b9a,stroke-width:2px,color:#fff
    classDef suppress fill:#f44336,stroke:#c62828,stroke-width:2px,color:#fff

    class startNode,exitNode startEnd
    class day3Check,day5Check,day6Verify,day8Check,day9CTA,day10RegCheck,day14Reg,day16Final,reminderCheck decision
    class day1Email,day6Study,day10Webinar email
    class day3Reminder,day5Clinical,day5Final,day8Reminder,day9Followup,day14Reminder action
    class day6Suppress suppress
    class conversion check"""


def _j(v) -> str:
    return json.dumps(v, indent=2, ensure_ascii=False)


# ------------------------------------------------------------------ prompts -------------

def analyst_prompt(prompt: str) -> str:
    return f"""
You are an expert Business Analyst. Your SOLE job is to read the provided brief/prompt and extract the core business logic, ignoring specific CRM system constraints.

## YOUR PROCESS
1. **THINKING BLOCK**: Output your "Thinking Process". Write freely about your analysis, identifying personas, triggers, conditions, time delays, and actions.
2. **SEPARATOR**: Output "---JSON_START---" exactly on a new line.
3. **JSON BLOCK**: Output a structured summary.

## INPUT PROMPT
{prompt}

## AMBIGUITIES RULES — CRITICAL
The "ambiguities" array should ONLY contain genuinely impactful assumptions that could change the flow design. For each ambiguity:
- Reference the user's ACTUAL campaign details (brand, product, audience, timing, etc.)
- Explain what you assumed and WHY it matters
- Do NOT list obvious defaults (e.g., "Assumed email will be sent via email" or "Assumed Salesforce objects")
- Do NOT list more than 3 ambiguities. If the brief is comprehensive, return an empty array.
- Each ambiguity should be specific enough that overriding it would change the flow architecture

BAD ambiguity examples (too generic, NEVER write these):
- "Assumed standard email delivery"
- "Assumed Contact & Account objects as primary recipient targets"
- "Assumed digital consent required before email trigger dispatch"

GOOD ambiguity examples (specific, references the brief):
- "The brief mentions 'follow-up after engagement' but doesn't specify whether engagement means email open or link click — assumed email open as the trigger"
- "No re-entry rule specified — assumed each HCP enters the journey only once (no re-entry after exit)"
- "Voucher amounts not specified for Day 30 reactivation — assumed incremental values (₹500, ₹800, ₹1000)"

## OUTPUT FORMAT
[Raw Thinking Text...]
---JSON_START---
{{
  "businessGoal": "Summary of what they want to achieve",
  "triggerConcept": "What kicks off the process?",
  "targetAudience": "Who is this for?",
  "steps": [
    {{
      "sequence": 1,
      "condition": "If Applicable",
      "action": "What happens?",
      "delay": "Time delay if any"
    }}
  ],
  "ambiguities": ["Only genuinely impactful assumptions referencing the user's specific campaign — or empty array if brief is comprehensive"]
}}
"""


def architect_prompt(analysis: dict, metadata: dict, current_spec: dict | None = None, feedback: str | None = None) -> str:
    refinement = ""
    if current_spec and feedback:
        refinement = f"""
## EXISTING FLOW SPECIFICATION (DO NOT REGENERATE - MODIFY ONLY)
{_j(current_spec)}

## MODIFICATION REQUEST
"{feedback}"

## REFINEMENT INSTRUCTIONS - CRITICAL
You are modifying an EXISTING flow. Follow these rules strictly:
1. **START with the existing spec above** - This is your base
2. **Apply ONLY the requested changes** from the Modification Request
3. **PRESERVE all unchanged elements** exactly as they are
4. **Return the complete updated spec** with modifications applied

**CRITICAL**: Do NOT regenerate from scratch. Make targeted modifications only.

**Examples of Refinement**:
- "Change email subject" → Update ONLY the subject field, keep body, recipient, etc.
- "Add a follow-up on Day 7" → Add a scheduled path, keep all existing elements
- "Remove SMS" → Delete the SMS element, keep all other elements
- "Change threshold to 60 days" → Update ONLY the condition value, keep structure
"""
    return f"""
You are a Salesforce Data Architect. Take the business requirements provided and map them strictly to Salesforce Flow syntax.

## AVAILABLE SALESFORCE OBJECTS
{_j(metadata)}

## BUSINESS REQUIREMENTS
{_j(analysis)}
{refinement}
## YOUR PROCESS
1. **THINKING BLOCK**: Write freely about how you map the business logic to Salesforce objects and flow elements.
2. **SEPARATOR**: Output "---JSON_START---" exactly on a new line.
3. **JSON BLOCK**: Output the strict Flow Specification.

## CRITICAL FLOW TYPE RULES:
- ALWAYS use flowType: "RecordTriggered" — NEVER use "ScheduledTriggered"
- ALWAYS include triggerEvent: "CreateAndUpdate"
- Put initial/Day 1 actions in "immediateElements" so the flow executes immediately on record creation. DO NOT leave immediateElements empty.
- For time-based follow-up journeys (Day 3, Day 5, Day 14, etc.) use "scheduledPaths" array with {{ "label", "duration", "unit", "offsetReference", "elements" }}.
- TOKEN BUDGET & ARCHITECTURE: Keep the thinking block brief (under 100 words). Map every touchpoint the business requirements describe cleanly into immediateElements and scheduledPaths. DO NOT generate deeply nested redundant sub-branches inside every single day — keep each touchpoint concise so the entire spec completes without truncation.

## OUTPUT FORMAT
[Raw Thinking Text...]
---JSON_START---
{{
  "rationale": "Detailed explanation of your Salesforce architecture decisions.",
  "spec": {{
    "flowType": "RecordTriggered",
    "triggerObject": "Contact",
    "triggerEvent": "CreateAndUpdate",
    "immediateElements": [
      {{ "type": "Email", "name": "Email_Day1", "label": "Day 1 Educational Email", "recipient": "Contact.Email", "subject": "Welcome & Clinical Overview", "body": "Clinical details..." }}
    ],
    "scheduledPaths": [
      {{
        "label": "Day 3 Followup",
        "duration": 3,
        "unit": "Days",
        "offsetReference": "CreatedDate",
        "elements": [
          {{ "type": "Decision", "name": "Check_Engagement_D3", "label": "Check Day 3 Open", "rules": [{{ "name": "Opened_D3", "label": "Email Opened", "condition": {{ "field": "HasOptedOutOfEmail", "operator": "EqualTo", "value": false }}, "elements": [] }}], "defaultElements": [] }}
        ]
      }}
    ]
  }}
}}

{SUPPORTED_ELEMENTS}
- NEVER USE type: "Wait" — use scheduledPaths instead for time-based delays.
- NEVER USE flowType: "ScheduledTriggered" — always RecordTriggered.
"""


def qa_prompt(analysis: dict, raw_spec: dict, metadata: dict) -> str:
    return f"""
You are a Principal Salesforce Flow Quality Assurance Engineer and Release Auditor.
Your job is to rigorously test, audit, and certify the Salesforce Flow Specification generated by the Salesforce Architect against the original Business Requirements and Salesforce Metadata Schema so that it is 100% PRODUCTION READY.

## BUSINESS REQUIREMENTS (SOURCE OF TRUTH)
{_j(analysis)}

## DRAFT ARCHITECT FLOW SPECIFICATION TO TEST
{_j(raw_spec)}

## AVAILABLE SALESFORCE METADATA SCHEMA
{_j(metadata)}

## YOUR MANDATORY QA AUDIT CHECKLIST:
1. **FULL JOURNEY COMPLETION & COVERAGE**:
   - Verify that EVERY touchpoint and step the business requirements describe (each day, send, reminder, engagement check and follow-up) is present and fully fleshed out in the Flow specification.
   - If any touchpoint or scheduled path from the business requirements is missing or was truncated, YOU MUST COMPLETE IT by adding the missing scheduled paths.
   - Do NOT add touchpoints, days or actions that the business requirements do not describe.
2. **SALESFORCE TOOLING SCHEMA COMPLIANCE**:
   - Ensure flowType is strictly "RecordTriggered" and triggerEvent is "CreateAndUpdate".
   - Ensure "immediateElements" has the Day 1 entry actions (Email, Decisions, Updates) and is NEVER empty.
   - Ensure "scheduledPaths" has all time-delayed follow-ups with {{ "label", "duration", "unit", "offsetReference", "elements" }}.
   - Ensure all element types are strictly supported: ["Email", "Decision", "UpdateRecord", "CreateRecord", "Assignment"]. NEVER use "Wait" elements.
3. **FIELD & DML INTEGRITY**:
   - Ensure all decision conditions use valid fields that exist in the AVAILABLE SALESFORCE METADATA SCHEMA, and valid operators ("EqualTo", "NotEqualTo", "Contains", "In", "IsNull").
   - Ensure decision rules and element names are unique and descriptive.
4. **PRODUCTION CERTIFICATION**:
   - Return the 100% complete, certified production-ready Flow specification.

{SUPPORTED_ELEMENTS}
- CRITICAL: Decision elements MUST use the key "rules" (not "outcomes").

## YOUR PROCESS:
1. **THINKING BLOCK**: Act like a strict QA test runner. Output a clear test audit log verifying:
   - [PASS] Trigger & Entry Criteria
   - [PASS] Immediate Day 1 Path Actions
   - [PASS] Scheduled Paths Coverage (every touchpoint in the requirements)
   - [PASS] Field Schema & DML Safety
2. **SEPARATOR**: Output "---JSON_START---" exactly on a new line.
3. **JSON BLOCK**: Output the certified test report and the certified production-ready spec.

## OUTPUT FORMAT:
[QA Test Execution Log & Audit Thinking...]
---JSON_START---
{{
  "testReport": {{
    "status": "PASSED_AND_CERTIFIED",
    "journeyCoveragePercent": 100,
    "testsExecuted": [
      "Trigger & Entry Criteria Audit: PASSED",
      "Immediate Path Actions Test: PASSED",
      "Scheduled Paths Completeness (all requirement touchpoints): PASSED",
      "Salesforce Field Schema & DML Safety Test: PASSED"
    ],
    "fixesApplied": [
      "Verified all journey steps are fully mapped into immediateElements and scheduledPaths"
    ]
  }},
  "spec": {{
    "flowType": "RecordTriggered",
    "triggerObject": "Contact",
    "triggerEvent": "CreateAndUpdate",
    "immediateElements": [
      {{ "type": "Email", "name": "Email_Day1_Educational", "label": "Day 1 Educational Email", "recipient": "Contact.Email", "subject": "Clinical insights for your practice", "body": "Initial educational content." }}
    ],
    "scheduledPaths": [
      {{
        "label": "Day 3 Follow-up (72h)",
        "duration": 72,
        "unit": "Hours",
        "offsetReference": "CreatedDate",
        "elements": [
          {{ "type": "Email", "name": "Email_D3_Reminder", "label": "Day 3 Reminder", "recipient": "Contact.Email", "subject": "Reminder: clinical insights", "body": "Reminder content." }}
        ]
      }}
    ]
  }}
}}
"""


def designer_prompt(spec: dict, feedback: str = "", original_prompt: str = "") -> str:
    feedback_block = f"\n## FEEDBACK TO INCORPORATE\n{feedback}" if feedback else ""
    return f"""
You are an expert Flow UX Designer. Your job is to create a complete, detailed Mermaid JS flowchart that visually represents the ENTIRE campaign journey described by the user.

## PRIMARY SOURCE — ORIGINAL USER CAMPAIGN BRIEF (USE THIS AS YOUR MAIN REFERENCE):
{original_prompt or 'Not provided — use the Flow Specification below instead.'}

## SECONDARY SOURCE — SALESFORCE FLOW SPECIFICATION (supplementary technical context):
{_j(spec)}
{feedback_block}

**IMPORTANT**: The Original User Campaign Brief above is your PRIMARY source. It contains the detailed day-by-day journey with every decision branch, engagement check, and action. The Flow Specification is a technical mapping that may have LOST detail. Always refer back to the Original Brief to ensure NOTHING is missing.

## YOUR PROCESS
1. **THINKING BLOCK**:
   a. First, read the ORIGINAL USER CAMPAIGN BRIEF above carefully.
   b. List EVERY day/step mentioned (e.g., "Day 1, Day 3, Day 5, Day 6, Day 8, Day 9, Day 10, Day 14, Day 16").
   c. For each day, list EVERY action and decision branch described.
   d. Count the total number of nodes you need. Your diagram MUST have at least this many nodes.
   e. Plan the flow: which nodes connect to which, with what edge labels.
2. **SEPARATOR**: Output "---JSON_START---" exactly on a new line.
3. **JSON BLOCK**: Output the final valid Mermaid code in JSON.

## COMPLETENESS RULE (HIGHEST PRIORITY):
- Read the ORIGINAL USER CAMPAIGN BRIEF carefully. Every day, step, decision, action, check, reminder, and exit condition mentioned MUST have its own node in the diagram.
- If the user describes Day 1, Day 3, Day 5, Day 6, Day 8, Day 9, Day 10, Day 14, Day 16 — your diagram MUST have nodes covering ALL of those days. That's 9 days minimum, likely 20+ nodes with all branches.
- Do NOT stop early. Do NOT merge multiple days into one node. Do NOT simplify or summarize.
- If a day has multiple branches (e.g., "Opened → do X, Not opened → do Y"), EACH branch must be a separate node.
- **BEFORE generating JSON, count your nodes and compare to the user's brief. If you have fewer nodes than steps described, you are WRONG — go back and add the missing ones.**

## CRITICAL MERMAID RULES:

### LABEL RULES:
1. **Labels MUST be descriptive and explanatory** — NOT short abbreviations.
   - CORRECT: day1Email["Day 1: Send Specialty-Specific<br/>Educational Email to HCPs"]
   - WRONG: email1["Email Day1"]
   - CORRECT: day3Check{{"Day 3: Check Email<br/>Open & Delivery Status"}}
   - WRONG: check3{{"Check D3"}}

2. **Use <br/> to wrap long labels across 2-3 lines** so text fits neatly inside node boxes.
   - Each line should be roughly 25-35 characters max.

3. Labels MUST be in double quotes. e.g. email30["My Label"]

### SYNTAX RULES:
1. Node IDs: alphanumeric only — NO spaces, hyphens, or special chars. Use semantic IDs: day1Email, day3Check, day5Engage
2. NO SUBGRAPHS allowed.
3. NO :::className inline syntax. WRONG: email30["label"]:::email. Instead use class lines at the bottom.
4. NEVER use reserved words as node IDs: start, end, subgraph, graph.
5. Node Shapes: Start/End = (("Label")), Decision = {{"Label"}}, Action = ["Label"]
   CRITICAL: Use EXACTLY TWO parentheses for circle nodes: (("Label")). NEVER use three: ((("Label"))). Triple parens will crash the renderer.
6. For sequential day-by-day campaigns, build a SEQUENTIAL flow with decision branches (not parallel branches from start).

## HOW TO APPLY STYLING (at the BOTTOM after all edges):
classDef decision fill:#ff9800,stroke:#e65100,stroke-width:3px,color:#000
classDef action fill:#2196f3,stroke:#1565c0,stroke-width:2px,color:#fff
classDef email fill:#4caf50,stroke:#2e7d32,stroke-width:2px,color:#fff
classDef startEnd fill:#00bcd4,stroke:#006064,stroke-width:3px,color:#fff
classDef check fill:#9c27b0,stroke:#6a1b9a,stroke-width:2px,color:#fff
classDef suppress fill:#f44336,stroke:#c62828,stroke-width:2px,color:#fff

class startNode,exitNode startEnd
class day3Check,day5Check decision
class day1Email,day6Study email
class day3Reminder,day5Clinical action

## COMPLETE EXAMPLE — Sequential HCP Email Campaign:
{_DESIGN_EXAMPLE}

## OUTPUT FORMAT
[Raw Thinking Text - count ALL steps from the spec, plan every node...list EVERY day/action...]
---JSON_START---
{{
  "mermaid": "graph TD\\n    startNode((\\"Campaign Entry:<br/>Record Triggered Contact\\"))\\n    exitNode((\\"Exit Campaign\\"))\\n    [ALL YOUR NODES HERE with descriptive labels using <br/> for wrapping]\\n    [ALL YOUR EDGES HERE]\\n    classDef decision fill:#ff9800,stroke:#e65100,stroke-width:3px,color:#000\\n    classDef action fill:#2196f3,stroke:#1565c0,stroke-width:2px,color:#fff\\n    classDef email fill:#4caf50,stroke:#2e7d32,stroke-width:2px,color:#fff\\n    classDef startEnd fill:#00bcd4,stroke:#006064,stroke-width:3px,color:#fff\\n    classDef check fill:#9c27b0,stroke:#6a1b9a,stroke-width:2px,color:#fff\\n    classDef suppress fill:#f44336,stroke:#c62828,stroke-width:2px,color:#fff\\n    class startNode,exitNode startEnd"
}}
"""


def tester_prompt(code: str) -> str:
    return f"""You are a strict Mermaid JS Parser and Syntax Validator.
Your job is to scrutinize the provided Mermaid code block for syntax errors, specifically looking for common issues that crash the renderer (like v11.12.2).

## MERMAID CODE TO TEST
```mermaid
{code}
```

## VALIDATION RULES
1. All text inside nodes MUST be enclosed in double quotes. (e.g. `node1["Some text"]` NOT `node1[Some text]`)
2. Node IDs MUST NOT contain special characters or spaces. (e.g. `node_1` is good, `node 1` is bad)
3. Node IDs MUST NOT be reserved keywords like "end", "subgraph", etc.
4. There MUST NOT be unescaped parentheses `()`, brackets `[]`, or curly braces `{{}}` inside node labels unless they are strictly inside double quotes.
5. Lines styling edges or nodes must end properly without trailing malformed characters (like `stroke-width:2px;1`).
6. Nodes MUST NOT have mismatched opening and closing brackets or extra brackets. For example, `node["Label"]]` is INVALID (extra bracket). `node["Label"}}` is INVALID (mismatched brackets). Correct format is `node["Label"]`.

## YOUR PROCESS
1. **THINKING BLOCK**: Act like a compiler. Go line by line. If you find a syntax error, describe exactly what line is broken and why.
2. **SEPARATOR**: Output "---JSON_START---" exactly.
3. **JSON BLOCK**: Provide your validation report.

## OUTPUT FORMAT
[Raw Thinking Text...]
---JSON_START---
{{
  "isValid": true|false,
  "feedback": "If invalid, explain EXACTLY what the Designer needs to fix. If valid, leave blank."
}}
"""


def validator_prompt(spec: dict) -> str:
    return f"""You are a strict Salesforce Flow Validator.
Your job is to review the proposed Flow Architecture and flag any potential limits, logic flaws, or best-practice violations.

## FLOW SPECIFICATION
{_j(spec)}

## YOUR PROCESS
1. **THINKING BLOCK**: Analyze the flow for DML limits, SOQL limits in loops, recursion risk, and general best practices.
2. **SEPARATOR**: Output "---JSON_START---" exactly.
3. **JSON BLOCK**: Provide your validation report.

## OUTPUT FORMAT
[Raw Thinking Text...]
---JSON_START---
{{
  "isValid": true|false,
  "warnings": ["Warning 1", "Warning 2"],
  "recommendations": ["Do this instead", "Consider adding X"]
}}
"""


def writer_prompt(brief: dict, spec: dict, validation: dict) -> str:
    return f"""You are an expert Salesforce Technical Architect and Documentation Specialist.
Your job is to produce a comprehensive Technical Design document wrapping up the entire generation process.

## INPUTS
* **Campaign Brief:** {json.dumps(brief, ensure_ascii=False)}
* **Flow Specification:** {json.dumps(spec, ensure_ascii=False)}
* **Validation Report:** {json.dumps(validation, ensure_ascii=False)}

## YOUR PROCESS
1. **THINKING BLOCK**: Synthesize the inputs into a cohesive narrative for an executive or senior developer.
2. **SEPARATOR**: Output "---JSON_START---" exactly.
3. **JSON BLOCK**: Provide the final documentation.

## OUTPUT FORMAT
[Raw Thinking Text...]
---JSON_START---
{{
    "executiveSummary": "High level overview...",
    "architectureDecision": "Why this flow structure was chosen...",
    "testingStrategy": ["Test case 1", "Test case 2"]
}}
"""


# ------------------------------------------------------------------ running an agent ----

def run(prompt: str, on_chunk: Callable[[str], None] | None, should_stop: Callable[[], bool] | None) -> dict:
    """One streamed agent call -> {fullText, thought, parsed, usage}."""
    text, usage = llm.complete(prompt, on_chunk=on_chunk, should_stop=should_stop)
    thought, parsed = llm.split_reasoning(text)
    return {"fullText": text, "thought": thought, "parsed": parsed, "usage": usage}


def normalize_spec_envelope(parsed, wrapper_key: str, default_wrapper) -> dict | None:
    """Camille's post-processing of an Architect / QA reply: accept a bare spec, ensure the
    element arrays exist, and promote the first scheduled path when Run Immediately is empty."""
    if not isinstance(parsed, dict):
        return None
    if not isinstance(parsed.get("spec"), dict) and (parsed.get("flowType") or parsed.get("immediateElements") or parsed.get("scheduledPaths")):
        parsed = {wrapper_key: parsed.get(wrapper_key) or default_wrapper, "spec": parsed}
    spec = parsed.get("spec")
    if not isinstance(spec, dict):
        return None
    if not isinstance(spec.get("immediateElements"), list):
        spec["immediateElements"] = []
    if not isinstance(spec.get("scheduledPaths"), list):
        spec["scheduledPaths"] = []
    if not spec["immediateElements"] and spec["scheduledPaths"]:
        first = spec["scheduledPaths"][0]
        if isinstance(first, dict) and first.get("elements"):
            spec["immediateElements"] = first["elements"]
            spec["scheduledPaths"] = spec["scheduledPaths"][1:]
    return parsed


# ------------------------------------------------------------------ fallbacks -----------

def _day(timing: str, default: int) -> int:
    m = re.search(r"\d+", timing or "")
    if not m:
        return default
    n = int(m.group(0))
    return n * 7 if re.search(r"week", timing, re.IGNORECASE) else n


def analysis_from_briefing(briefing: dict) -> dict:
    b = normalize_briefing(briefing)
    ov = b["campaignOverview"]
    steps = [{"sequence": i + 1, "condition": "", "action": f"{j['stage']}: {j['actions']}".strip(": "), "delay": j["timing"]}
             for i, j in enumerate(b["journeyFlow"])]
    return {
        "businessGoal": ov.get("objective") or b["journeyEndGoals"] or NOT_SPECIFIED,
        "triggerConcept": "; ".join(b["journeyEntryCriteria"]) or "An eligible Contact record is created or updated",
        "targetAudience": ov.get("primaryAudience") or NOT_SPECIFIED,
        "steps": steps,
        "ambiguities": [],
    }


def spec_from_briefing(briefing: dict) -> dict:
    """The brief's journey flow as a record-triggered flow: entry-day steps run immediately,
    each later day becomes a scheduled path offset from the record's creation. The entry day
    is Day 0 when the brief uses a Day 0, else Day 1."""
    b = normalize_briefing(briefing)
    immediate: list[dict] = []
    paths: dict[int, dict] = {}
    days = [_day(step["timing"], i + 1) for i, step in enumerate(b["journeyFlow"])]
    entry_day = 0 if 0 in days else 1
    for i, step in enumerate(b["journeyFlow"]):
        day = days[i]
        title = step["stage"] or step["timing"] or f"Step {i + 1}"
        email = {"type": "Email", "name": f"Email_Step_{i + 1}", "label": title[:80], "recipient": "Contact.Email",
                 "subject": title[:120], "body": step["actions"] or title}
        if day <= entry_day:
            immediate.append(email)
        else:
            path = paths.setdefault(day, {"label": step["timing"] or f"Day {day}", "duration": day - entry_day, "unit": "Days",
                                          "offsetReference": "CreatedDate", "elements": []})
            path["elements"].append(email)
    if not immediate and not paths:
        return {"flowType": "RecordTriggered", "triggerObject": "Contact", "triggerEvent": "CreateAndUpdate",
                "immediateElements": [{"type": "Email", "name": "Email_Day1", "label": "Day 1 Initial Email",
                                       "recipient": "Contact.Email", "subject": "Campaign Kickoff",
                                       "body": "Initial educational communication."}],
                "scheduledPaths": [{"label": "Day 3 Followup", "duration": 3, "unit": "Days", "offsetReference": "CreatedDate",
                                    "elements": [{"type": "Email", "name": "Email_Day3", "label": "Day 3 Reminder Email",
                                                  "recipient": "Contact.Email", "subject": "Follow-up",
                                                  "body": "Follow-up communication."}]}]}
    ordered = [paths[d] for d in sorted(paths)]
    if not immediate:
        immediate = ordered[0]["elements"]
        ordered = ordered[1:]
    return {"flowType": "RecordTriggered", "triggerObject": "Contact", "triggerEvent": "CreateAndUpdate",
            "immediateElements": immediate, "scheduledPaths": ordered}


def validate_rules(spec: dict, requirements: str = "") -> dict:
    """A structural review of the spec when the Validator model isn't available."""
    from .flow_xml import summarize
    s = summarize(spec)
    warnings, recs = [], []
    if not s["total"]:
        warnings.append("The flow has no actions.")
    emails = s["elements"].get("Email", 0)
    if emails:
        warnings.append(f"{emails} Send Email action(s): each counts against the org's daily single-email limit.")
    if not s["elements"].get("Decision"):
        recs.append("Add a consent check (for example HasOptedOutOfEmail) before the first send.")
    if s["scheduled_paths"]:
        recs.append("Scheduled paths run relative to the triggering record's save time; confirm that matches the journey's day count.")
    if re.search(r"\b(sms|whatsapp|text message)\b", requirements or "", re.IGNORECASE):
        recs.append("SMS and WhatsApp require Marketing Cloud or a custom integration; only Email is native to Salesforce Flow.")
    return {"isValid": bool(s["total"]), "warnings": warnings, "recommendations": recs}


def docs_from(briefing: dict, spec: dict, validation: dict) -> dict:
    from .flow_xml import summarize
    b = normalize_briefing(briefing)
    s = summarize(spec)
    return {
        "executiveSummary": (f"{b['campaignName']}: a record-triggered Salesforce Flow on {spec.get('triggerObject', 'Contact')} "
                             f"with {len(spec.get('immediateElements') or [])} immediate action(s) and {s['scheduled_paths']} "
                             f"scheduled path(s), built from the approved Campaign Briefing Document."),
        "architectureDecision": ("A record-triggered flow runs the Day 1 actions on entry, and each later touchpoint is a "
                                 "scheduled path offset from the record's creation, so no Wait elements are needed."),
        "testingStrategy": ["Create a test Contact that meets the entry criteria and confirm the Day 1 action runs.",
                            "Confirm every scheduled path is queued with the right offset.",
                            "Opt the test Contact out of email and confirm no further sends.",
                            *[f"Review: {w}" for w in (validation.get("warnings") or [])[:2]]],
    }


def diagram_fallback(spec: dict) -> str:
    return mermaid.from_spec(spec)
