import { useState } from "react";
import { Icon } from "../../components/Icon";
import { Rich } from "../campaignplanner/Rich";
import type { SegItem } from "./api";

type Item<K extends SegItem["kind"]> = Extract<SegItem, { kind: K }>;

const fmt = (n: number) => n.toLocaleString();

/** The agent's thinking steps, the last one live (as the Campaign Planner shows them). */
function ProgressCard({ item, live }: { item: Item<"progress">; live: boolean }) {
  const [open, setOpen] = useState(false);
  const running = live && item.status === "running";
  const last = item.steps[item.steps.length - 1];
  if (!running) {
    return (
      <div className="v3-cc-progress-done">
        <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
          <Icon name="check" size={12} /> <span>{last?.details ?? "Done"}</span>
          {item.steps.length > 1 && <Icon name="chevronDown" size={11} />}
        </button>
        {open && <ul>{item.steps.map((s, i) => <li key={i}><b>{s.title}</b> {s.details}</li>)}</ul>}
      </div>
    );
  }
  return (
    <div className="v3-cc-card v3-cc-progress">
      {item.steps.map((s, i) => (
        <div key={i} className={`v3-cc-progress-step ${i === item.steps.length - 1 ? "active" : ""}`}>
          <span className="v3-cc-progress-mark">{i === item.steps.length - 1 ? <span className="v3-cc-spinner" /> : <Icon name="check" size={11} />}</span>
          <div><b>{s.title}</b><span>{s.details}</span></div>
        </div>
      ))}
      {!item.steps.length && <div className="v3-ask-thinking"><span /><span /><span /></div>}
    </div>
  );
}

/** Camille's consent follow-up: pick one or more email consent statuses, or skip the filter. */
function ConsentCard({ item, disabled, onConfirm }: { item: Item<"consent">; disabled: boolean; onConfirm: (values: string[]) => void }) {
  const [picked, setPicked] = useState<string[]>([]);
  const answered = item.answered !== null;
  const shown = answered ? item.answered ?? [] : picked;
  const toggle = (v: string) => setPicked((p) => (p.includes(v) ? p.filter((x) => x !== v) : [...p, v]));
  return (
    <div className={`v3-cc-card v3-seg-consent ${answered || item.closed ? "done" : ""}`}>
      <div className="v3-cc-card-head">
        <span className="v3-cc-card-icon"><Icon name={answered ? "check" : "target"} size={14} /></span>
        <div><b>Email Consent Status</b><span>{item.text}</span></div>
      </div>
      <div className="v3-seg-chips" role="group" aria-label="Email consent status">
        {item.options.map((v) => {
          const on = shown.includes(v);
          return (
            <button key={v} type="button" className={`v3-seg-chip ${on ? "on" : ""}`} aria-pressed={on}
              disabled={answered || item.closed || disabled} onClick={() => toggle(v)}>
              <span className="v3-seg-check" aria-hidden>{on ? <Icon name="check" size={10} /> : null}</span>{v}
            </button>
          );
        })}
      </div>
      {answered ? (
        <p className="v3-seg-answered">{shown.length ? `Selected: ${shown.join(", ")}` : "Skipped — no consent filter applied"}</p>
      ) : item.closed ? (
        <p className="v3-seg-answered">Discarded.</p>
      ) : (
        <div className="v3-cc-card-actions">
          <button type="button" className="v3-cc-btn" disabled={disabled} onClick={() => onConfirm([])}>Skip — No consent filter</button>
          <button type="button" className="v3-cc-btn primary" disabled={disabled || !picked.length} onClick={() => onConfirm(picked)}>
            <Icon name="arrowRight" size={13} /> Confirm selection{picked.length ? ` (${picked.length})` : ""}
          </button>
        </div>
      )}
    </div>
  );
}

/** Camille's SQL card: the generated query with its name, explanation and description. */
function SqlCard({ item }: { item: Item<"sql"> }) {
  return (
    <div className="v3-cc-card v3-seg-sql">
      <div className="v3-seg-sql-head">
        <span className="v3-cc-badge">Generated SQL</span>
        <b>{item.segmentName}</b>
        {item.source === "rules" && <em className="v3-cc-src rules" title="Built by rules: the AI model wasn't available">Rules</em>}
      </div>
      {item.explanation && <p className="v3-seg-text">{item.explanation}</p>}
      <pre className="v3-cc-code v3-seg-code"><code>{item.sql}</code></pre>
      {item.segmentDescription && <p className="v3-seg-desc">{item.segmentDescription}</p>}
      {item.healed.length > 0 && (
        <p className="v3-seg-fix"><Icon name="refresh" size={11} /> Fixed by the Tester Agent: {item.healed.join(" · ")}</p>
      )}
      {(item.warnings ?? []).map((w, i) => <p key={i} className="v3-cc-banner warn"><Icon name="alertTriangle" size={12} /> <span>{w}</span></p>)}
      {item.note && <p className="v3-cc-banner warn">{item.note}</p>}
    </div>
  );
}

