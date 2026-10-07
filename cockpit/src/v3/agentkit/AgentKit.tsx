import { useEffect, useRef, useState } from "react";
import { getBrandReadiness, type BrandReadiness } from "../../api";
import { Icon } from "../../components/Icon";
import "./agentkit.css";

/** Shared pieces for step-by-step agents (Brand Compass Agent, Signal Scout): the acknowledgement card the
 *  agent shows before it builds, the progress list (only finished steps + the current one), and the
 *  Live reasoning slide-in panel (same look as the Campaign Agent's). */

export type SkillStatus = "idle" | "running" | "done" | "error";
export interface AgentStep { id: string; name: string; skills: string[] }
export interface Ack {
  mode?: string; understood?: string; question?: string;
  have?: { what: string; detail?: string }[];
  missing?: { what: string; impact?: string }[];
  approach?: string[];
}
export interface ReasonEntry { id: string; title: string; status: SkillStatus; lines: string[]; error?: string }

export function AckCard({ ack, onConfirm, onEdit }: { ack: Ack; onConfirm: () => void; onEdit: () => void }) {
  return (
    <section className="v3-ak-ack">
      <div className="v3-ak-ack-head"><Icon name="sparkles" size={14} /><b>Here's what I've got</b></div>
      {ack.understood && <p>{ack.understood}</p>}
      {(ack.have ?? []).length > 0 && (
        <div className="v3-ak-list have">
          <em>Available</em>
          {ack.have!.map((h, i) => <div key={i}><Icon name="check" size={10} /><span><b>{h.what}</b>{h.detail ? ` — ${h.detail}` : ""}</span></div>)}
        </div>
      )}
      {(ack.missing ?? []).length > 0 && (
        <div className="v3-ak-list missing">
          <em>Not available</em>
          {ack.missing!.map((m, i) => <div key={i}><span className="v3-ak-x">–</span><span><b>{m.what}</b>{m.impact ? ` — ${m.impact}` : ""}</span></div>)}
        </div>
      )}
      {(ack.approach ?? []).length > 0 && (
        <div className="v3-ak-list">
          <em>How I'll build it</em>
          <ol>{ack.approach!.map((a, i) => <li key={i}>{a}</li>)}</ol>
        </div>
      )}
      {ack.question && <p className="v3-ak-q">{ack.question}</p>}
      <div className="v3-ak-ack-actions">
        <button type="button" className="v3-cc-btn primary" onClick={onConfirm}>Looks good, build it</button>
        <button type="button" className="v3-cc-btn" onClick={onEdit}>Let me add more</button>
      </div>
    </section>
  );
}

