/**
 * Plan document skin — the Brand Engagement Plan (~25 section renderers: SWOT,
 * Gantt, RACI, toolkit tables, benchmarks, content library, precedents, awards…)
 * is composed entirely server-side (orchestrator.recompose_plan / plan_document.py)
 * as ready-to-inject HTML, not structured JSON — there is no per-section data API
 * for the client to rebuild these as discrete React components without a backend
 * change. Reimplementing 25 renderers as components fed by nothing would mean
 * screen-scraping our own HTML, which is worse than the alternative taken here:
 * treat the document as its own self-contained artifact (like inserting a scanned
 * exact replica) and port its legacy stylesheet verbatim, scoped under one class,
 * with its own local palette — same principle already established for the
 * workbook-replica (.tk-*) colors elsewhere in this app: exact fidelity over
 * reskinning. Modern CSS nesting (Chrome 112+/Edge 112+) is used throughout to
 * scope ~250 legacy selectors under .plan-doc-skin without hand-prefixing each one.
 */
export const planDocSkinCss = `
.plan-doc-skin {
  container-type: inline-size;
  --indegene-navy: #0B3D91;
  --indegene-cyan: #00AEEF;
  --text: #1B2436; --muted: #5B6478; --faint: #8891A3;
  --accent: var(--indegene-navy);
  --accent-soft: rgba(0,174,239,0.16);
  --line: rgba(11,61,145,0.14);
  --green: #17A673; --amber: #C77700; --red: #D6455B;
  --glass: rgba(255,255,255,0.55);
  --glass-strong: rgba(255,255,255,0.85);
  --glass-blur: blur(10px) saturate(150%);
  --shadow-raised-sm: 0 6px 16px -8px rgba(11,61,145,0.20), inset 0 1px 0 rgba(255,255,255,0.6);
  --tk-magenta: #C6007E; --tk-cyan: #00AEEF; --tk-navy: #002060; --tk-grey: #808080;
  --tk-green: #92D050; --tk-band: #0070C0; --tk-msg-green: #E2EFDA; --tk-msg-orange: #F4B183;
  --tk-msg-blue: #DEEBF7; --tk-open: #B45309; --tk-open-bg: #FEF3C7;

  font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
  color: var(--text);
  font-size: 12.5px;
  line-height: 1.55;

  h1 { font-size: 16px; margin: 0 0 4px; }
  h2 { font-size: 13.5px; margin: 16px 0 6px; padding-top: 10px; border-top: 1px solid var(--line); color: var(--indegene-navy); }
  h3 { font-size: 12px; margin: 10px 0 4px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
  p { margin: 6px 0; }
  ul { margin: 4px 0; padding-left: 18px; }
  li { margin-bottom: 3px; }

  .plan-sub { color: var(--muted); font-size: 11.5px; }
  .plan-kv, .plan-table { width: 100%; border-collapse: collapse; margin: 6px 0; font-size: 11.5px; }
  .plan-kv th { text-align: left; color: var(--muted); font-weight: 500; padding: 3px 8px 3px 0; vertical-align: top; white-space: nowrap; }
  .plan-kv td { padding: 3px 0; }
  .plan-table th, .plan-table td { border: 1px solid var(--line); padding: 4px 6px; text-align: left; }
  .plan-table th { color: var(--muted); }
  .plan-statement { border-left: 3px solid var(--indegene-cyan); margin: 6px 0; padding: 8px 12px; background: var(--accent-soft); border-radius: 0 8px 8px 0; font-style: italic; }
  .plan-doc { margin: 3px 0; }
  .plan-src { color: var(--faint); font-size: 10px; text-transform: uppercase; letter-spacing: 0.03em; margin-right: 5px; }
  .plan-empty { color: var(--faint); font-style: italic; }
  .plan-caveat { color: var(--faint); font-style: italic; font-size: 11px; }
  .plan-bar-row { display: flex; align-items: center; gap: 8px; margin: 4px 0; font-size: 11.5px; }
  .plan-bar-row .material-symbols-outlined { font-size: 15px; color: var(--indegene-navy); flex: 0 0 auto; }
  .plan-bar-label { flex: 0 0 88px; color: var(--muted); }
  .plan-bar-track { flex: 1; height: 12px; background: rgba(11,61,145,0.08); border-radius: 3px; overflow: hidden; }
  .plan-bar-fill { height: 100%; background: linear-gradient(90deg, var(--indegene-navy), var(--indegene-cyan)); }
  .plan-bar-val { flex: 0 0 auto; color: var(--faint); font-size: 11px; }

  .plan-toc {
    position: sticky; top: -14px; z-index: 4; display: flex; flex-wrap: wrap; gap: 6px;
    margin: 2px -4px 14px; padding: 10px 4px 12px; background: linear-gradient(var(--glass-strong) 75%, transparent);
    a {
      display: inline-flex; align-items: center; gap: 4px; font-size: 10.5px; font-weight: 600;
      color: var(--indegene-navy); background: rgba(11,61,145,0.07); border: 1px solid var(--line); border-radius: 999px;
      padding: 4px 9px; text-decoration: none; white-space: nowrap;
      .material-symbols-outlined { font-size: 13px; }
      &:hover { background: var(--accent-soft); }
    }
  }

  .plan-sec {
    scroll-margin-top: 44px; margin: 6px 0; border: 1px solid var(--line); border-radius: 10px;
    background: var(--glass); backdrop-filter: var(--glass-blur); -webkit-backdrop-filter: var(--glass-blur);
    box-shadow: var(--shadow-raised-sm);
    > summary.plan-sec-head {
      display: flex; align-items: center; gap: 9px; margin: 0;
      padding: 9px 12px; cursor: pointer; list-style: none; user-select: none;
      &::-webkit-details-marker { display: none; }
      .material-symbols-outlined { font-size: 17px; color: #fff; background: var(--indegene-navy); border-radius: 8px; padding: 5px; flex: 0 0 auto; }
      h2 { margin: 0; border: none; padding: 0; font-size: 13.5px; color: var(--indegene-navy); }
      &::after { content: ""; flex: 1; height: 1px; background: var(--line); }
    }
    .plan-sec-chev { font-size: 18px !important; color: var(--muted) !important; background: none !important; padding: 0 !important; transition: transform .18s ease; }
    &[open] > summary .plan-sec-chev { transform: rotate(180deg); }
    .plan-sec-body { padding: 2px 12px 12px; }
    .plan-sec-sub { margin: 10px 0 6px; }
  }
  .tk-sec-align > summary .material-symbols-outlined:first-child { background: var(--tk-magenta); }
  .tk-sec-select > summary .material-symbols-outlined:first-child { background: var(--tk-cyan); }
  .tk-sec-create > summary .material-symbols-outlined:first-child { background: var(--tk-navy); }
  .tk-sec-deploy > summary .material-symbols-outlined:first-child { background: var(--tk-grey); }

  .plan-hero {
    display: flex; gap: 10px; align-items: flex-start; margin: 2px 0 4px; padding: 12px 14px;
    background: linear-gradient(135deg, rgba(0,174,239,0.14), rgba(11,61,145,0.07)); border: 1px solid rgba(0,174,239,0.25);
    border-radius: 12px;
    .material-symbols-outlined { font-size: 20px; color: var(--indegene-navy); flex: 0 0 auto; margin-top: 1px; }
    p { margin: 0; }
  }

  .plan-badges { display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0 12px; }
  .plan-badge {
    display: inline-flex; align-items: center; gap: 4px; font-size: 11px; font-weight: 600;
    padding: 4px 10px; border-radius: 999px; background: rgba(11,61,145,0.08); color: var(--indegene-navy);
    .material-symbols-outlined { font-size: 13px; }
  }

  .plan-swot-grid {
    display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 8px 0 14px;
    @container (max-width: 500px) { grid-template-columns: 1fr; }
  }
  .plan-swot-cell {
    border-radius: 10px; padding: 10px 12px; border: 1px solid var(--line);
    h3 { display: flex; align-items: center; gap: 5px; margin: 0 0 6px; text-transform: none; letter-spacing: 0; font-size: 11.5px; color: inherit;
      .material-symbols-outlined { font-size: 15px; } }
    ul { margin: 0; padding-left: 15px; }
    li { margin-bottom: 3px; }
  }
  .s-strength { background: rgba(18,134,111,0.07); border-color: rgba(18,134,111,0.28); color: #12866F; }
  .s-weak { background: rgba(198,40,40,0.06); border-color: rgba(198,40,40,0.22); color: #B3261E; }
  .s-opp { background: rgba(23,104,209,0.07); border-color: rgba(23,104,209,0.25); color: #1768D1; }
  .s-threat { background: rgba(166,114,10,0.07); border-color: rgba(166,114,10,0.25); color: #A6720A; }

  .plan-precedent-card {
    border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px; margin: 6px 0;
    background: var(--glass-strong); backdrop-filter: var(--glass-blur); -webkit-backdrop-filter: var(--glass-blur);
    box-shadow: var(--shadow-raised-sm);
    .pc-title { font-weight: 700; font-size: 12.5px; margin-bottom: 4px; display: flex; align-items: center; gap: 7px; flex-wrap: wrap; }
    .pc-meta { font-size: 11px; color: var(--muted); }
  }
  .tier-badge { display: inline-flex; align-items: center; font-size: 9.5px; font-weight: 700; padding: 2px 8px; border-radius: 999px; text-transform: uppercase; letter-spacing: 0.03em; }
  .tier-gold { background: rgba(191,149,15,0.18); color: #8A6A05; }
  .tier-silver { background: rgba(120,130,140,0.20); color: #51565C; }
  .tier-bronze { background: rgba(176,98,50,0.20); color: #8A4A20; }

  .plan-gantt { margin: 10px 0 14px; }
  .plan-gantt-row { display: flex; align-items: center; gap: 8px; margin: 5px 0; font-size: 11px; }
  .plan-gantt-label { flex: 0 0 200px; color: var(--muted);
    @container (max-width: 560px) { flex-basis: 120px; }
  }
  .plan-gantt-track { flex: 1; display: grid; grid-template-columns: repeat(var(--total-weeks), 1fr); gap: 2px; height: 20px; }
  .plan-gantt-bar { border-radius: 4px; background: linear-gradient(90deg, var(--indegene-navy), var(--indegene-cyan)); color: #fff; font-size: 9.5px; display: flex; align-items: center; justify-content: center; white-space: nowrap; overflow: hidden; cursor: default; }

  /* Customer Engagement Planning Toolkit -- exact workbook replica styles. */
  .tk-home {
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 8px 0 12px;
    @container (max-width: 640px) { grid-template-columns: repeat(2, 1fr); }
  }
  .tk-ribbon {
    color: #fff; font-weight: 700; font-size: 11px; text-align: center; padding: 9px 8px 13px;
    border-radius: 4px; position: relative; margin-bottom: 10px; line-height: 1.3;
    clip-path: polygon(0 0, 100% 0, 100% 100%, 54% 100%, 50% 86%, 46% 100%, 0 100%);
  }
  .tk-align { --tkc: var(--tk-magenta); } .tk-select { --tkc: var(--tk-cyan); }
  .tk-create { --tkc: var(--tk-navy); } .tk-deploy { --tkc: var(--tk-grey); }
  .tk-ribbon.tk-align { background: var(--tk-magenta); } .tk-ribbon.tk-select { background: var(--tk-cyan); }
  .tk-ribbon.tk-create { background: var(--tk-navy); } .tk-ribbon.tk-deploy { background: var(--tk-grey); }
  .tk-item {
    display: flex; align-items: center; gap: 7px; margin: 6px 0; padding: 5px 9px 5px 4px;
    border-radius: 999px; color: #fff; font-size: 10.5px; font-weight: 600; text-decoration: none;
    &:hover { filter: brightness(1.12); }
    .tk-num { flex: 0 0 20px; height: 20px; border-radius: 50%; background: #fff; color: #333; display: flex; align-items: center; justify-content: center; font-size: 10.5px; font-weight: 700; border: 1.5px solid rgba(0,0,0,0.15); }
  }
  .tk-item.tk-align { background: color-mix(in srgb, var(--tk-magenta) 88%, #fff); }
  .tk-item.tk-select { background: color-mix(in srgb, var(--tk-cyan) 92%, #000 4%); }
  .tk-item.tk-create { background: var(--tk-navy); }
  .tk-item.tk-deploy { background: color-mix(in srgb, var(--tk-grey) 90%, #fff); }
  .tk-item-label { text-decoration: underline; }

  .tk-phase-banner {
    color: #fff; font-weight: 700; font-size: 12.5px; padding: 9px 14px; border-radius: 8px;
    margin: 18px 0 6px; display: flex; align-items: center; gap: 10px;
    .tk-phase-no { font-size: 9.5px; text-transform: uppercase; letter-spacing: 0.08em; background: rgba(255,255,255,0.22); border-radius: 999px; padding: 2px 8px; }
  }
  .tk-phase-banner.tk-align { background: var(--tk-magenta); } .tk-phase-banner.tk-select { background: var(--tk-cyan); }
  .tk-phase-banner.tk-create { background: var(--tk-navy); } .tk-phase-banner.tk-deploy { background: var(--tk-grey); }
  .tk-phase-banner.tk-support { background: color-mix(in srgb, var(--indegene-navy) 24%, #fff); color: var(--indegene-navy); }

  .plan-open-chip { display: inline-flex; align-items: center; font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: var(--tk-open); background: var(--tk-open-bg); border: 1px solid #F59E0B55; border-radius: 999px; padding: 2px 7px; margin-left: 6px; white-space: nowrap; }
  .plan-open-row td { background: color-mix(in srgb, var(--tk-open-bg) 45%, transparent); }
  .plan-openq-group {
    border: 1px solid #F59E0B55; background: color-mix(in srgb, var(--tk-open-bg) 40%, transparent);
    border-radius: 10px; padding: 9px 12px; margin: 7px 0;
    ul { margin: 5px 0 0; padding-left: 17px; }
  }
  .plan-openq-title { font-weight: 700; font-size: 12px; color: var(--tk-open); }
  .plan-openq-src { font-weight: 500; font-size: 10px; color: var(--faint); margin-left: 6px; }

  .tk-qtable {
    width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 11px;
    th, td { border: 1px solid #9aa7bd; padding: 5px 7px; text-align: left; vertical-align: top; }
    tr.tk-qhead th { background: var(--tk-navy); color: #fff; font-weight: 700; }
    tr.tk-band td { background: var(--tk-band); color: #fff; font-weight: 700; text-align: center; }
  }
  .tk-srno { text-align: center; width: 34px; }
  .tk-oneidea div { margin: 2px 0; }
  .tk-dist { display: flex; gap: 4px; margin-top: 6px; flex-wrap: wrap; }
  .tk-dist-cell { border: 1px solid #333; border-radius: 3px; min-width: 44px; text-align: center; overflow: hidden; }
  .tk-dist-k { background: var(--tk-navy); color: #fff; font-size: 9.5px; font-weight: 700; padding: 2px 4px; }
  .tk-dist-v { padding: 2px 4px; font-weight: 600; }

  .tk-feas-wrap {
    display: flex; gap: 10px; align-items: flex-start; margin: 8px 0;
    @container (max-width: 620px) { flex-direction: column; .tk-legend { flex-direction: row; flex-basis: auto; } }
  }
  .tk-feas {
    flex: 1;
    .tk-cat { background: #f2f5fa; font-weight: 700; width: 110px; vertical-align: middle; }
    .tk-q { min-width: 180px; }
    td.tk-t0, td.tk-t1, td.tk-t2 { color: #fff; font-weight: 600; text-align: center; width: 84px; opacity: 0.45; }
    td.sel { opacity: 1; outline: 2.5px solid var(--indegene-navy); outline-offset: -2.5px; }
  }
  td.tk-t0 { background: var(--tk-cyan); } td.tk-t1 { background: var(--tk-magenta); } td.tk-t2 { background: var(--tk-green); }
  .tk-feas-note { font-size: 10px; color: var(--muted); font-style: italic; margin-top: 3px; }
  .tk-legend { flex: 0 0 170px; display: flex; flex-direction: column; gap: 8px; }
  .tk-legend-box {
    border-radius: 6px; color: #fff; padding: 8px 10px; font-size: 10.5px; line-height: 1.35;
    strong { display: block; margin-bottom: 3px; }
  }
  .tk-legend-box.tk-t0 { background: var(--tk-cyan); } .tk-legend-box.tk-t1 { background: var(--tk-magenta); }
  .tk-legend-box.tk-t2 { background: var(--tk-green); }
  .tk-level { display: inline-block; color: #fff; font-weight: 700; border-radius: 4px; padding: 1px 8px; }
  .tk-feas-overall { font-size: 12.5px; margin: 6px 0 2px; }

  .tk-mf-side { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0; }
  .tk-chip {
    border-radius: 8px; color: #fff; font-size: 10.5px; font-weight: 700; padding: 6px 10px; max-width: 240px;
    span { display: block; font-weight: 500; margin-top: 2px; }
  }
  .tk-chip-blue { background: #4472C4; } .tk-chip-navy { background: var(--tk-navy); } .tk-chip-cyan { background: var(--tk-cyan); }
  .tk-mf-pools {
    display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 10px; margin: 8px 0;
    @container (max-width: 620px) { grid-template-columns: 1fr; }
  }
  .tk-mf-pool h4 { margin: 0 0 5px; font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); font-style: italic; }
  .tk-pool { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
  .tk-pool-col { display: flex; flex-direction: column; gap: 6px; }
  .tk-depri { border: 1px solid #333; border-radius: 4px; min-height: 60px; padding: 6px; display: flex; flex-direction: column; gap: 5px; background: rgba(255,255,255,0.6); }
  .tk-msg { border-radius: 6px; padding: 7px 9px; font-size: 10.5px; line-height: 1.35; border: 1px solid rgba(0,0,0,0.12);
    .tk-msg-km { font-weight: 700; }
  }
  .tk-msg-green { background: var(--tk-msg-green); } .tk-msg-orange { background: var(--tk-msg-orange); }
  .tk-msg-blue { background: var(--tk-msg-blue); } .tk-msg-plain { background: #fff; }
  .tk-msg-empty { background: transparent; border: none; color: var(--faint); font-style: italic; }
  .tk-mf-bar { background: var(--tk-band); color: #fff; font-weight: 700; font-style: italic; text-align: center; font-size: 11px; padding: 6px 10px; border-radius: 4px; margin: 10px 0 8px; }
  .tk-mf-grid {
    display: grid; grid-template-columns: 70px repeat(4, 1fr); gap: 8px;
    @container (max-width: 620px) { grid-template-columns: 70px 1fr 1fr; }
  }
  .tk-mf-rail { background: var(--tk-navy); color: #fff; border-radius: 4px; font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; padding: 8px 6px; text-align: center; }
  .tk-mf-col { display: flex; flex-direction: column; gap: 6px; }

  .tk-impacts {
    display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin: 8px 0;
    @container (max-width: 680px) { grid-template-columns: 1fr 1fr; }
  }
  .tk-imp-col { display: flex; flex-direction: column; gap: 6px; }
  .tk-imp-head { background: var(--tk-band); color: #fff; font-weight: 700; font-size: 10px; text-transform: uppercase; letter-spacing: 0.14em; padding: 4px 8px; display: flex; align-items: center; gap: 6px; }
  .tk-circ { flex: 0 0 18px; width: 18px; height: 18px; border-radius: 50%; background: var(--tk-cyan); color: #fff; display: inline-flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; }
  .tk-circ.n-navy { background: var(--tk-navy); } .tk-circ.n-mag { background: var(--tk-magenta); }
  .tk-circ.n-cyan { background: var(--tk-cyan); } .tk-circ.n-green { background: var(--tk-green); }
  .tk-imp-box { border: 1px solid #888; background: #fff; border-radius: 3px; padding: 6px 8px; font-size: 10px; }
  .tk-cs-col { border: 1px dashed var(--tk-grey); border-radius: 6px; padding: 6px; }
  .tk-cs-head { background: #3b3b3b; color: #fff; font-size: 10px; font-weight: 700; padding: 4px 8px; border-radius: 3px; display: flex; align-items: center; gap: 6px; }
  .tk-cs-badge { background: #000; border-radius: 50%; width: 18px; height: 18px; display: inline-flex; align-items: center; justify-content: center; font-size: 9px; flex: 0 0 18px; }
  .tk-cs-trigger { color: #C77700; font-size: 9.5px; font-weight: 700; text-decoration: underline; margin: 2px 0; }

  .tk-pyr {
    display: grid; grid-template-columns: 170px 1fr; gap: 14px; margin: 8px 0; align-items: center;
    @container (max-width: 560px) { grid-template-columns: 1fr; }
  }
  .tk-pyr-left { display: flex; flex-direction: column; align-items: center; gap: 2px; }
  .tk-pyr-layer {
    color: #fff; font-weight: 700; font-size: 9.5px; text-align: center; padding: 10px 4px 6px;
    &:nth-child(1) { width: 34%; clip-path: polygon(50% 0, 100% 100%, 0 100%); padding-top: 16px; }
    &:nth-child(2) { width: 56%; clip-path: polygon(19% 0, 81% 0, 100% 100%, 0 100%); }
    &:nth-child(3) { width: 78%; clip-path: polygon(14% 0, 86% 0, 100% 100%, 0 100%); }
    &:nth-child(4) { width: 100%; clip-path: polygon(11% 0, 89% 0, 100% 100%, 0 100%); }
  }
  .tk-pyr-navy { background: var(--tk-navy); } .tk-pyr-mag { background: var(--tk-magenta); }
  .tk-pyr-cyan { background: var(--tk-cyan); } .tk-pyr-green { background: var(--tk-green); }
  .tk-pyr-row { display: flex; gap: 8px; align-items: flex-start; margin: 6px 0; }
  .tk-pyr-obj { flex: 1; border: 1.5px solid #555; border-radius: 999px; padding: 5px 12px; font-size: 10.5px;
    strong { font-size: 11px; }
  }
  .tk-pyr-bucket { float: right; font-size: 8.5px; font-weight: 700; color: var(--tk-grey); letter-spacing: 0.08em; }
  .tk-pyr-measure { color: var(--muted); font-size: 10px; margin-top: 2px; }

  .tk-scroll { overflow-x: auto; }
  .tk-chsel {
    .tk-tick { text-align: center; width: 40px; }
    .tk-ch { font-weight: 600; }
    td.tk-t0, td.tk-t1, td.tk-t2 { color: #fff; font-weight: 700; opacity: 1; }
  }
  .tk-audit {
    th, td { min-width: 90px; }
    td:first-child, th:first-child { min-width: 68px; width: 68px; text-align: center; }
  }
  .tk-asset-thumb {
    display: inline-block; line-height: 0;
    img { width: 56px; height: 40px; object-fit: cover; border-radius: 4px; border: 1px solid var(--line); box-shadow: 0 1px 3px rgba(11,61,145,0.12); transition: transform .15s ease; }
    &:hover img { transform: scale(1.06); border-color: var(--indegene-cyan); }
  }
  .tk-raci { text-align: center; font-weight: 700; }
  .tk-raci-r { background: #DFF2E1; color: #1B7A34; } .tk-raci-a { background: #FFE6EF; color: var(--tk-magenta); }
  .tk-raci-c { background: #E4F3FC; color: #0B6FA8; } .tk-raci-i { background: #F1F1F1; color: #666; }

  .plan-agent-chip {
    display: inline-flex; align-items: center; gap: 3px; font-size: 9px; font-weight: 700;
    text-transform: uppercase; letter-spacing: .3px; color: #fff; background: linear-gradient(90deg,#5A32E0,#8A63F0);
    padding: 2px 8px; border-radius: 999px; white-space: nowrap;
    .material-symbols-outlined { font-size: 12px; }
  }
  .plan-agent-row { background: rgba(90,50,224,0.055);
    td { border-left: 0; }
    td:first-child { box-shadow: inset 3px 0 0 #5A32E0; }
  }
  .plan-agent-val { margin-top: 5px; font-size: 11.5px; line-height: 1.4;
    strong { color: #4a27c4; }
  }
  .plan-agent-legend { font-size: 10.5px; color: var(--muted); margin-top: 9px; display: flex; flex-wrap: wrap; align-items: center; gap: 6px; line-height: 1.5; }

  .bm-block { margin-bottom: 18px; }
  .bm-headline { font-size: 12.5px; color: var(--indegene-navy); background: rgba(90,50,224,0.06); border-left: 3px solid #5A32E0; border-radius: 0 8px 8px 0; padding: 8px 11px; margin-bottom: 10px; display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
  .bm-cols { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px;
    h4 { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .4px; color: var(--faint); margin: 0 0 6px; }
  }
  .bm-h4 { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .4px; color: var(--faint); margin: 12px 0 6px; }
  .bm-total td { background: rgba(11,61,145,0.05); }
  .conf-pill { font-size: 8.5px; font-weight: 700; text-transform: uppercase; letter-spacing: .3px; padding: 1px 7px; border-radius: 999px; white-space: nowrap; }
  .conf-cited { background: #DFF2E1; color: #1B7A34; }
  .conf-derived { background: #E4F3FC; color: #0B6FA8; }
  .conf-approx { background: #FFF3E0; color: #C77700; }
  .bm-aff { display: inline-flex; gap: 2px;
    i { width: 7px; height: 7px; border-radius: 50%; background: #dfe3e8; display: inline-block; }
    i.on { background: #5A32E0; }
  }
  .bm-gov li { margin-bottom: 5px; font-size: 11.5px; line-height: 1.45; }
  .bm-srcs { font-size: 11px; a { color: #0B6FA8; } }

  .tk-lib-block { margin-top: 14px; border-top: 2px dashed var(--line); padding-top: 12px; }
  .tk-lib-h { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--indegene-navy); margin: 0 0 3px;
    .material-symbols-outlined { font-size: 18px; color: var(--green); }
  }
  .tk-lib-sub { font-size: 11.5px; color: var(--muted); margin: 0 0 9px; }
  .tk-lib-grid, .tk-cf-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 9px; }
  .tk-lib-col, .tk-cf-col { background: rgba(11,61,145,0.03); border: 1px solid var(--line); border-radius: 9px; padding: 8px; }
  .tk-lib-col-head, .tk-cf-head { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .3px; color: var(--indegene-navy); margin-bottom: 7px; display: flex; align-items: center; gap: 5px; }
  .tk-cf-head .tk-cf-count { margin-left: auto; background: var(--indegene-navy); color: #fff; font-size: 10px; border-radius: 999px; padding: 0 7px; }
  .tk-claim {
    background: #fff; border: 1px solid var(--line); border-left: 3px solid var(--tk-cyan); border-radius: 6px; padding: 6px 8px; margin-bottom: 6px;
    &:has(.tk-claim-approved) { border-left-color: var(--green); }
    &:has(.tk-claim-review) { border-left-color: var(--amber); }
  }
  .tk-claim-txt { font-size: 11.5px; line-height: 1.35; color: #1a2330; }
  .tk-claim-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 5px; margin-top: 5px; }
  .tk-claim-none { color: var(--muted); font-size: 11px; border-left-color: #ccc; }
  .tk-claim-badge { font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: .3px; padding: 1px 6px; border-radius: 999px; }
  .tk-claim-approved { background: #DFF2E1; color: #1B7A34; border-left-color: var(--green); }
  .tk-claim-review { background: #FFF3E0; color: var(--amber); }
  .tk-claim-draft { background: #EEF0F3; color: #667; }
  .tk-claim-mat { font-size: 9.5px; font-family: ui-monospace, monospace; color: #667; background: #f4f6f9; padding: 1px 5px; border-radius: 4px; }
  .tk-ref-chip { display: inline-flex; align-items: center; gap: 2px; font-size: 9.5px; font-weight: 600; color: #0B6FA8; background: #E4F3FC; padding: 1px 6px; border-radius: 999px; text-decoration: none;
    .material-symbols-outlined { font-size: 12px; }
  }
  .tk-lib-empty { font-size: 12px; color: var(--muted); background: #fff8e6; border: 1px solid #f0e0a8; border-radius: 8px; padding: 9px 11px; margin-top: 12px; }
  .tk-cf-asset { display: flex; align-items: center; gap: 6px; background: #fff; border: 1px solid var(--line); border-radius: 6px; padding: 5px 7px; margin-bottom: 5px; }
  .tk-cf-fmt { font-size: 9px; font-weight: 700; text-transform: uppercase; color: #fff; background: var(--tk-cyan); padding: 1px 5px; border-radius: 4px; }
  .tk-cf-title { font-size: 11px; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .tk-cf-badge { font-size: 9px; color: var(--muted); }

  /* Brand intelligence kit (Brand foundation, concepts shelf, guardrails, signals) */
  .bk-src-chip { display: inline-flex; align-items: center; font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; color: #fff; background: linear-gradient(90deg,#1A1F6E,#3454C4); border-radius: 999px; padding: 2px 8px; margin-left: 6px; vertical-align: 2px; }
  .bk-core { background: linear-gradient(120deg,#1A1F6E,#2A2F8E); color: #fff; border-radius: 12px; padding: 16px 18px; margin: 4px 0 12px; }
  .bk-tagline { font-size: 19px; font-weight: 800; letter-spacing: .01em; }
  .bk-claim { font-size: 13px; opacity: .92; margin-top: 3px; }
  .bk-company { font-size: 10.5px; opacity: .66; margin-top: 8px; }
  .bk-pillars { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 9px; margin-bottom: 12px; }
  .bk-pillar { border: 1px solid var(--line); border-left: 3px solid #F07055; border-radius: 9px; padding: 9px 11px; background: var(--glass-strong); }
  .bk-pillar-name { font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: .05em; color: #F07055; }
  .bk-pillar-claim { font-size: 12.5px; font-weight: 600; color: var(--text); margin: 3px 0; }
  .bk-pillar-evid { font-size: 10.5px; color: var(--muted); line-height: 1.4; }
  .bk-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 8px; margin-bottom: 8px; }
  .bk-stat { text-align: center; border: 1px solid var(--line); border-radius: 9px; padding: 9px 6px; background: var(--glass-strong); }
  .bk-stat-v { font-size: 17px; font-weight: 800; color: #1A1F6E; }
  .bk-stat-k { font-size: 10px; color: var(--muted); margin-top: 2px; }
  .bk-stat-s { font-size: 9px; color: var(--faint); text-transform: uppercase; letter-spacing: .03em; margin-top: 3px; }
  .bk-label { font-size: 11.5px; color: var(--muted); line-height: 1.55; border-left: 3px solid var(--line); padding-left: 10px; }
  .bk-tones { display: flex; flex-wrap: wrap; gap: 6px; margin: 4px 0 10px; }
  .bk-tone { font-size: 11px; font-weight: 600; color: #1A1F6E; background: rgba(26,31,110,0.08); border-radius: 999px; padding: 4px 11px; }
  .bk-ccs { display: flex; flex-wrap: wrap; gap: 7px; margin-bottom: 10px; }
  .bk-cc { flex: 1; min-width: 88px; text-align: center; border: 1px solid var(--line); border-radius: 9px; padding: 8px 4px; background: var(--glass-strong); }
  .bk-cc-v { font-size: 14px; font-weight: 800; color: var(--text); }
  .bk-cc-k { font-size: 9.5px; color: var(--faint); text-transform: uppercase; letter-spacing: .03em; margin-top: 2px; }
  .bk-cc-hero { border-color: #3EC9A7; background: rgba(62,201,167,0.10);
    .bk-cc-v { color: #0d8a6a; }
  }
  .bk-comps { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 8px; margin-bottom: 10px; }
  .bk-comp { border: 1px solid var(--line); border-radius: 9px; padding: 9px 11px; background: var(--glass-strong); }
  .bk-comp-threat { font-size: 9px; font-weight: 800; text-transform: uppercase; letter-spacing: .05em; color: #a83232; }
  .bk-comp-name { font-size: 13px; font-weight: 700; color: var(--text); margin: 2px 0; }
  .bk-comp-d { font-size: 10.5px; color: var(--muted); line-height: 1.45; }
  .bk-sigs { display: flex; flex-direction: column; gap: 7px; margin-bottom: 10px; }
  .bk-sig { display: flex; gap: 10px; align-items: flex-start; border: 1px solid var(--line); border-radius: 9px; padding: 8px 10px; background: var(--glass-strong); }
  .bk-sig-kind { flex: 0 0 auto; font-size: 8.5px; font-weight: 800; text-transform: uppercase; letter-spacing: .04em; border-radius: 5px; padding: 3px 7px; margin-top: 2px; }
  .bk-sev-high { background: rgba(217,75,75,.13); color: #a83232; }
  .bk-sev-medium { background: rgba(199,119,0,.13); color: #8a5500; }
  .bk-sev-low { background: rgba(11,61,145,.10); color: var(--indegene-navy); }
  .bk-sig-h { font-size: 12px; font-weight: 600; color: var(--text); }
  .bk-sig-d { font-size: 10.5px; color: var(--muted); line-height: 1.45; margin-top: 2px; }
  .bk-con-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 9px; margin-bottom: 10px; }
  .bk-con-card { border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px; background: var(--glass-strong); }
  .bk-con-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
  .bk-con-id { font-size: 9px; font-family: ui-monospace, monospace; color: var(--faint); }
  .bk-con-status { font-size: 8.5px; font-weight: 800; text-transform: uppercase; letter-spacing: .05em; border-radius: 5px; padding: 2px 7px; }
  .bk-con-active { background: rgba(62,201,167,.16); color: #0d8a6a; }
  .bk-con-legacy { background: rgba(107,114,128,.14); color: #555; }
  .bk-con-emerging { background: rgba(240,112,85,.15); color: #c04a2f; }
  .bk-con-name { font-size: 13px; font-weight: 700; color: #1A1F6E; }
  .bk-con-desc { font-size: 11px; color: var(--muted); line-height: 1.5; margin: 4px 0 6px; }
  .bk-con-tags { display: flex; flex-wrap: wrap; gap: 4px; }
  .bk-con-tag { font-size: 9px; color: var(--faint); border: 1px solid var(--line); border-radius: 999px; padding: 1px 7px; }
  .bk-guard-grid {
    display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 10px;
    @container (max-width: 560px) { grid-template-columns: 1fr; }
  }
  .bk-guard-col { border: 1px solid var(--line); border-radius: 10px; overflow: hidden; background: var(--glass-strong); }
  .bk-guard-head { font-size: 11px; font-weight: 800; letter-spacing: .05em; padding: 8px 12px; color: #fff; }
  .bk-guard-dos .bk-guard-head { background: #17A673; }
  .bk-guard-donts .bk-guard-head { background: #D6455B; }
  .bk-guard-cat { font-size: 9px; font-weight: 800; text-transform: uppercase; letter-spacing: .05em; color: var(--faint); padding: 7px 12px 2px; }
  .bk-guard-item { font-size: 11px; color: var(--text); line-height: 1.5; padding: 3px 12px 3px 12px; }
  .bk-swatches { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 8px; }
  .bk-swatch { display: flex; gap: 8px; align-items: center; font-size: 10.5px; color: var(--muted);
    i { width: 26px; height: 26px; border-radius: 7px; border: 1px solid var(--line); display: inline-block; }
    strong { display: block; font-size: 11px; color: var(--text); }
    span { display: block; font-size: 9.5px; }
  }

  /* Award-winning campaigns (precedent section) */
  .aw-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 11px; margin-top: 8px; }
  .aw-card { background: var(--glass-strong); backdrop-filter: var(--glass-blur); -webkit-backdrop-filter: var(--glass-blur); border: 1px solid var(--line); border-radius: 11px; padding: 11px 12px; box-shadow: var(--shadow-raised-sm); }
  .aw-top { display: flex; align-items: center; justify-content: space-between; gap: 6px; margin-bottom: 6px; }
  .aw-badge { display: inline-flex; align-items: center; gap: 4px; font-size: 10px; font-weight: 700; color: #fff; padding: 2px 8px; border-radius: 999px;
    .material-symbols-outlined { font-size: 13px; }
  }
  .aw-grand { background: linear-gradient(90deg,#B8860B,#E6B325); } .aw-gold { background: #C79200; }
  .aw-silver { background: #8A8D93; } .aw-bronze { background: #A6702E; } .aw-finalist { background: #5A6B8C; }
  .aw-match { font-size: 9.5px; font-weight: 600; color: var(--indegene-navy); background: rgba(11,61,145,.08); padding: 1px 7px; border-radius: 999px; }
  .aw-title { font-size: 13px; font-weight: 700; color: var(--indegene-navy); line-height: 1.25; }
  .aw-meta { font-size: 10.5px; color: var(--muted); margin: 2px 0 7px; }
  .aw-row { display: grid; grid-template-columns: 62px 1fr; gap: 7px; font-size: 11px; line-height: 1.35; margin-bottom: 5px;
    .aw-k { font-weight: 700; color: var(--faint); text-transform: uppercase; font-size: 9px; letter-spacing: .3px; padding-top: 1px; }
  }
  .aw-srcs { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
  .aw-src { display: inline-flex; align-items: center; gap: 2px; font-size: 9.5px; color: #0B6FA8; text-decoration: none;
    .material-symbols-outlined { font-size: 12px; }
  }

  /* Manual inline editing is a separate feature (not wired in this port) --
     keep the base rule inert so any stray contenteditable markup doesn't look broken. */
  [contenteditable="true"] { cursor: text; }
}
`;