/** Camille's naming question (agent-question card). */
function NameCard({ item }: { item: Item<"name"> }) {
  return (
    <div className={`v3-cc-agent-msg ${item.reason ? "v3-seg-warn-msg" : ""}`}>
      <span className="v3-cc-agent-avatar" aria-hidden>AI</span>
      <div className="v3-seg-name">
        <Rich text={item.text} />
        {item.answered !== null ? <span className="v3-seg-answered">Named: {item.answered}</span>
          : item.closed ? <span className="v3-seg-answered">Discarded.</span> : null}
      </div>
    </div>
  );
}

/** Camille's record-count confirmation (count-confirm-card). */
function CountCard({ item, disabled, onCreate, onDiscard }: {
  item: Item<"count">; disabled: boolean; onCreate: () => void; onDiscard: () => void;
}) {
  const warn = item.status !== "ok";
  const message = item.status === "ok"
    ? `This segment currently contains ${fmt(item.count ?? 0)} records. Do you want to proceed and create the segment?`
    : item.status === "zero"
      ? (item.note
        ? "This segment has 0 records, and the reason below means it will stay empty until the SQL changes. Do you still want to create it?"
        : "Currently, this segment will have 0 records, but in the future, data can populate under this segment. Do you want to create the segment?")
      : item.status === "unavailable"
        ? "Data Cloud isn't connected on this server, so the segment can't be sized or created here. Copy the SQL from the Segment panel to create it in Data Cloud yourself."
        : "Unable to estimate record count for this segment. Do you want to proceed and create it anyway?";
  const answered = item.answered !== null;
  return (
    <div className={`v3-cc-card v3-seg-count ${warn ? "warn" : ""} ${answered ? "done" : ""}`}>
      <div className="v3-cc-card-head">
        <span className={`v3-cc-card-icon ${warn ? "warn" : ""}`}><Icon name={warn ? "alertTriangle" : "target"} size={14} /></span>
        <div><b>Segment Record Count</b><span>{message}</span></div>
      </div>
      {item.note && (item.status === "unknown" || item.status === "zero") && <p className="v3-seg-note">{item.note}</p>}
      {answered ? (
        <p className="v3-seg-answered">{item.answered?.proceed ? "Confirmed." : "Cancelled."}</p>
      ) : (
        <div className="v3-cc-card-actions">
          {item.status === "unavailable" ? (
            <button type="button" className="v3-cc-btn" disabled={disabled} onClick={onDiscard}>Done</button>
          ) : (
            <>
              <button type="button" className="v3-cc-btn" disabled={disabled} onClick={onDiscard}>No</button>
              <button type="button" className="v3-cc-btn primary" disabled={disabled} onClick={onCreate}><Icon name="check" size={13} /> Yes</button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

/** Camille's segment-success card. */
function SuccessCard({ item }: { item: Item<"success"> }) {
  return (
    <div className="v3-cc-card v3-seg-success">
      <div className="v3-cc-card-head">
        <span className="v3-cc-card-icon ok"><Icon name="check" size={14} /></span>
        <div><b>Segment Created Successfully</b><span>In Salesforce Data Cloud</span></div>
      </div>
      <dl className="v3-seg-rows">
        <dt>Name</dt><dd>{item.segmentName}</dd>
        <dt>ID</dt><dd className="mono">{item.segmentId}</dd>
        <dt>Published</dt><dd>{item.published ? "Yes" : `No${item.publishError ? ` (${item.publishError})` : ""}`}</dd>
        {item.count !== null && <><dt>Records</dt><dd>{fmt(item.count)} when created</dd></>}
      </dl>
      {item.segmentUrl && (
        <a className="v3-cc-btn" href={item.segmentUrl} target="_blank" rel="noopener noreferrer">
          <Icon name="link" size={13} /> View Segment in Salesforce
        </a>
      )}
      <p className="v3-seg-text muted">You can create another segment by typing a new query below.</p>
    </div>
  );
}

export function SegConversation({ items, liveIds, busy, onConsent, onCreate, onDiscard }: {
  items: SegItem[];
  liveIds: Set<string>;
  busy: boolean;
  onConsent: (values: string[]) => void;
  onCreate: () => void;
  onDiscard: () => void;
}) {
  return (
    <div className="v3-cc-thread" aria-live="polite">
      {items.map((it) => {
        switch (it.kind) {
          case "user":
            return <div key={it.id} className="v3-cc-user">{it.text}</div>;
          case "progress":
            return <ProgressCard key={it.id} item={it} live={liveIds.has(it.id)} />;
          case "consent":
            return <ConsentCard key={it.id} item={it} disabled={busy} onConfirm={onConsent} />;
          case "sql":
            return <SqlCard key={it.id} item={it} />;
          case "name":
            return <NameCard key={it.id} item={it} />;
          case "count":
            return <CountCard key={it.id} item={it} disabled={busy} onCreate={onCreate} onDiscard={onDiscard} />;
          case "success":
            return <SuccessCard key={it.id} item={it} />;
          default:
            return null;
        }
      })}
    </div>
  );
}
