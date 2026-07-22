// Arrowhead marker defs (Section 3.3 arrowhead catalog). Uses SVG2 context-stroke so a
// single marker set works for every edge color instead of generating one marker per hex.
export function EdgeMarkerDefs() {
  return (
    <svg width="0" height="0" style={{ position: "absolute" }}>
      <defs>
        <marker id="wf-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="context-stroke" />
        </marker>
        <marker id="wf-open-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10" fill="none" stroke="context-stroke" strokeWidth="1.5" />
        </marker>
        <marker id="wf-circle" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <circle cx="5" cy="5" r="4" fill="white" stroke="context-stroke" strokeWidth="1.5" />
        </marker>
        <marker id="wf-circle-filled" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <circle cx="5" cy="5" r="4" fill="context-stroke" />
        </marker>
        <marker id="wf-cross" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M 1 1 L 9 9 M 9 1 L 1 9" stroke="context-stroke" strokeWidth="1.5" />
        </marker>
        <marker id="wf-diamond" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
          <polygon points="5,0 10,5 5,10 0,5" fill="white" stroke="context-stroke" strokeWidth="1.5" />
        </marker>
        <marker id="wf-diamond-filled" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
          <polygon points="5,0 10,5 5,10 0,5" fill="context-stroke" />
        </marker>
      </defs>
    </svg>
  );
}

export function markerUrl(kind: string): string | undefined {
  if (kind === "none") return undefined;
  return `url(#wf-${kind})`;
}
