import type { SegEvent, SegItem, SegState } from "./api";

/** Applies one streamed step event to the session state the way the server applied it to its
 *  working copy, so the conversation on screen matches what the step will commit. The step's
 *  final `done` event then replaces the state with the committed one. Pure: no mutation. */
export function applyEvent(state: SegState, ev: SegEvent): SegState {
  const mapItem = (id: string, fn: (it: SegItem) => SegItem): SegState =>
    ({ ...state, items: state.items.map((it) => (it.id === id ? fn(it) : it)) });

  switch (ev.type) {
    case "item":
      return state.items.some((it) => it.id === ev.item.id) ? state : { ...state, items: [...state.items, ev.item] };
    case "item_update":
      return state.items.some((it) => it.id === ev.item.id)
        ? mapItem(ev.item.id, () => ev.item)
        : { ...state, items: [...state.items, ev.item] };
    case "progress":
      return mapItem(ev.item_id, (it) => (it.kind === "progress" ? { ...it, steps: [...it.steps, ev.step] } : it));
    default:
      return state;
  }
}
