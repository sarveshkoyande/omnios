import { useEffect, useRef, useState } from "react";

type MermaidApi = (typeof import("mermaid"))["default"];

/** Mermaid is large, so it loads only when a journey diagram is first shown (its own chunk). */
let loading: Promise<MermaidApi> | null = null;

function token(name: string, fallback: string): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

function loadMermaid(): Promise<MermaidApi> {
  if (!loading) {
    loading = import("mermaid").then(({ default: m }) => {
      // Camille's diagram settings, coloured from the Cockpit's own tokens (cockpit.css :root).
      m.initialize({
        startOnLoad: false,
        theme: "base",
        securityLevel: "strict", // labels still keep <br/> line breaks (DOMPurify allows them)
        themeVariables: {
          primaryColor: token("--primary-light-background", "#F5F0FF"),
          primaryTextColor: token("--fg", "#231F20"),
          primaryBorderColor: token("--primary", "#5D2CC9"),
          lineColor: token("--muted", "#6D6E71"),
          mainBkg: token("--base-white", "#FFFFFF"),
          nodeBorder: token("--primary", "#5D2CC9"),
          clusterBkg: token("--neutral-50", "#FAFAFA"),
          clusterBorder: token("--neutral-300", "#D1D5DB"),
          defaultLinkColor: token("--muted", "#6D6E71"),
          titleColor: token("--fg", "#231F20"),
          edgeLabelBackground: token("--base-white", "#FFFFFF"),
          fontFamily: '"DM Sans", sans-serif',
          fontSize: "13px",
        },
        flowchart: { useMaxWidth: true, htmlLabels: true, curve: "basis", padding: 25, nodeSpacing: 60, rankSpacing: 100 },
      });
      return m;
    }).catch((e) => { loading = null; throw e; });
  }
  return loading;
}

/** Camille's client-side safety net for model-written Mermaid (the server sanitises too). */
function sanitize(code: string): string {
  let s = code;
  s = s.replace(/\(\(\(("(?:[^"\\]|\\.)*")\)\)\)/g, "(($1))");
  s = s.replace(/\(\(\(([^()]*)\)\)\)/g, "(($1))");
  s = s.replace(/]:::[\w]+/g, "]").replace(/\):::[\w]+/g, ")").replace(/}:::[\w]+/g, "}");
  s = s.replace(/\({4,}/g, "((").replace(/\){4,}/g, "))");
  if (!s.includes("\n") && s.includes("\\n")) s = s.replace(/\\n/g, "\n");
  s = s.replace(/^```mermaid\s*/gm, "").replace(/^```\s*$/gm, "");
  return s.trim();
}

