import { useEffect, useMemo, useState } from "react";
import Box from "@mui/material/Box";
import Dialog from "@mui/material/Dialog";
import IconButton from "@mui/material/IconButton";
import Link from "@mui/material/Link";
import CircularProgress from "@mui/material/CircularProgress";
import Typography from "@mui/material/Typography";
import {
  fetchCogneeStatus,
  fetchPharmaIntelArtifacts,
  fetchPharmaIntelSummary,
  probeCogneeGrounding,
  submitCogneeFeedback,
  type CogneeProbe,
  type CogneeStatus,
  type PharmaIntelArtifacts,
  type PharmaIntelSummary,
} from "../api";
import { ConsolePanel } from "../components/ConsolePanel";
import { tokens, indigoTint } from "../theme/tokens";

const fmt = new Intl.NumberFormat("en-US");
type Drilldown = { kind: string; value?: string; title: string };

const evidenceKindByLabel: Record<string, string> = {
  "Official messages": "official_messages",
  "FDA label sections": "fda_label_sections",
  "DailyMed SPLs": "dailymed_spls",
  "Clinical trials": "clinical_trials",
  "PubMed articles": "pubmed_articles",
  "ASCO abstracts": "asco_abstracts",
  "SEER cancer stats": "seer_cancer_stats",
  "Award rows": "award_rows",
  "OPDP letters": "opdp_letters",
  "SEC mentions": "sec_mentions",
};

function clickableSx(enabled: boolean) {
  return enabled
    ? {
        cursor: "pointer",
        transition: "border-color 120ms ease, background-color 120ms ease, transform 120ms ease",
        "&:hover": { borderColor: tokens.color.primary, background: indigoTint(0.035), transform: "translateY(-1px)" },
        "&:focus-visible": { outline: `2px solid ${tokens.color.primary}`, outlineOffset: 2 },
      }
    : {};
}

function StatTile({ icon, label, value, onOpen }: { icon: string; label: string; value: number; onOpen?: () => void }) {
  return (
    <Box
      role={onOpen ? "button" : undefined}
      tabIndex={onOpen ? 0 : undefined}
      onClick={onOpen}
      onKeyDown={(event) => {
        if (onOpen && (event.key === "Enter" || event.key === " ")) {
          event.preventDefault();
          onOpen();
        }
      }}
      sx={{ border: `1px solid ${tokens.color.outline}`, borderRadius: 2, p: 2, minWidth: 0, background: "#fff", ...clickableSx(Boolean(onOpen)) }}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
        <span className="material-symbols-outlined" style={{ fontSize: 18, color: tokens.color.primary }}>
          {icon}
        </span>
        <Typography variant="caption" sx={{ color: "text.secondary", fontWeight: 700, textTransform: "uppercase" }}>
          {label}
        </Typography>
      </Box>
      <Typography sx={{ fontSize: 28, fontWeight: 800, lineHeight: 1 }}>{fmt.format(value || 0)}</Typography>
    </Box>
  );
}

function BarList({ rows, onOpen }: { rows: Array<{ label: string; count: number }>; onOpen?: (row: { label: string; count: number }) => void }) {
  const max = Math.max(1, ...rows.map((row) => row.count || 0));
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1.25 }}>
      {rows.map((row) => (
        <Box
          key={row.label}
          role={onOpen ? "button" : undefined}
          tabIndex={onOpen ? 0 : undefined}
          onClick={() => onOpen?.(row)}
          onKeyDown={(event) => {
            if (onOpen && (event.key === "Enter" || event.key === " ")) {
              event.preventDefault();
              onOpen(row);
            }
          }}
          sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "220px 1fr 74px" }, gap: 1, alignItems: "center", borderRadius: 1, px: 0.75, py: 0.25, ...clickableSx(Boolean(onOpen)) }}
        >
          <Typography sx={{ fontSize: 13, color: "text.secondary", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {row.label}
          </Typography>
          <Box sx={{ height: 12, borderRadius: 999, background: indigoTint(0.08), overflow: "hidden" }}>
            <Box sx={{ width: `${Math.max(3, (row.count / max) * 100)}%`, height: "100%", background: tokens.color.primary }} />
          </Box>
          <Typography sx={{ fontSize: 13, fontWeight: 800, textAlign: { xs: "left", md: "right" } }}>{fmt.format(row.count)}</Typography>
        </Box>
      ))}
    </Box>
  );
}

