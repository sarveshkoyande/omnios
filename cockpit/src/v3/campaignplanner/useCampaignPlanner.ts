import { useCallback, useEffect, useRef, useState } from "react";
import { ccApi, sfApi, streamJob, type CCEvent, type CCSession, type JobStarted, type SalesforceStatus } from "./api";
import { applyEvent } from "./reducer";

export interface Scope { brand: string | null; planId: number | null; campaignId: number | null }

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

/** The Campaign Planner session for one brand + campaign, and the step running on it.
 *  A running step is followed through its event stream; after a reload the stream is replayed
 *  from its first event onto the saved state, so the page always shows where the step is. */
export function useCampaignPlanner() {
  const [session, setSession] = useState<CCSession | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [running, setRunning] = useState<{ jobId: string; kind: string } | null>(null);
  const [jobError, setJobError] = useState<string | null>(null);
  const [liveIds, setLiveIds] = useState<Set<string>>(() => new Set());
  const [liveMermaid, setLiveMermaid] = useState<string | null>(null);
  const [sf, setSf] = useState<SalesforceStatus | null>(null);
  const stream = useRef<AbortController | null>(null);
  const sidRef = useRef<string | null>(null);
  const runningRef = useRef(false);

  const stopStream = useCallback(() => {
    stream.current?.abort();
    stream.current = null;
  }, []);

  const settle = useCallback((next: CCSession | null) => {
    if (next) setSession(next);
    setRunning(null);
    runningRef.current = false;
    setLiveIds(new Set());
    setLiveMermaid(null);
  }, []);

  const attach = useCallback((sid: string, jobId: string, after: number, attempt = 0) => {
    stopStream();
    const ctrl = new AbortController();
    stream.current = ctrl;
    let seen = after;
    let finished = false;
    const onEvent = (ev: CCEvent) => {
      if (sidRef.current !== sid) return;
      seen = ev.seq;
      if (ev.type === "done") {
        finished = true;
        if (ev.status === "ok") setJobError(null);
        if (ev.session) settle(ev.session);
        else ccApi.get(sid).then(settle, () => settle(null));
        return;
      }
      if (ev.type === "error") { setJobError(ev.message); return; }
      if (ev.type === "item") setLiveIds((s) => new Set(s).add(ev.item.id));
      if (ev.type === "mermaid") setLiveMermaid(ev.mermaid);
      setSession((prev) => (prev && prev.id === sid ? { ...prev, state: applyEvent(prev.state, ev) } : prev));
    };
    const recover = () => {
      if (ctrl.signal.aborted || finished || sidRef.current !== sid) return;
      // The connection dropped mid-step: the step itself keeps running on the server.
      ccApi.get(sid).then((s) => {
        if (sidRef.current !== sid) return;
        if (s.job?.id === jobId && attempt < 30) {
          setTimeout(() => { if (sidRef.current === sid && runningRef.current) attach(sid, jobId, seen, attempt + 1); }, 1500);
        } else {
          settle(s);
        }
      }, () => { if (attempt < 30) setTimeout(() => attach(sid, jobId, seen, attempt + 1), 3000); });
    };
    streamJob(sid, jobId, after, onEvent, ctrl.signal).then(recover, recover);
  }, [settle, stopStream]);

  const adopt = useCallback((s: CCSession) => {
    stopStream();
    sidRef.current = s.id;
    setSession(s);
    setJobError(null);
    setLiveIds(new Set());
    setLiveMermaid(null);
    if (s.job) {
      setRunning({ jobId: s.job.id, kind: s.job.kind });
      runningRef.current = true;
      attach(s.id, s.job.id, 0);
    } else {
      setRunning(null);
      runningRef.current = false;
    }
  }, [attach, stopStream]);

  const load = useCallback((loader: () => Promise<CCSession>) => {
    setLoading(true);
    setLoadError(null);
    loader().then(adopt, (e) => { setLoadError(message(e)); setSession(null); sidRef.current = null; }).finally(() => setLoading(false));
  }, [adopt]);

  const openScope = useCallback((scope: Scope) => load(() => ccApi.open({ brand: scope.brand, plan_id: scope.planId, campaign_id: scope.campaignId })), [load]);

  const refreshSf = useCallback(() => { sfApi.status().then(setSf, () => setSf(null)); }, []);
  useEffect(() => { refreshSf(); }, [refreshSf]);
  useEffect(() => () => stopStream(), [stopStream]);

  /** Start a step; its events then stream in. Returns false when it couldn't start. */
  const start = useCallback(async (starter: (sid: string) => Promise<JobStarted>): Promise<boolean> => {
    const sid = sidRef.current;
    if (!sid || runningRef.current) return false;
    setJobError(null);
    runningRef.current = true;
    try {
      const { job_id, kind } = await starter(sid);
      setRunning({ jobId: job_id, kind });
      setLiveIds(new Set());
      attach(sid, job_id, 0);
      return true;
    } catch (e) {
      runningRef.current = false;
      setJobError(message(e));
      return false;
    }
  }, [attach]);

  const direct = useCallback(async (fn: (sid: string) => Promise<CCSession>) => {
    const sid = sidRef.current;
    if (!sid) return;
    setJobError(null);
    try { const s = await fn(sid); if (sidRef.current === sid) adopt(s); } catch (e) { setJobError(message(e)); }
  }, [adopt]);

  return {
    session, loading, loadError, running, jobError, liveIds, liveMermaid, sf,
    openScope, refreshSf,
    clearError: () => setJobError(null),
    analyze: (prompt: string, file: File | null, autoAssume: boolean) => start((sid) => ccApi.analyze(sid, prompt, file, autoAssume)),
    answer: (text: string) => start((sid) => ccApi.answers(sid, text)),
    acceptAssumptions: () => start((sid) => ccApi.assumptions(sid, "accept")),
    resolveAssumptions: (text: string) => start((sid) => ccApi.assumptions(sid, "resolve", text)),
    updateBriefing: (text: string) => start((sid) => ccApi.updateBriefing(sid, text)),
    buildBlueprint: (feedback?: string) => start((sid) => ccApi.blueprint(sid, feedback)),
    deploy: () => start((sid) => ccApi.deploy(sid)),
    cancel: () => direct((sid) => ccApi.cancel(sid)),
    reset: () => direct((sid) => ccApi.reset(sid)),
    restoreBriefing: (v: number) => direct((sid) => ccApi.restoreBriefing(sid, v)),
    rename: (title: string) => direct((sid) => ccApi.rename(sid, title)),
    disconnectSf: () => { sfApi.disconnect().then(setSf, () => undefined); },
  };
}
