import { useCallback, useEffect, useRef, useState } from "react";
import { segApi, streamJob, type Dataset, type JobStarted, type SegEvent, type SegSession } from "./api";
import { applyEvent } from "./reducer";

export interface Scope { brand: string | null; planId: number | null; campaignId: number | null }

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

/** The Segmentation Planner session for one brand + campaign, and the step running on it.
 *  A running step is followed through its event stream; after a reload the stream is replayed
 *  from its first event onto the saved state, so the page always shows where the step is. */
export function useSegmentationPlanner() {
  const [session, setSession] = useState<SegSession | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [running, setRunning] = useState<{ jobId: string; kind: string } | null>(null);
  const [jobError, setJobError] = useState<string | null>(null);
  const [liveIds, setLiveIds] = useState<Set<string>>(() => new Set());
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [datasetBusy, setDatasetBusy] = useState(false);
  const stream = useRef<AbortController | null>(null);
  const sidRef = useRef<string | null>(null);
  const runningRef = useRef(false);

  const stopStream = useCallback(() => {
    stream.current?.abort();
    stream.current = null;
  }, []);

  const settle = useCallback((next: SegSession | null) => {
    if (next) setSession(next);
    setRunning(null);
    runningRef.current = false;
    setLiveIds(new Set());
  }, []);

  const attach = useCallback((sid: string, jobId: string, after: number, attempt = 0) => {
    stopStream();
    const ctrl = new AbortController();
    stream.current = ctrl;
    let seen = after;
    let finished = false;
    const onEvent = (ev: SegEvent) => {
      if (sidRef.current !== sid) return;
      seen = ev.seq;
      if (ev.type === "done") {
        finished = true;
        if (ev.status === "ok") setJobError(null);
        if (ev.session) settle(ev.session);
        else segApi.get(sid).then(settle, () => settle(null));
        return;
      }
      if (ev.type === "error") { setJobError(ev.message); return; }
      if (ev.type === "item") setLiveIds((s) => new Set(s).add(ev.item.id));
      setSession((prev) => (prev && prev.id === sid ? { ...prev, state: applyEvent(prev.state, ev) } : prev));
    };
    const recover = () => {
      if (ctrl.signal.aborted || finished || sidRef.current !== sid) return;
      // The connection dropped mid-step: the step itself keeps running on the server.
      segApi.get(sid).then((s) => {
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

  const adopt = useCallback((s: SegSession) => {
    stopStream();
    sidRef.current = s.id;
    setSession(s);
    setJobError(null);
    setLiveIds(new Set());
    if (s.job) {
      setRunning({ jobId: s.job.id, kind: s.job.kind });
      runningRef.current = true;
      attach(s.id, s.job.id, 0);
    } else {
      setRunning(null);
      runningRef.current = false;
    }
  }, [attach, stopStream]);

  const openScope = useCallback((scope: Scope) => {
    setLoadError(null);
    segApi.open({ brand: scope.brand, plan_id: scope.planId, campaign_id: scope.campaignId })
      .then(adopt, (e) => { setLoadError(message(e)); setSession(null); sidRef.current = null; });
  }, [adopt]);

  const loadDataset = useCallback((refresh = false) => {
    setDatasetBusy(true);
    segApi.dataset(refresh).then(setDataset, () => undefined).finally(() => setDatasetBusy(false));
  }, []);
  useEffect(() => { loadDataset(false); }, [loadDataset]);
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

  /** A plain step: the server answers with the session. Returns false when it failed. */
  const direct = useCallback(async (fn: (sid: string) => Promise<SegSession>): Promise<boolean> => {
    const sid = sidRef.current;
    if (!sid) return false;
    setJobError(null);
    try {
      const s = await fn(sid);
      if (sidRef.current === sid) adopt(s);
      return true;
    } catch (e) {
      setJobError(message(e));
      return false;
    }
  }, [adopt]);

  return {
    session, loadError, running, jobError, liveIds, dataset, datasetBusy,
    openScope, loadDataset,
    clearError: () => setJobError(null),
    query: (text: string) => direct((sid) => segApi.query(sid, text)),
    consent: (values: string[]) => start((sid) => segApi.consent(sid, values)),
    name: (name: string) => start((sid) => segApi.name(sid, name)),
    create: () => start((sid) => segApi.create(sid)),
    discard: () => direct((sid) => segApi.discard(sid)),
    reset: () => direct((sid) => segApi.reset(sid)),
    cancel: () => direct((sid) => segApi.cancel(sid)),
    rename: (title: string) => direct((sid) => segApi.rename(sid, title)),
  };
}