function CoverageTable({ rows, onOpen }: { rows: PharmaIntelSummary["top_brands"]; onOpen: (brand: string) => void }) {
  const max = Math.max(1, ...rows.map((row) => Number(row.total_evidence_count || 0)));
  return (
    <Box sx={{ overflowX: "auto" }}>
      <Box component="table" sx={{ width: "100%", borderCollapse: "collapse", minWidth: 760 }}>
        <Box component="thead">
          <Box component="tr" sx={{ borderBottom: `1px solid ${tokens.color.outline}` }}>
            {["Brand", "Total", "Labels", "Trials", "PubMed", "ASCO", "Awards", "SEC"].map((h) => (
              <Box component="th" key={h} sx={{ textAlign: h === "Brand" ? "left" : "right", py: 1, px: 1, fontSize: 12, color: "text.secondary" }}>
                {h}
              </Box>
            ))}
          </Box>
        </Box>
        <Box component="tbody">
          {rows.map((row) => {
            const total = Number(row.total_evidence_count || 0);
            const brand = String(row.brand || "");
            return (
              <Box
                component="tr"
                key={brand}
                role="button"
                tabIndex={0}
                onClick={() => onOpen(brand)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onOpen(brand);
                  }
                }}
                sx={{ borderBottom: `1px solid ${tokens.color.outline}`, ...clickableSx(true) }}
              >
                <Box component="td" sx={{ py: 1.1, px: 1, fontWeight: 800 }}>{row.brand}</Box>
                <Box component="td" sx={{ py: 1.1, px: 1, minWidth: 170 }}>
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                    <Box sx={{ flex: 1, height: 10, borderRadius: 999, background: indigoTint(0.08), overflow: "hidden" }}>
                      <Box sx={{ width: `${Math.max(4, (total / max) * 100)}%`, height: "100%", background: tokens.color.secondary }} />
                    </Box>
                    <Typography sx={{ fontSize: 13, fontWeight: 800, width: 42, textAlign: "right" }}>{fmt.format(total)}</Typography>
                  </Box>
                </Box>
                {[
                  Number(row.label_message_count || 0) + Number(row.dailymed_label_count || 0),
                  row.clinical_trial_count,
                  row.pubmed_article_count,
                  row.asco_abstract_count,
                  row.award_mention_count,
                  row.sec_annual_filing_mention_count,
                ].map((value, idx) => (
                  <Box component="td" key={idx} sx={{ py: 1.1, px: 1, textAlign: "right", fontSize: 13, fontWeight: 700 }}>
                    {fmt.format(Number(value || 0))}
                  </Box>
                ))}
              </Box>
            );
          })}
        </Box>
      </Box>
    </Box>
  );
}

