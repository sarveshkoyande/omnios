import { useEffect, useRef, useState } from "react";
import { planDocSkinCss } from "@omni-frontend/workspace/planDocSkinCss";
import type { TreeCampaign } from "../../types";
import { AskCard } from "./AskCard";
import { Md } from "./md";
import { useCampaignPlan } from "./useCampaignPlan";

// The plan document's own stylesheet (scoped to .plan-doc-skin), injected once.
function useDocSkin() {
  useEffect(() => {
    if (document.getElementById("cp-doc-skin")) return;
    const tag = document.createElement("style");
    tag.id = "cp-doc-skin";
    tag.textContent = planDocSkinCss;
    document.head.appendChild(tag);
  }, []);
}

const BRIEF_FIELDS: [string, string][] = [
  ["brand", "Brand"], ["therapy_area", "Therapy area"], ["indication", "Indication"], ["lifecycle_key", "Lifecycle"],
  ["audience", "Audience"], ["objective", "Objective"], ["geography", "Geography"], ["budget", "Budget"],
];

function briefValue(slots: Record<string, unknown>, key: string): string {
  const v = slots[key];
  if (key === "budget") return typeof v === "number" && v > 0 ? `$${v.toLocaleString()}` : "";
  return typeof v === "string" ? v : "";
}

/** The campaign's Campaign Plan, built in the Cockpit: brief, conversation with the planning
 *  agent, and the plan sections as they land. */
export function CampaignPlanPage({ campaign }: { campaign: TreeCampaign }) {
  useDocSkin();
  const plan = useCampaignPlan(campaign.project_id as string);
  const [text, setText] = useState("");
  const threadRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: "smooth" });
  }, [plan.items.length, plan.busy, plan.running]);

  if (plan.error) return <div className="hier-page"><div className="error-banner">Couldn't open this Campaign Plan: {plan.error}</div></div>;
  if (!plan.loaded) return <div className="loading">Opening the Campaign Plan&hellip;</div>;

  const slots = (plan.slots ?? {}) as unknown as Record<string, unknown>;
  const landed = plan.sections.length;
  const total = Math.max(plan.total, landed);
  const status = plan.pendingAsk ? "Waiting for your answer"
    : plan.running ? (plan.active ? `Working on section ${plan.active.num}: ${plan.active.title}` : "Building the plan…")
    : plan.done ? "Plan ready"
    : landed ? "Paused" : "Collecting the brief";
  const canType = !plan.busy && !plan.running;
  const pid = encodeURIComponent(campaign.project_id as string);

  return (
    <div className="cp-page">
      <div className="cp-head">
        <div>
          <div className="kit-update-eyebrow">Campaign Plan</div>
          <h1 className="kit-update-title">{campaign.name}</h1>
          <div className="cp-status" role="status">{status}</div>
        </div>
        {plan.hasResult && (
          <div className="hier-head-actions">
            <a className="jc-btn" href={`/api/projects/${pid}/export.docx`}>Download Word</a>
            <a className="jc-btn" href={`/api/projects/${pid}/export.pdf`}>Download PDF</a>
          </div>
        )}
      </div>

      <div className="cp-brief" aria-label="Brief">
        {BRIEF_FIELDS.map(([k, label]) => {
          const v = briefValue(slots, k);
          return (
            <span key={k} className={`cp-brief-chip ${v ? "" : "is-missing"}`}>
              <span className="cp-brief-label">{label}</span>{v || "Not given yet"}
            </span>
          );
        })}
      </div>
      {total > 0 && (
        <div className="cp-progress" aria-label={`${landed} of ${total} sections`}>
          <div className="cp-progress-bar" style={{ width: `${Math.round((landed / total) * 100)}%` }} />
          <span>{landed} of {total} sections</span>
        </div>
      )}

      <div className="cp-body">
        <section className="cp-doc jc-card" aria-label="Plan document">
          {plan.active && (
            <div className="cp-active">
              <div className="cp-active-title">Section {plan.active.num} · {plan.active.title}</div>
              <div className="cp-active-state">
                {plan.active.state === "ground" ? "Gathering evidence…" : plan.active.state === "ask" ? "Needs your answer in the conversation" : plan.active.note || "Drafting…"}
              </div>
              {plan.active.grounding.length > 0 && (
                <ul className="cp-grounding">
                  {plan.active.grounding.slice(0, 6).map((g, i) => (
                    <li key={i}><strong>{g.label}</strong> — {g.snippet} <span className="hier-hint">{g.source}</span></li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {plan.sections.length > 0 ? (
            <div className="plan-doc-skin cp-doc-skin">
              {[...plan.sections].sort((a, b) => a.num - b.num).map((s) => (
                <article key={s.section_id} className="cp-section" dangerouslySetInnerHTML={{ __html: s.html }} />
              ))}
            </div>
          ) : plan.planHtml ? (
            <div className="plan-doc-skin cp-doc-skin" dangerouslySetInnerHTML={{ __html: plan.planHtml }} />
          ) : !plan.active && (
            <div className="cp-empty">
              <p>The plan appears here section by section once the brief is complete.</p>
              <p className="hier-hint">Tell the planning agent about the campaign on the right: audience, objective, budget, channels.</p>
            </div>
          )}
        </section>

        <aside className="cp-chat" aria-label="Planning agent">
          <div className="cp-chat-head"><span className="agent-dock-avatar" aria-hidden>AI</span> Campaign planning agent</div>
          <div className="cp-thread" ref={threadRef} aria-live="polite">
            {plan.items.map((it) => {
              if (it.kind === "ask") {
                return <AskCard key={it.id} ask={it.ask} answered={it.answered} onAnswer={(v) => { void plan.answer(it.id, it.ask, v); }} />;
              }
              if (it.kind === "status") return <div key={it.id} className="cp-msg-status"><Md text={it.text} /></div>;
              return (
                <div key={it.id} className={`cp-msg cp-msg-${it.kind}`}>
                  <Md text={it.text} />
                  {it.kind === "agent" && it.clarify && (
                    <div className="cp-clarify">Question {it.clarify.group_index + 1} of {it.clarify.group_total}: {it.clarify.title}</div>
                  )}
                </div>
              );
            })}
            {(plan.busy || (plan.running && !plan.active)) && <div className="cp-msg-status">Thinking…</div>}
          </div>
          <form className="agent-dock-form cp-compose" onSubmit={(e) => { e.preventDefault(); if (text.trim()) { void plan.send(text); setText(""); } }}>
            <textarea className="jc-input agent-dock-input" rows={2} value={text} disabled={!canType}
              placeholder={plan.pendingAsk ? "Answer the question above, or type here" : plan.running ? "The agent is building the plan…" : "Tell the planning agent about this campaign"}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (text.trim() && canType) { void plan.send(text); setText(""); } } }} />
            <button type="submit" className="jc-btn jc-btn-keep" disabled={!canType || !text.trim()}>Send</button>
          </form>
        </aside>
      </div>
    </div>
  );
}
