import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Pan-zoom wrapper around the exact SOP diagram SVG (GET .../flow-sop/diagram.svg,
 * rendered server-side by strategy/flow_sop/diagram.py -- unchanged, pixel-identical to the
 * reference project's own output). The SVG markup is fetched as text and injected inline
 * (real <svg> in the DOM, not an <img src="...">) so it behaves like native vector content --
 * sharp at any zoom, sized to its own viewBox -- instead of a flatly embedded picture. This
 * only adds a viewport around the unchanged SVG: wheel-to-zoom, drag-to-pan, and the same
 * +/-/Fit View control row the older react-flow canvas had. Deliberately NOT routed through
 * react-flow/the generic flow-builder canvas -- that's what produced the wrong shapes/colors
 * before; this keeps the correct SVG and only adds a viewport around it.
 */

const MIN_SCALE = 0.2;
const MAX_SCALE = 3;
const STEP = 1.2;

export function SopDiagramViewer({ src, alt, overrideMarkup }: {
  src: string; alt: string;
  /** SVG markup to show instead of fetching `src` -- how the Flow Editor's chat pushes an
   *  edited diagram in without a request round trip through the .../diagram.svg endpoint
   *  (which only ever knows the unedited, freshly-generated spec). */
  overrideMarkup?: string | null;
}) {
  const [scale, setScale] = useState(1);
  const [tx, setTx] = useState(0);
  const [ty, setTy] = useState(0);
  const [markup, setMarkup] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const dragRef = useRef<{ x: number; y: number; tx: number; ty: number } | null>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (overrideMarkup != null) { setMarkup(overrideMarkup); setError(null); return; }
    let live = true;
    setMarkup(null);
    setError(null);
    fetch(src).then((r) => {
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      return r.text();
    }).then((text) => { if (live) setMarkup(text); })
      .catch((e) => { if (live) setError(e instanceof Error ? e.message : String(e)); });
    return () => { live = false; };
  }, [src, overrideMarkup]);

  const clamp = (s: number) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, s));

  const zoomAt = useCallback((factor: number, cx?: number, cy?: number) => {
    setScale((prev) => {
      const next = clamp(prev * factor);
      const vp = viewportRef.current;
      if (vp) {
        const rect = vp.getBoundingClientRect();
        const px = cx ?? rect.width / 2;
        const py = cy ?? rect.height / 2;
        setTx((prevTx) => px - ((px - prevTx) / prev) * next);
        setTy((prevTy) => py - ((py - prevTy) / prev) * next);
      }
      return next;
    });
  }, []);

  const onWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const rect = viewportRef.current?.getBoundingClientRect();
    const cx = rect ? e.clientX - rect.left : undefined;
    const cy = rect ? e.clientY - rect.top : undefined;
    zoomAt(e.deltaY < 0 ? STEP : 1 / STEP, cx, cy);
  };

  const onPointerDown = (e: React.PointerEvent) => {
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    dragRef.current = { x: e.clientX, y: e.clientY, tx, ty };
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (!dragRef.current) return;
    setTx(dragRef.current.tx + (e.clientX - dragRef.current.x));
    setTy(dragRef.current.ty + (e.clientY - dragRef.current.y));
  };
  const onPointerUp = () => { dragRef.current = null; };

  /** Fits the diagram's width to the viewport's width -- not width-and-height both, which is
   *  what made a tall diagram (segmentation spine + journey lanes stacked below it) render
   *  tiny to also satisfy the height constraint. Height overflow is expected and fine: drag
   *  to pan down to the rest, the same gesture used at any other zoom level. */
  const fitView = useCallback(() => {
    const vp = viewportRef.current;
    const svg = canvasRef.current?.querySelector("svg");
    const w = svg ? parseFloat(svg.getAttribute("width") || "0") : 0;
    const h = svg ? parseFloat(svg.getAttribute("height") || "0") : 0;
    if (!vp || !svg || !w || !h) { setScale(1); setTx(0); setTy(0); return; }
    const rect = vp.getBoundingClientRect();
    const pad = 32;
    const next = clamp((rect.width - pad) / w);
    setScale(next);
    setTx((rect.width - w * next) / 2);
    setTy(pad / 2);
  }, []);

  useEffect(() => { if (markup) fitView(); }, [markup, fitView]);

  return (
    <div className="jc-sop-viewport" ref={viewportRef} onWheel={onWheel}
      onPointerDown={onPointerDown} onPointerMove={onPointerMove}
      onPointerUp={onPointerUp} onPointerLeave={onPointerUp}>
      {error && <div className="jc-empty">Couldn't load the diagram: {error}</div>}
      {markup && (
        <div className="jc-sop-canvas" ref={canvasRef} role="img" aria-label={alt}
          style={{ transform: `translate(${tx}px, ${ty}px) scale(${scale})` }}
          dangerouslySetInnerHTML={{ __html: markup }} />
      )}
      <div className="jc-sop-controls">
        <button type="button" aria-label="Zoom in" onClick={() => zoomAt(STEP)}>+</button>
        <button type="button" aria-label="Zoom out" onClick={() => zoomAt(1 / STEP)}>&minus;</button>
        <button type="button" aria-label="Fit view" onClick={fitView}>Fit</button>
      </div>
    </div>
  );
}
