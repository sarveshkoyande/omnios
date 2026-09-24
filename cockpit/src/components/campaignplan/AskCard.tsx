import { useState } from "react";
import type { StudioAsk } from "@omni-frontend/workspace/studio/studioTypes";
import { Md } from "./md";

/** One question the planning agent needs answered before it drafts the section: options with
 *  the agent's recommendation marked, optional multi-select and free text. */
export function AskCard({ ask, answered, onAnswer }: {
  ask: StudioAsk;
  answered: string | null;
  onAnswer: (value: string) => void;
}) {
  const initial = ask.multi_select ? (ask.preselected?.length ? ask.preselected : [ask.recommendation.label]) : [];
  const [picked, setPicked] = useState<string[]>(initial);
  const [free, setFree] = useState("");
  const locked = answered !== null;

  const toggle = (label: string) =>
    setPicked((p) => (p.includes(label) ? p.filter((x) => x !== label) : [...p, label]));

  return (
    <div className={`cp-ask ${locked ? "is-answered" : ""}`}>
      <div className="cp-ask-q"><Md text={ask.text} /></div>
      {ask.why && <div className="cp-ask-why"><Md text={ask.why} /></div>}
      {ask.evidence_note && <div className="cp-ask-why">{ask.evidence_note}</div>}
      <div className="cp-ask-options">
        {ask.options.map((o) => {
          const recommended = o.label === ask.recommendation.label;
          const chosen = locked ? answered!.split(/\s*[,;]\s*/).includes(o.label) || answered === o.label : picked.includes(o.label);
          return (
            <button key={o.label} type="button" disabled={locked}
              className={`cp-ask-option ${chosen ? "is-chosen" : ""} ${recommended ? "is-recommended" : ""}`}
              onClick={() => (ask.multi_select ? toggle(o.label) : onAnswer(o.label))}>
              <span className="cp-ask-option-label">
                {o.label}
                {recommended && <span className="cp-ask-rec">Recommended</span>}
              </span>
              {(o.size || o.criteria) && <span className="cp-ask-option-meta">{[o.size, o.criteria].filter(Boolean).join(" · ")}</span>}
              {o.distribution && (
                <span className="cp-ask-option-meta">{o.distribution.map((d) => `${d.channel} ${d.pct}%`).join(" · ")}</span>
              )}
            </button>
          );
        })}
      </div>
      {!locked && ask.recommendation_reason && <div className="cp-ask-why">Why the recommendation: <Md text={ask.recommendation_reason} /></div>}
      {!locked && ask.multi_select && (
        <button type="button" className="jc-btn jc-btn-keep" disabled={!picked.length} onClick={() => onAnswer(picked.join(", "))}>
          Use {picked.length} {ask.select_noun ?? "option"}{picked.length === 1 ? "" : "s"}
        </button>
      )}
      {!locked && ask.free_text && (
        <form className="cp-ask-free" onSubmit={(e) => { e.preventDefault(); if (free.trim()) onAnswer(free.trim()); }}>
          <input className="jc-input" placeholder="Or answer in your own words" value={free} onChange={(e) => setFree(e.target.value)} />
          <button type="submit" className="jc-btn" disabled={!free.trim()}>Answer</button>
        </form>
      )}
      {locked && <div className="cp-ask-answered">Answered: <strong>{answered || "—"}</strong></div>}
    </div>
  );
}