function ArtifactViewer({
  drilldown,
  data,
  loading,
  error,
  onClose,
}: {
  drilldown: Drilldown | null;
  data: PharmaIntelArtifacts | null;
  loading: boolean;
  error: string;
  onClose: () => void;
}) {
  return (
    <Dialog open={Boolean(drilldown)} onClose={onClose} fullWidth maxWidth="lg">
      <Box sx={{ p: 3, pb: 2, borderBottom: `1px solid ${tokens.color.outline}`, position: "relative" }}>
        <Typography variant="h2" sx={{ pr: 5 }}>{data?.title || drilldown?.title || "Artifacts"}</Typography>
        <Typography sx={{ color: "text.secondary", mt: 0.75, fontSize: 13 }}>
          Representative scraped records from the pharma intelligence warehouse.
        </Typography>
        <IconButton onClick={onClose} aria-label="Close" sx={{ position: "absolute", top: 14, right: 14 }}>
          <span className="material-symbols-outlined">close</span>
        </IconButton>
      </Box>
      <Box sx={{ p: 3, maxHeight: "72vh", overflowY: "auto", background: tokens.color.canvas }}>
        {loading && (
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, color: "text.secondary" }}>
            <CircularProgress size={20} />
            <Typography>Loading artifacts...</Typography>
          </Box>
        )}
        {error && <Typography sx={{ color: tokens.color.danger }}>{error}</Typography>}
        {!loading && !error && data?.items.length === 0 && <Typography sx={{ color: "text.secondary" }}>No artifacts found for this selection.</Typography>}
        {!loading && !error && data?.items.map((item, idx) => (
          <Box key={`${item.id}-${idx}`} sx={{ background: "#fff", border: `1px solid ${tokens.color.outline}`, borderRadius: 2, p: 2, mb: 2 }}>
            <Box sx={{ display: "flex", gap: 1.5, alignItems: "flex-start", justifyContent: "space-between" }}>
              <Box sx={{ minWidth: 0 }}>
                <Typography sx={{ fontWeight: 800, overflowWrap: "anywhere" }}>{item.title}</Typography>
                {item.subtitle && <Typography sx={{ color: "text.secondary", fontSize: 12, mt: 0.5, overflowWrap: "anywhere" }}>{item.subtitle}</Typography>}
              </Box>
              {item.url && (
                <Link href={item.url} target="_blank" rel="noreferrer" sx={{ flex: "0 0 auto", fontSize: 12, fontWeight: 700 }}>
                  Source
                </Link>
              )}
            </Box>
            {Object.keys(item.metadata || {}).length > 0 && (
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75, mt: 1.5 }}>
                {Object.entries(item.metadata).map(([key, value]) => (
                  <Box key={key} sx={{ border: `1px solid ${indigoTint(0.14)}`, background: indigoTint(0.045), borderRadius: 1, px: 1, py: 0.5 }}>
                    <Typography component="span" sx={{ fontSize: 11, color: "text.secondary", mr: 0.5 }}>{key}</Typography>
                    <Typography component="span" sx={{ fontSize: 11, fontWeight: 800 }}>{String(value)}</Typography>
                  </Box>
                ))}
              </Box>
            )}
            <Box
              component="pre"
              sx={{
                mt: 1.5,
                mb: 0,
                whiteSpace: "pre-wrap",
                overflowWrap: "anywhere",
                fontFamily: "Consolas, 'Courier New', monospace",
                fontSize: 12,
                lineHeight: 1.55,
                maxHeight: 340,
                overflowY: "auto",
                background: "rgba(15, 23, 42, 0.04)",
                border: `1px solid ${tokens.color.outline}`,
                borderRadius: 1,
                p: 1.5,
              }}
            >
              {item.content || "No captured text is stored for this artifact."}
            </Box>
          </Box>
        ))}
      </Box>
    </Dialog>
  );
}

