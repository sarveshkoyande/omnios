import type { CCAgent, CCEvent, CCItem, CCState } from "./api";

/** Applies one streamed job event to the session state, the way the server applied it to its
 *  working copy -- so the conversation on screen matches what the job will commit. The job's
 *  final `done` event then replaces the state with the committed one. Pure: no mutation. */
export function applyEvent(state: CCState, ev: CCEvent): CCState {
  const mapItem = (id: string, fn: (it: CCItem) => CCItem): CCState =>
    ({ ...state, items: state.items.map((it) => (it.id === id ? fn(it) : it)) });

  switch (ev.type) {
    case "item": {
      if (state.items.some((it) => it.id === ev.item.id)) return state;
      const next = { ...state, items: [...state.items, ev.item] };
      // A question or assumption card arriving is the job moving the plan to that stage.
      if (ev.item.kind === "questions" && ev.item.answered === null) return { ...next, stage: "clarifying", questions: ev.item.questions };
      if (ev.item.kind === "assumptions" && ev.item.resolved === null) return { ...next, stage: "assumptions", assumptions: ev.item.assumptions };
      return next;
    }
    case "item_update":
      return state.items.some((it) => it.id === ev.item.id)
        ? mapItem(ev.item.id, () => ev.item)
        : { ...state, items: [...state.items, ev.item] };
    case "item_status":
      return mapItem(ev.item_id, (it) => (it.kind === "progress" || it.kind === "pipeline" ? { ...it, status: ev.status } : it));
    case "progress":
      return mapItem(ev.item_id, (it) => (it.kind === "progress" || it.kind === "pipeline" ? { ...it, steps: [...it.steps, ev.step] } : it));
    case "agent_start":
    case "agent_done":
      return mapItem(ev.item_id, (it) => {
        if (it.kind !== "pipeline") return it;
        const found = it.agents.find((a) => a.name === ev.agent.name);
        const merged: CCAgent = { ...ev.agent, reasoning: found?.reasoning ?? "" };
        return { ...it, agents: found ? it.agents.map((a) => (a.name === ev.agent.name ? merged : a)) : [...it.agents, merged] };
      });
    case "thought":
      return mapItem(ev.item_id, (it) => (it.kind !== "pipeline" ? it : {
        ...it, agents: it.agents.map((a) => (a.name === ev.agent ? { ...a, reasoning: (a.reasoning ?? "") + ev.text } : a)),
      }));
    case "briefing":
      // A changed brief after the journey exists keeps the journey (now flagged stale).
      return {
        ...state, briefing: ev.briefing, briefing_version: ev.version, briefing_source: ev.source, briefing_note: ev.note,
        stage: state.stage === "blueprint" ? "blueprint" : "briefing", blueprint_stale: Boolean(state.blueprint),
      };
    case "blueprint":
      return { ...state, blueprint: ev.blueprint, spec: ev.blueprint.spec, stage: "blueprint", blueprint_stale: false };
    case "deploy":
      return { ...state, deployment: ev.deployment };
    default:
      return state;
  }
}
