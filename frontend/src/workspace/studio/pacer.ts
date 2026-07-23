/**
 * Pacer — the human-rhythm playback queue (design rule 5).
 *
 * SSE events arrive in bursts; the pacer replays them at a conversational pace:
 *  - chat: the author's typing indicator shows for min(400 + 28·len, 2500) ms
 *  - banter replies get extra 900–1600 ms jitter after their target is visible
 *  - non-chat events keep a 500 ms floor so the assembly reads as deliberate
 *  - skip() flushes everything instantly (also the reduced-motion default)
 *  - after each section lands (phase_done), the pacer PAUSES and waits for an
 *    explicit resume() -- sections no longer auto-advance one into the next.
 *    skip() still flushes past any pending pause, for the "Skip ahead" escape hatch.
 */
import type { StudioEvent } from "./studioTypes";

const REDUCED = typeof window !== "undefined" &&
  window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

export class Pacer {
  private queue: StudioEvent[] = [];
  private running = false;
  private skipping = REDUCED;
  private disposed = false;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private paused = false;

  constructor(
    private apply: (ev: StudioEvent) => void,
    private setTyping: (author: string | null) => void,
    private setAwaitingContinue: (awaiting: boolean) => void = () => {},
  ) {}

  enqueue(ev: StudioEvent) {
    this.queue.push(ev);
    if (!this.running && !this.paused) void this.drain();
  }

  /** Called by the "Continue to next section" button. */
  resume() {
    if (!this.paused) return;
    this.paused = false;
    this.setAwaitingContinue(false);
    if (!this.running) void this.drain();
  }

  /** Flush everything immediately (skip-ahead control / reduced motion). */
  skip() {
    this.skipping = true;
    this.paused = false;
    this.setAwaitingContinue(false);
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    this.setTyping(null);
    while (this.queue.length) this.apply(this.queue.shift()!);
    this.running = false;
  }

  dispose() {
    this.disposed = true;
    if (this.timer) clearTimeout(this.timer);
    this.queue = [];
    this.setTyping(null);
  }

  private wait(ms: number) {
    return new Promise<void>((resolve) => {
      this.timer = setTimeout(resolve, ms);
    });
  }

  private async drain() {
    this.running = true;
    while (this.queue.length && !this.disposed) {
      if (this.skipping) {
        this.skip();
        return;
      }
      const ev = this.queue.shift()!;
      if (ev.type === "chat") {
        const base = Math.min(400 + 28 * ev.text.length, 2500);
        const jitter = ev.kind === "banter" ? 900 + Math.random() * 700 : 0;
        this.setTyping(ev.author);
        await this.wait(base + jitter);
        this.setTyping(null);
      } else if (ev.type === "ask") {
        // The ask is itself a chat moment from the section's owner.
        this.setTyping("ask");
        await this.wait(Math.min(400 + 20 * ev.text.length, 2200));
        this.setTyping(null);
      } else {
        await this.wait(500);
      }
      if (this.disposed) return;
      this.apply(ev);
      if (ev.type === "phase_done" && !this.skipping) {
        this.paused = true;
        this.setAwaitingContinue(true);
        this.running = false;
        return;
      }
    }
    this.running = false;
  }
}