function CogneeQaPanel() {
  const [status, setStatus] = useState<CogneeStatus | null>(null);
  const [probe, setProbe] = useState<CogneeProbe | null>(null);
  const [brand, setBrand] = useState("Oncomyra");
  const [therapyArea, setTherapyArea] = useState("oncology");
  const [selectedTopics, setSelectedTopics] = useState<string[]>(["intake_context", "segmentation_targeting", "channel_budget"]);
  const [activeTopic, setActiveTopic] = useState("");
  const [feedback, setFeedback] = useState("");
  const [expected, setExpected] = useState("");
  const [rating, setRating] = useState("needs-fix");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchCogneeStatus().then(setStatus).catch((err) => setError(String(err)));
  }, []);

  const runProbe = async () => {
    setBusy(true);
    setError("");
    try {
      const data = await probeCogneeGrounding({ brand, therapy_area: therapyArea, topics: selectedTopics });
      setProbe(data);
      setActiveTopic(data.topics[0]?.topic ?? "");
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

  const active = probe?.topics.find((topic) => topic.topic === activeTopic) ?? probe?.topics[0];
  const toggleTopic = (topic: string) => {
    setSelectedTopics((prev) => prev.includes(topic) ? prev.filter((item) => item !== topic) : [...prev, topic]);
  };

  const saveFeedback = async () => {
    if (!active || !feedback.trim()) return;
    setBusy(true);
    setError("");
    try {
      const data = await submitCogneeFeedback({
        topic: active.topic,
        brand,
        therapy_area: therapyArea,
        request: active.query,
        observed: active.guidance,
        feedback,
        expected,
        rating,
      });
      setStatus((prev) => prev ? { ...prev, feedback: data.items } : prev);
      setFeedback("");
      setExpected("");
      await runProbe();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <ConsolePanel title="Cognee Grounding QA" icon="psychology">
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "0.8fr 1.2fr" }, gap: 2.5 }}>
        <Box>
          <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", mb: 1.5 }}>
            <Box sx={{ border: `1px solid ${tokens.color.outline}`, borderRadius: 1, px: 1, py: 0.5, background: status?.health.enabled ? indigoTint(0.05) : "#fff" }}>
              <Typography sx={{ fontSize: 12, fontWeight: 800 }}>Enabled: {String(status?.health.enabled ?? false)}</Typography>
            </Box>
            <Box sx={{ border: `1px solid ${tokens.color.outline}`, borderRadius: 1, px: 1, py: 0.5, background: status?.health.graph_ready ? "rgba(16,185,129,0.08)" : "rgba(245,158,11,0.08)" }}>
              <Typography sx={{ fontSize: 12, fontWeight: 800 }}>Graph ready: {String(status?.health.graph_ready ?? false)}</Typography>
            </Box>
          </Box>
          <Typography sx={{ color: "text.secondary", fontSize: 13, mb: 2 }}>
            {status?.health.note ?? "Checking Cognee status..."}
          </Typography>
          <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, mb: 1.5 }}>
            <Box component="input" value={brand} onChange={(event) => setBrand(event.target.value)} placeholder="Brand" style={{ padding: 10, border: `1px solid ${tokens.color.outline}`, borderRadius: 8 }} />
            <Box component="input" value={therapyArea} onChange={(event) => setTherapyArea(event.target.value)} placeholder="Therapy area" style={{ padding: 10, border: `1px solid ${tokens.color.outline}`, borderRadius: 8 }} />
          </Box>
          <Typography sx={{ fontSize: 12, fontWeight: 800, mb: 1 }}>Topics to probe</Typography>
          <Box sx={{ display: "flex", gap: 0.75, flexWrap: "wrap", mb: 2 }}>
            {(status?.topics ?? []).map((topic) => {
              const checked = selectedTopics.includes(topic.key);
              return (
                <Box
                  key={topic.key}
                  role="button"
                  tabIndex={0}
                  onClick={() => toggleTopic(topic.key)}
                  sx={{ px: 1, py: 0.5, borderRadius: 999, border: `1px solid ${checked ? tokens.color.primary : tokens.color.outline}`, background: checked ? indigoTint(0.08) : "#fff", fontSize: 12, fontWeight: 700, cursor: "pointer" }}
                >
                  {topic.key}
                </Box>
              );
            })}
          </Box>
          <Box component="button" disabled={busy || selectedTopics.length === 0} onClick={runProbe} style={{ padding: "9px 14px", borderRadius: 8, border: 0, background: tokens.color.primary, color: "#fff", fontWeight: 800, cursor: "pointer" }}>
            {busy ? "Running..." : "Run request probe"}
          </Box>
          {probe && <Typography sx={{ fontSize: 12, color: "text.secondary", mt: 1 }}>Probe finished in {probe.elapsed_ms} ms.</Typography>}
          {error && <Typography sx={{ color: tokens.color.danger, mt: 1 }}>{error}</Typography>}
        </Box>

        <Box>
          {!probe && <Typography sx={{ color: "text.secondary" }}>Run a probe to see per-topic Cognee extraction and feedback overlays.</Typography>}
          {probe && (
            <>
              <Box sx={{ display: "flex", gap: 0.75, flexWrap: "wrap", mb: 1.5 }}>
                {probe.topics.map((topic) => (
                  <Box key={topic.topic} role="button" tabIndex={0} onClick={() => setActiveTopic(topic.topic)} sx={{ px: 1, py: 0.5, borderRadius: 1, border: `1px solid ${active?.topic === topic.topic ? tokens.color.primary : tokens.color.outline}`, background: topic.has_guidance ? indigoTint(0.05) : "rgba(245,158,11,0.06)", cursor: "pointer", fontSize: 12, fontWeight: 800 }}>
                    {topic.topic} {topic.has_guidance ? "" : "(empty)"}
                  </Box>
                ))}
              </Box>
              {active && (
                <Box>
                  <Typography sx={{ fontSize: 12, fontWeight: 800, mb: 0.5 }}>Request query</Typography>
                  <Typography sx={{ fontSize: 12, color: "text.secondary", mb: 1.25 }}>{active.query}</Typography>
                  <Typography sx={{ fontSize: 12, fontWeight: 800, mb: 0.5 }}>Extracted guidance</Typography>
                  <Box component="pre" sx={{ whiteSpace: "pre-wrap", fontSize: 12, lineHeight: 1.5, maxHeight: 240, overflow: "auto", border: `1px solid ${tokens.color.outline}`, borderRadius: 1, p: 1.25, background: "#fff" }}>
                    {active.guidance || "No Cognee guidance returned for this topic/request."}
                  </Box>
                  <Typography sx={{ fontSize: 12, fontWeight: 800, mt: 1.5, mb: 0.75 }}>Feedback for future requests</Typography>
                  <Box component="textarea" value={feedback} onChange={(event) => setFeedback(event.target.value)} placeholder="What is wrong or missing in this extraction?" style={{ width: "100%", minHeight: 68, padding: 10, border: `1px solid ${tokens.color.outline}`, borderRadius: 8, resize: "vertical" }} />
                  <Box component="textarea" value={expected} onChange={(event) => setExpected(event.target.value)} placeholder="Expected correction / better guidance" style={{ width: "100%", minHeight: 68, padding: 10, marginTop: 8, border: `1px solid ${tokens.color.outline}`, borderRadius: 8, resize: "vertical" }} />
                  <Box sx={{ display: "flex", gap: 1, alignItems: "center", mt: 1 }}>
                    <Box component="select" value={rating} onChange={(event) => setRating(event.target.value)} style={{ padding: 8, border: `1px solid ${tokens.color.outline}`, borderRadius: 8 }}>
                      <option value="needs-fix">Needs fix</option>
                      <option value="missing">Missing</option>
                      <option value="good">Good</option>
                    </Box>
                    <Box component="button" disabled={busy || !feedback.trim()} onClick={saveFeedback} style={{ padding: "8px 12px", borderRadius: 8, border: 0, background: tokens.color.secondary, color: "#fff", fontWeight: 800, cursor: "pointer" }}>
                      Save feedback
                    </Box>
                  </Box>
                </Box>
              )}
            </>
          )}
        </Box>
      </Box>
      {(status?.feedback ?? []).length > 0 && (
        <Box sx={{ mt: 2.5, pt: 2, borderTop: `1px solid ${tokens.color.outline}` }}>
          <Typography sx={{ fontSize: 12, fontWeight: 800, mb: 1 }}>Recent feedback overlay</Typography>
          {(status?.feedback ?? []).slice(0, 5).map((item) => (
            <Typography key={item.id} sx={{ fontSize: 12, color: "text.secondary", mb: 0.5 }}>
              <b>{item.topic}</b>: {item.feedback}
            </Typography>
          ))}
        </Box>
      )}
    </ConsolePanel>
  );
}

