import { useMemo } from "react";
import { useReactFlow } from "@xyflow/react";
import { useWorkflowStore } from "../store/useWorkflowStore";
import { validateDocument } from "../validation/engine";
import type { ValidationIssue } from "../validation/types";

const RULE_TITLES: Record<number, string> = {
  1: "Start reachability",
  2: "Start/end connectivity",
  3: "Decision branching",
  4: "Orphans & dead ends",
  5: "Fork/join reconciliation",
  6: "Loops",
  7: "Port direction",
  8: "Edge endpoint integrity",
  9: "Off-page references",
  10: "Lane/pool membership",
  11: "Required data on publish",
  12: "Id uniqueness & reserved words",
};

export function ValidationTab() {
  const document = useWorkflowStore((s) => s.document);
  const activePageId = useWorkflowStore((s) => s.activePageId);
  const setActivePage = useWorkflowStore((s) => s.setActivePage);
  const select = useWorkflowStore((s) => s.select);
  const { setCenter } = useReactFlow();

  const issues = useMemo(() => validateDocument(document), [document]);
  const errors = issues.filter((i) => i.severity === "error");
  const warnings = issues.filter((i) => i.severity === "warning");

  const focus = (issue: ValidationIssue) => {
    if (issue.pageId !== activePageId) setActivePage(issue.pageId);
    const page = document.pages.find((p) => p.id === issue.pageId);
    if (!page || !issue.elementId) return;

    if (issue.elementType === "node") {
      select({ nodeIds: [issue.elementId] });
      const n = page.nodes.find((x) => x.id === issue.elementId);
      if (n) setCenter(n.position.x + n.size.w / 2, n.position.y + n.size.h / 2, { zoom: 1, duration: 300 });
    } else if (issue.elementType === "edge") {
      select({ edgeIds: [issue.elementId] });
      const e = page.edges.find((x) => x.id === issue.elementId);
      const src = e && page.nodes.find((n) => n.id === e.source.nodeId);
      const tgt = e && page.nodes.find((n) => n.id === e.target.nodeId);
      if (src && tgt) {
        setCenter(
          (src.position.x + tgt.position.x) / 2 + src.size.w / 2,
          (src.position.y + tgt.position.y) / 2 + src.size.h / 2,
          { zoom: 1, duration: 300 }
        );
      }
    }
  };

  if (issues.length === 0) {
    return <p className="wf-inspector-empty">No issues found. Document passes the strict-flowchart profile.</p>;
  }

  const renderList = (list: ValidationIssue[]) =>
    list.map((issue) => (
      <div key={issue.id} className={`wf-issue wf-issue-${issue.severity}`} onClick={() => focus(issue)}>
        <div className="wf-issue-head">
          <span className={`wf-badge wf-badge-${issue.severity}`}>{issue.severity}</span>
          <span className="wf-issue-rule">Rule {issue.rule} - {RULE_TITLES[issue.rule]}</span>
        </div>
        <div className="wf-issue-message">{issue.message}</div>
      </div>
    ));

  return (
    <div className="wf-tab-validation">
      {errors.length > 0 && (
        <>
          <div className="wf-palette-heading">Errors ({errors.length})</div>
          {renderList(errors)}
        </>
      )}
      {warnings.length > 0 && (
        <>
          <div className="wf-palette-heading">Warnings ({warnings.length})</div>
          {renderList(warnings)}
        </>
      )}
    </div>
  );
}