function download(name: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Camille's PNG export: HTML labels (foreignObject) are swapped for SVG text first, because a
 *  canvas refuses to draw foreignObject content and would produce a blank image. */
function exportPng(svgEl: SVGSVGElement, name: string) {
  const clone = svgEl.cloneNode(true) as SVGSVGElement;
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  clone.setAttribute("xmlns:xlink", "http://www.w3.org/1999/xlink");
  clone.querySelectorAll("foreignObject").forEach((fo) => {
    const parent = fo.parentNode;
    if (!parent) return;
    const tmp = document.createElement("div");
    tmp.innerHTML = fo.innerHTML;
    const content = (tmp.textContent ?? "").trim();
    const x = parseFloat(fo.getAttribute("x") ?? "0") || 0;
    const y = parseFloat(fo.getAttribute("y") ?? "0") || 0;
    const w = parseFloat(fo.getAttribute("width") ?? "100") || 100;
    const h = parseFloat(fo.getAttribute("height") ?? "30") || 30;
    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", String(x + w / 2));
    text.setAttribute("y", String(y + h / 2));
    text.setAttribute("text-anchor", "middle");
    text.setAttribute("dominant-baseline", "central");
    text.setAttribute("font-family", "DM Sans, sans-serif");
    text.setAttribute("font-size", "13");
    text.setAttribute("fill", "#231F20");
    const max = Math.max(10, Math.floor(w / 7));
    const lines: string[] = [];
    let cur = "";
    for (const word of content.split(/\s+/)) {
      if ((cur + " " + word).trim().length > max && cur) { lines.push(cur.trim()); cur = word; } else { cur = cur ? `${cur} ${word}` : word; }
    }
    if (cur.trim()) lines.push(cur.trim());
    const lh = 16;
    lines.forEach((line, i) => {
      const t = document.createElementNS("http://www.w3.org/2000/svg", "tspan");
      t.setAttribute("x", text.getAttribute("x") ?? "0");
      t.setAttribute("dy", String(i === 0 ? -((lines.length - 1) * lh) / 2 : lh));
      t.textContent = line;
      text.appendChild(t);
    });
    parent.replaceChild(text, fo);
  });
  let width = 0;
  let height = 0;
  const vb = clone.getAttribute("viewBox");
  if (vb) {
    const parts = vb.split(/[\s,]+/).map(Number);
    width = parts[2];
    height = parts[3];
  } else {
    width = parseFloat(clone.getAttribute("width") ?? "") || 800;
    height = parseFloat(clone.getAttribute("height") ?? "") || 600;
  }
  clone.setAttribute("width", String(width));
  clone.setAttribute("height", String(height));
  const pad = 40;
  const scale = 2;
  const canvas = document.createElement("canvas");
  canvas.width = (width + pad * 2) * scale;
  canvas.height = (height + pad * 2) * scale;
  const ctx = canvas.getContext("2d");
  const svgText = new XMLSerializer().serializeToString(clone);
  const url = URL.createObjectURL(new Blob([svgText], { type: "image/svg+xml;charset=utf-8" }));
  const img = new Image();
  img.onload = () => {
    if (ctx) {
      ctx.scale(scale, scale);
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, width + pad * 2, height + pad * 2);
      ctx.drawImage(img, pad, pad, width, height);
    }
    URL.revokeObjectURL(url);
    canvas.toBlob((blob) => { if (blob) download(`${name}.png`, blob); }, "image/png");
  };
  img.onerror = () => {
    URL.revokeObjectURL(url);
    download(`${name}.svg`, new Blob([svgText], { type: "image/svg+xml;charset=utf-8" }));
  };
  img.src = url;
}

export function MermaidView({ code, fileName = "journey-flow" }: { code: string; fileName?: string }) {
  const host = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [actual, setActual] = useState(false);
  const [showCode, setShowCode] = useState(false);

  useEffect(() => {
    let live = true;
    setError(null);
    const id = `ccm-${Math.random().toString(36).slice(2, 10)}`;
    loadMermaid()
      .then((m) => m.render(id, sanitize(code)))
      .then(({ svg: out }) => { if (live) setSvg(out); })
      .catch((e: unknown) => {
        document.getElementById(`d${id}`)?.remove();
        document.getElementById(id)?.remove();
        if (live) { setSvg(""); setError(e instanceof Error ? e.message : String(e)); }
      });
    return () => { live = false; };
  }, [code]);

  const svgEl = () => host.current?.querySelector("svg") as SVGSVGElement | null;

  return (
    <div className="v3-cc-mermaid">
      <div className="v3-cc-mermaid-bar">
        <button type="button" onClick={() => setActual((a) => !a)} disabled={!svg}>{actual ? "Fit to width" : "Actual size"}</button>
        <button type="button" onClick={() => { const el = svgEl(); if (el) exportPng(el, fileName); }} disabled={!svg}>Download PNG</button>
        <button type="button" disabled={!svg} onClick={() => {
          const el = svgEl();
          if (el) download(`${fileName}.svg`, new Blob([new XMLSerializer().serializeToString(el)], { type: "image/svg+xml;charset=utf-8" }));
        }}>Download SVG</button>
        <button type="button" onClick={() => setShowCode((s) => !s)} aria-pressed={showCode}>{showCode ? "Hide code" : "Mermaid code"}</button>
      </div>
      {error && <div className="v3-cc-banner error">The diagram couldn't be drawn: {error}</div>}
      {!svg && !error && <div className="v3-cc-mermaid-loading">Drawing the journey…</div>}
      <div ref={host} className={`v3-cc-mermaid-canvas ${actual ? "actual" : ""}`} dangerouslySetInnerHTML={{ __html: svg }} />
      {showCode && <pre className="v3-cc-code">{code}</pre>}
    </div>
  );
}