export function Artefacts() {
  const [data, setData] = useState<PharmaIntelSummary | null>(null);
  const [error, setError] = useState("");
  const [drilldown, setDrilldown] = useState<Drilldown | null>(null);
  const [artifactData, setArtifactData] = useState<PharmaIntelArtifacts | null>(null);
  const [artifactError, setArtifactError] = useState("");
  const [artifactLoading, setArtifactLoading] = useState(false);

  useEffect(() => {
    fetchPharmaIntelSummary().then(setData).catch((err) => setError(String(err)));
  }, []);

  useEffect(() => {
    if (!drilldown) return;
    setArtifactLoading(true);
    setArtifactError("");
    setArtifactData(null);
    fetchPharmaIntelArtifacts(drilldown.kind, drilldown.value ?? "")
      .then(setArtifactData)
      .catch((err) => setArtifactError(String(err)))
      .finally(() => setArtifactLoading(false));
  }, [drilldown]);

  const sourceRows = useMemo(
    () => (data?.source_counts ?? []).map((row) => ({ label: row.source, count: row.count })),
    [data],
  );

  return (
    <Box sx={{ maxWidth: 1240, mx: "auto", px: { xs: 2, md: 6 }, py: 6, display: "flex", flexDirection: "column", gap: 4 }}>
      <Box>
        <Typography variant="h1">Artefacts</Typography>
        <Typography sx={{ color: "text.secondary", mt: 1 }}>
          Pharma intelligence warehouse, oncology evidence coverage and campaign-message sources.
        </Typography>
      </Box>

      {error && (
        <ConsolePanel title="Warehouse status" icon="error">
          <Typography sx={{ color: tokens.color.danger }}>{error}</Typography>
        </ConsolePanel>
      )}

      {!data && !error && (
        <ConsolePanel title="Warehouse status" icon="hourglass_top">
          <Typography sx={{ color: "text.secondary" }}>Loading warehouse summary...</Typography>
        </ConsolePanel>
      )}

      {data && (
        <>
          <CogneeQaPanel />

          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr 1fr", lg: "repeat(5, 1fr)" }, gap: 2 }}>
            <StatTile icon="database" label="Documents" value={data.totals.documents ?? 0} onOpen={() => setDrilldown({ kind: "documents", title: "Indexed source documents" })} />
            <StatTile icon="travel_explore" label="Sources" value={data.totals.sources ?? 0} onOpen={() => setDrilldown({ kind: "documents", title: "Indexed source documents" })} />
            <StatTile icon="biotech" label="ASCO abstracts" value={data.totals.asco_abstracts ?? 0} onOpen={() => setDrilldown({ kind: "asco_abstracts", title: "ASCO abstracts" })} />
            <StatTile icon="query_stats" label="SEER sites" value={data.totals.seer_cancer_stats ?? 0} onOpen={() => setDrilldown({ kind: "seer_cancer_stats", title: "SEER cancer stats" })} />
            <StatTile icon="campaign" label="Message evidence" value={data.totals.message_evidence ?? 0} onOpen={() => setDrilldown({ kind: "message_evidence", title: "Message evidence" })} />
          </Box>

          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "1.15fr 0.85fr" }, gap: 3 }}>
            <ConsolePanel title="Oncology Evidence Mix" icon="hub">
              <BarList
                rows={data.evidence_mix ?? []}
                onOpen={(row) => setDrilldown({ kind: evidenceKindByLabel[row.label] ?? "documents", title: row.label })}
              />
            </ConsolePanel>
            <ConsolePanel title="Campaign Message Mix" icon="forum">
              <BarList rows={data.message_mix ?? []} onOpen={(row) => setDrilldown({ kind: `message:${row.label}`, title: row.label })} />
            </ConsolePanel>
          </Box>

          <ConsolePanel title="Top Oncology Brand Coverage" icon="monitoring">
            <CoverageTable rows={data.top_brands ?? []} onOpen={(brand) => setDrilldown({ kind: "brand", value: brand, title: brand })} />
          </ConsolePanel>

          <ConsolePanel title="Indexed Source Documents" icon="source">
            <BarList rows={sourceRows} onOpen={(row) => setDrilldown({ kind: "source", value: row.label, title: row.label })} />
          </ConsolePanel>
        </>
      )}

      <ArtifactViewer drilldown={drilldown} data={artifactData} loading={artifactLoading} error={artifactError} onClose={() => setDrilldown(null)} />
    </Box>
  );
}