/** Finished steps as compact rows, the current step expanded with its sub-tasks so far; later steps hidden. */
export function StepProgress({ steps, skillNames, status, currentStep, done }: {
  steps: AgentStep[]; skillNames: Record<string, string>; status: Record<string, SkillStatus>;
  currentStep: number; done: boolean;
}) {
  return (
    <div className="v3-ak-progress">
      {steps.map((st, i) => {
        if (i > currentStep && !done) return null;
        const finished = done || i < currentStep;
        const failed = st.skills.filter((k) => status[k] === "error").length;
        if (finished) {
          return (
            <div key={st.id} className="v3-ak-row done">
              <span className="v3-ak-dot"><Icon name="check" size={9} /></span>
              <b>{st.name}</b>
              {failed > 0 && <small className="v3-ak-warn">{failed} part{failed > 1 ? "s" : ""} didn't finish</small>}
            </div>
          );
        }
        return (
          <div key={st.id} className="v3-ak-row current">
            <div className="v3-ak-row-head"><span className="v3-ak-dot"><span className="v3-cc-spinner small" /></span><b>{st.name}</b></div>
            <ul>
              {st.skills.filter((k) => (status[k] ?? "idle") !== "idle").map((k) => (
                <li key={k} className={status[k]}>
                  {status[k] === "running" ? <span className="v3-cc-spinner small" /> : status[k] === "done" ? <Icon name="check" size={9} /> : <span className="v3-ak-x">!</span>}
                  {skillNames[k] ?? k}{status[k] === "running" ? "…" : ""}
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}

export function ReasoningPanel({ entries, live, onClose }: { entries: ReasonEntry[]; live: boolean; onClose: () => void }) {
  const body = useRef<HTMLDivElement>(null);
  const total = entries.reduce((n, e) => n + e.lines.length + (e.status === "running" ? 1 : 0), 0);
  useEffect(() => { if (body.current) body.current.scrollTop = body.current.scrollHeight; }, [total]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <aside className="v3-refine v3-cc-reason" aria-label="Live reasoning">
      <div className="v3-refine-head">
        <b><Icon name="eye" size={14} /> Live reasoning{live && <span className="v3-cc-live-dot" />}</b>
        <button type="button" aria-label="Close" onClick={onClose}><Icon name="close" size={13} /></button>
      </div>
      <div className="v3-refine-body" ref={body}>
        {entries.length === 0 && <p className="v3-muted">The agent's reasoning appears here as it works.</p>}
        {entries.map((e) => (
          <div key={e.id} className="v3-cc-reason-card">
            <b>{e.title}</b>
            {e.status === "running" && <div className="v3-ask-thinking"><span /><span /><span /></div>}
            {e.lines.length > 0 && <ul className="v3-ak-lines">{e.lines.map((l, i) => <li key={i}>{l}</li>)}</ul>}
            {e.status === "error" && <p className="v3-cc-banner error">{e.error}</p>}
          </div>
        ))}
      </div>
    </aside>
  );
}

export function ReasoningButton({ live, onClick }: { live: boolean; onClick: () => void }) {
  return (
    <button type="button" className="v3-ak-reason-btn" onClick={onClick}>
      <Icon name="eye" size={13} /> Live reasoning{live && <span className="v3-cc-live-dot" />}
    </button>
  );
}

export const DOC_ACCEPT = ".pdf,.docx,.pptx,.txt,.md";

/** The glass drop zone every agent's intake uses: drag and drop the brand plan and other details
 *  (several files), plus a text box. `multiple={false}` for agents that read one document. */
export function GlassDrop({ files, setFiles, notes, setNotes, multiple = true, disabled, notesLabel, placeholder, hint,
  dropLabel = "Drag and drop the brand plan and other details", dropSub }: {
  files: File[]; setFiles: (f: File[]) => void; notes: string; setNotes: (v: string) => void;
  multiple?: boolean; disabled?: boolean; notesLabel: string; placeholder: string; hint?: string;
  dropLabel?: string; dropSub?: string;
}) {
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const add = (list: FileList | null) => {
    const picked = Array.from(list ?? []);
    if (!picked.length) return;
    setFiles(multiple ? [...files, ...picked.filter((f) => !files.some((x) => x.name === f.name))] : [picked[0]]);
  };
  return (
    <div className="v3-glass-intake">
      <div className={`v3-glass-drop ${drag ? "drag" : ""} ${disabled ? "off" : ""}`}
        onDragOver={(e) => { e.preventDefault(); if (!disabled) setDrag(true); }}
        onDragLeave={(e) => { e.preventDefault(); setDrag(false); }}
        onDrop={(e) => { e.preventDefault(); setDrag(false); if (!disabled) add(e.dataTransfer.files); }}
        onClick={() => !disabled && input.current?.click()} role="button" tabIndex={0}
        onKeyDown={(e) => { if (e.key === "Enter" && !disabled) input.current?.click(); }}>
        <span className="v3-glass-orb"><Icon name="document" size={22} /></span>
        <b>{dropLabel}</b>
        <span>{dropSub ?? (multiple ? "Briefs, research, notes" : "One document")} · PDF, DOCX, PPTX, TXT or MD · or <u>browse</u></span>
        <input ref={input} type="file" accept={DOC_ACCEPT} multiple={multiple} hidden
          onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
      </div>
      {files.length > 0 && (
        <div className="v3-glass-files">
          {files.map((f) => (
            <span key={f.name} className="v3-glass-chip"><Icon name="document" size={11} /> {f.name}
              <button type="button" aria-label={`Remove ${f.name}`} disabled={disabled} onClick={() => setFiles(files.filter((x) => x !== f))}><Icon name="close" size={10} /></button>
            </span>
          ))}
        </div>
      )}
      <label className="v3-glass-label">{notesLabel}</label>
      <textarea className="v3-glass-text" rows={5} value={notes} disabled={disabled} placeholder={placeholder} onChange={(e) => setNotes(e.target.value)} />
      {hint && <span className="v3-glass-hint">{hint}</span>}
    </div>
  );
}

const READY_SHORT: Record<string, string> = { brand_plan: "Plan", kit: "Kit", audiences: "Audiences", patient_flow: "Patient flow", compliance: "Compliance", client_data: "Client data" };

/** "Ready from Brand Compass" in one line: a status pill and a chip per source. Details are on hover; a missing
 *  source is a link to fix it. The brand plan is uploaded once, in the Brand Compass Agent. */
export function ReadyFromBrandIQ({ brand }: { brand: string; compact?: boolean }) {
  const [r, setR] = useState<BrandReadiness | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    setR(null); setFailed(false);
    getBrandReadiness(brand).then(setR).catch(() => setFailed(true));
  }, [brand]);
  if (failed) return null;
  return (
    <div className={`v3-ready ${r && !r.has_brand_plan ? "warn" : ""}`}>
      <span className="v3-ready-pill" title={r && !r.has_brand_plan ? "No brand plan in Brand Compass: drafts use the kit and public sources" : undefined}>
        {r ? (r.has_brand_plan ? <><Icon name="check" size={11} /> Ready from Brand Compass</> : "Brand Compass · no plan yet") : "Reading Brand Compass…"}
      </span>
      {r?.items.map((i) => {
        const chip = <><i className={`v3-ready-dot ${i.status}`} />{READY_SHORT[i.id] ?? i.label}</>;
        return i.fix && i.status !== "ok"
          ? <a key={i.id} className="v3-ready-chip" href={i.fix} title={`${i.detail} — click to fix`}>{chip}</a>
          : <span key={i.id} className="v3-ready-chip" title={i.detail}>{chip}</span>;
      })}
    </div>
  );
}

/** Option C: the command bar every agent opens with. One box: what you want (optional), the brand's Brand Compass
 *  as a chip (gaps on click), a paperclip for documents, and go. Leave it empty and press go. */
export function CommandBar({ brand, value, setValue, files, setFiles, onGo, busy, busyLabel, placeholder,
  multiple = true, attachLabel = "Attach documents", goLabel = "Start", disabled, hideBrandIQ, children }: {
  brand: string | null; value: string; setValue: (v: string) => void; files: File[]; setFiles: (f: File[]) => void;
  onGo: () => void; busy?: boolean; busyLabel?: string | null; placeholder: string; multiple?: boolean;
  attachLabel?: string; goLabel?: string; disabled?: boolean; hideBrandIQ?: boolean; children?: React.ReactNode;
}) {
  const [r, setR] = useState<BrandReadiness | null>(null);
  const [showGaps, setShowGaps] = useState(false);
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    setR(null);
    if (brand && !hideBrandIQ) getBrandReadiness(brand).then(setR).catch(() => setR(null));
  }, [brand, hideBrandIQ]);
  const gaps = (r?.items ?? []).filter((i) => i.status === "missing" || i.status === "partial");
  const add = (list: FileList | null) => {
    const picked = Array.from(list ?? []);
    if (picked.length) setFiles(multiple ? [...files, ...picked.filter((f) => !files.some((x) => x.name === f.name))] : [picked[0]]);
  };
  const go = () => { if (!busy && !disabled) onGo(); };
  return (
    <div className="v3-cmd-wrap">
      {children}
      <div className={`v3-cmd ${drag ? "drag" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={(e) => { e.preventDefault(); setDrag(false); }}
        onDrop={(e) => { e.preventDefault(); setDrag(false); if (!busy) add(e.dataTransfer.files); }}>
        <textarea rows={3} value={value} disabled={busy} placeholder={placeholder} onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); go(); } }} />
        {files.length > 0 && (
          <div className="v3-cmd-files">
            {files.map((f) => (
              <span key={f.name} className="v3-cmd-file"><Icon name="document" size={11} /> {f.name}
                <button type="button" aria-label={`Remove ${f.name}`} disabled={busy} onClick={() => setFiles(files.filter((x) => x !== f))}><Icon name="close" size={10} /></button>
              </span>
            ))}
          </div>
        )}
        <div className="v3-cmd-bar">
          {brand && !hideBrandIQ && (
            <button type="button" className={`v3-cmd-chip ${r && !r.has_brand_plan ? "warn" : ""}`} onClick={() => setShowGaps((v) => !v)}
              title={gaps.length ? gaps.map((g) => `${g.label}: ${g.detail}`).join("\n") : "Everything Brand Compass needs is loaded"}>
              {r ? <><Icon name="check" size={11} /> {brand} Brand Compass{gaps.length ? <em> · {gaps.length} gap{gaps.length > 1 ? "s" : ""}</em> : null}</> : `${brand} Brand Compass…`}
            </button>
          )}
          <button type="button" className="v3-cmd-icon" aria-label={attachLabel} title={attachLabel} disabled={busy} onClick={() => input.current?.click()}>
            <Icon name="paperclip" size={15} />
          </button>
          <input ref={input} type="file" accept={DOC_ACCEPT} multiple={multiple} hidden onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
          <span className="v3-cmd-space" />
          <button type="button" className="v3-cmd-go" disabled={busy || disabled} onClick={go}>
            {busy ? <><span className="v3-cc-spinner small" /> {busyLabel ?? "Working…"}</> : <>{goLabel} <Icon name="arrowRight" size={13} /></>}
          </button>
        </div>
      </div>
      {showGaps && gaps.length > 0 && (
        <div className="v3-cmd-gaps">
          {gaps.map((g) => <a key={g.id} href={g.fix ?? "#/v3/agent/brand-iq"}><i className={`v3-ready-dot ${g.status}`} /> {g.label} — fix in Brand Compass</a>)}
        </div>
      )}
    </div>
  );
}

/** The standard agent intake, now the command bar. */
export function ReadyIntake({ brand, startLabel, busyLabel, busy, onStart, files, setFiles, notes, setNotes, placeholder, children }: {
  brand: string; startLabel: string; busyLabel?: string | null; busy?: boolean; onStart: () => void;
  files: File[]; setFiles: (f: File[]) => void; notes: string; setNotes: (v: string) => void;
  addLabel?: string; notesLabel?: string; placeholder: string; dropLabel?: string; defaultOpen?: boolean;
  children?: React.ReactNode;
}) {
  return (
    <CommandBar brand={brand} value={notes} setValue={setNotes} files={files} setFiles={setFiles} onGo={onStart}
      busy={busy} busyLabel={busyLabel} placeholder={placeholder} goLabel={startLabel}>
      {children}
    </CommandBar>
  );
}

/** The chat box every planning agent keeps open: steer it in your own words at any point. The model reads
 *  the message (no keyword rules) and answers, redoes a step, jumps ahead or switches auto-run. */
export interface ChatMsg { role: "you" | "agent"; text: string; intent?: string; step?: string | null }
export function AgentChat({ messages, onSend, busy, placeholder, suggestions = [] }: {
  messages: ChatMsg[]; onSend: (text: string) => void; busy?: boolean; placeholder?: string; suggestions?: string[];
}) {
  const [text, setText] = useState("");
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ block: "nearest" }); }, [messages.length]);
  const send = (t: string) => { const v = t.trim(); if (!v || busy) return; onSend(v); setText(""); };
  return (
    <div className="v3-achat">
      {messages.length > 0 && (
        <div className="v3-achat-thread">
          {messages.map((m, i) => (
            <div key={i} className={`v3-achat-msg ${m.role}`}>
              {m.role === "agent" && <span className="v3-achat-av"><Icon name="sparkles" size={11} /></span>}
              <p>{m.text}</p>
            </div>
          ))}
          <div ref={end} />
        </div>
      )}
      {!messages.length && suggestions.length > 0 && (
        <div className="v3-achat-sugg">{suggestions.map((s) => <button key={s} type="button" disabled={busy} onClick={() => send(s)}>{s}</button>)}</div>
      )}
      <div className="v3-achat-box">
        <textarea rows={2} value={text} disabled={busy} placeholder={placeholder ?? "Tell the agent what to change, ask why, or say “run everything”…"}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(text); } }} />
        <button type="button" className="v3-achat-send" disabled={busy || !text.trim()} onClick={() => send(text)} aria-label="Send">
          {busy ? <span className="v3-cc-spinner small" /> : <Icon name="arrowRight" size={14} />}
        </button>
      </div>
    </div>
  );
}
