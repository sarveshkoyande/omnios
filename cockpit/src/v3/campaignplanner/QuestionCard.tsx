import { useState } from "react";
import { Icon } from "../../components/Icon";
import type { CCQuestion } from "./api";

/** Camille's clarification card (LLMQuestionCard): up to three questions from the Campaign
 *  Consultant, each with context-specific options (one recommended) and a write-in. A question
 *  with no options is answered in the user's own words. The answers go back as
 *  "Q: ...\nA: ..." blocks, exactly as Camille sent them. */
export function QuestionCard({ questions, answered, disabled, onSubmit }: {
  questions: CCQuestion[];
  answered: string | null;
  disabled: boolean;
  onSubmit: (formatted: string) => void;
}) {
  // The recommended option is pre-selected, so what is submitted by default is visible.
  const [picked, setPicked] = useState<Record<number, number>>(() =>
    Object.fromEntries(questions
      .map((q, i): [number, number] => [i, q.options.findIndex((o) => o.recommended)])
      .filter(([, j]) => j >= 0)));
  const [writeIns, setWriteIns] = useState<Record<number, string>>({});

  if (answered !== null) {
    return (
      <div className="v3-cc-card done">
        <div className="v3-cc-card-head">
          <span className="v3-cc-card-icon"><Icon name="check" size={14} /></span>
          <div><b>Campaign clarifications answered</b><span>{questions.length} question{questions.length === 1 ? "" : "s"}</span></div>
        </div>
      </div>
    );
  }

  const submit = () => {
    const text = questions.map((q, i) => {
      const own = (writeIns[i] ?? "").trim();
      let answer: string;
      if (own) answer = own;
      else if (picked[i] !== undefined && q.options[picked[i]]) {
        const o = q.options[picked[i]];
        answer = o.description ? `${o.label}: ${o.description}` : o.label;
      } else if (q.options.length) {
        const o = q.options.find((x) => x.recommended) ?? q.options[0];
        answer = o.description ? `${o.label}: ${o.description}` : o.label;
      } else answer = "Not specified — use best practice defaults";
      return `Q: ${q.question}\nA: ${answer}`;
    }).join("\n\n");
    onSubmit(text);
  };

  return (
    <form className="v3-cc-card v3-cc-questions" onSubmit={(e) => { e.preventDefault(); if (!disabled) submit(); }}>
      <div className="v3-cc-card-head">
        <span className="v3-cc-card-icon"><Icon name="sparkles" size={14} /></span>
        <div>
          <b>Campaign clarifications needed</b>
          <span>Select an option or type a custom answer so the agent can design the right journey.</span>
        </div>
      </div>
      {questions.map((q, i) => (
        <fieldset key={i} className="v3-cc-q" disabled={disabled}>
          <legend><span className="v3-cc-q-num">{i + 1}</span>{q.question}</legend>
          {q.options.map((o, j) => {
            const on = picked[i] === j && !(writeIns[i] ?? "").trim();
            return (
              <button key={j} type="button" className={`v3-cc-opt ${on ? "on" : ""}`} aria-pressed={on}
                onClick={() => { setPicked((p) => ({ ...p, [i]: j })); setWriteIns((w) => ({ ...w, [i]: "" })); }}>
                <span className="v3-cc-opt-radio" aria-hidden />
                <span className="v3-cc-opt-text">
                  <b>{o.label}{o.recommended && <em className="v3-cc-badge">Recommended</em>}</b>
                  {o.description && <span>{o.description}</span>}
                </span>
              </button>
            );
          })}
          <input className="v3-cc-input" value={writeIns[i] ?? ""}
            placeholder={q.options.length ? "Or type a custom preference here…" : "Type your answer here…"}
            onChange={(e) => setWriteIns((w) => ({ ...w, [i]: e.target.value }))} />
        </fieldset>
      ))}
      <div className="v3-cc-card-actions">
        <button type="submit" className="v3-cc-btn primary" disabled={disabled}>Submit clarifications &amp; continue</button>
      </div>
    </form>
  );
}
