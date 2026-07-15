import { useEffect, useState } from "react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import IconButton from "@mui/material/IconButton";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { generateBrd, generateRaci, getSetup, saveSetup } from "../../api";
import { PlanTable } from "./PlanTable";
import { StageHead } from "./StageHead";
import { ConsolePanel } from "../../components/ConsolePanel";
import type { CampaignSetup, Confirmation, PlanResult, ResourcePlanRow, Stakeholder, TimelineActivity, Vendor } from "../types";

let uid = 0;
const nextId = () => `s${Date.now()}_${++uid}`;

const emptySetup = (): CampaignSetup => ({
  jira: { space_key: "", project_id: "", board_url: "" },
  stakeholders: [],
  vendors: [],
  confirmations: [],
  timeline: [],
  resources: [],
  raci: [],
  brd: null,
});

const RACI_LETTERS = ["R", "A", "C", "I"] as const;

export function StageOrchestration({ result, projectId }: { result: PlanResult | null; projectId: string | null }) {
  const [setup, setSetup] = useState<CampaignSetup>(emptySetup());
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState<"raci" | "brd" | null>(null);

  useEffect(() => {
    if (!projectId) return;
    setLoaded(false);
    getSetup(projectId).then((s) => { setSetup({ ...emptySetup(), ...s }); setLoaded(true); });
  }, [projectId]);

  if (!result) {
    return <ConsolePanel><Typography sx={{ color: "text.secondary", fontStyle: "italic" }}>Complete Stage 1 to begin campaign delivery setup.</Typography></ConsolePanel>;
  }
  if (!projectId || !loaded) {
    return <ConsolePanel><Typography sx={{ color: "text.secondary", fontStyle: "italic" }}>Loading setup…</Typography></ConsolePanel>;
  }

  const keyMessages = result.stage_2_4_message_flow?.key_messages ?? [];
  const channels = result.stage_5_channel_selection?.channels ?? [];

  const persist = async (next: CampaignSetup) => {
    setSetup(next);
    setSaving(true);
    try {
      await saveSetup(projectId, next);
    } finally {
      setSaving(false);
    }
  };

  const addStakeholder = () => persist({ ...setup, stakeholders: [...setup.stakeholders, { id: nextId(), name: "", role: "", team: "", email: "" }] });
  const updateStakeholder = (id: string, patch: Partial<Stakeholder>) =>
    persist({ ...setup, stakeholders: setup.stakeholders.map((s) => (s.id === id ? { ...s, ...patch } : s)) });
  const removeStakeholder = (id: string) => persist({ ...setup, stakeholders: setup.stakeholders.filter((s) => s.id !== id) });

  const addVendor = () => persist({ ...setup, vendors: [...setup.vendors, { id: nextId(), name: "", type: "", contact: "", status: "Identified" }] });
  const updateVendor = (id: string, patch: Partial<Vendor>) =>
    persist({ ...setup, vendors: setup.vendors.map((v) => (v.id === id ? { ...v, ...patch } : v)) });
  const removeVendor = (id: string) => persist({ ...setup, vendors: setup.vendors.filter((v) => v.id !== id) });

  const addConfirmation = () => persist({ ...setup, confirmations: [...setup.confirmations, { id: nextId(), team: "Marketing", item: "", status: "Pending", notes: "" }] });
  const updateConfirmation = (id: string, patch: Partial<Confirmation>) =>
    persist({ ...setup, confirmations: setup.confirmations.map((c) => (c.id === id ? { ...c, ...patch } : c)) });
  const removeConfirmation = (id: string) => persist({ ...setup, confirmations: setup.confirmations.filter((c) => c.id !== id) });

  const addActivity = () => persist({ ...setup, timeline: [...setup.timeline, { id: nextId(), activity: "", start: "", end: "", duration_days: undefined, status: "Not started", raci: {} }] });
  const updateActivity = (id: string, patch: Partial<TimelineActivity>) =>
    persist({ ...setup, timeline: setup.timeline.map((a) => (a.id === id ? { ...a, ...patch } : a)) });
  const removeActivity = (id: string) => persist({ ...setup, timeline: setup.timeline.filter((a) => a.id !== id) });
  const setActivityRaci = (activityId: string, stakeholderId: string, letter: string) =>
    persist({
      ...setup,
      timeline: setup.timeline.map((a) =>
        a.id === activityId ? { ...a, raci: { ...(a.raci ?? {}), [stakeholderId]: letter === "" ? undefined : (letter as "R" | "A" | "C" | "I") } } : a,
      ),
    });

  const addResource = () => persist({ ...setup, resources: [...setup.resources, { id: nextId(), role: "", stakeholder_id: undefined, stakeholder_name: "", allocation_pct: undefined, notes: "" }] });
  const updateResource = (id: string, patch: Partial<ResourcePlanRow>) =>
    persist({ ...setup, resources: setup.resources.map((r) => (r.id === id ? { ...r, ...patch } : r)) });
  const removeResource = (id: string) => persist({ ...setup, resources: setup.resources.filter((r) => r.id !== id) });

  const onGenerateRaci = async () => {
    setGenerating("raci");
    try {
      const { raci } = await generateRaci(projectId);
      setSetup((s) => ({ ...s, raci }));
    } finally {
      setGenerating(null);
    }
  };

  const onGenerateBrd = async () => {
    setGenerating("brd");
    try {
      const brd = await generateBrd(projectId);
      setSetup((s) => ({ ...s, brd }));
    } finally {
      setGenerating(null);
    }
  };

  return (
    <Box>
      <StageHead
        icon="account_tree"
        title="Campaign Setup & Orchestration"
        blurb="Stand up delivery of the plan: Jira space, stakeholder register and vendors, reconfirm key messages/channels/asset availability with marketing and medical, estimate the timeline, plan resourcing, then generate the RACI and BRD before moving to Campaign Operations."
      />

      <ConsolePanel title="Carried over from Brand Plan & Strategy" sx={{ mb: 3 }}>
        <Typography variant="overline">Key messages to reconfirm</Typography>
        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, mt: 0.5, mb: 1.5 }}>
          {keyMessages.length ? keyMessages.map((km, i) => <Chip key={i} size="small" label={km.topic} />) : <Typography variant="body2" sx={{ color: "text.secondary", fontStyle: "italic" }}>None captured.</Typography>}
        </Box>
        <Typography variant="overline">Channels to reconfirm</Typography>
        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, mt: 0.5 }}>
          {channels.length ? channels.map((c, i) => <Chip key={i} size="small" color="secondary" label={c.channel} />) : <Typography variant="body2" sx={{ color: "text.secondary", fontStyle: "italic" }}>None captured.</Typography>}
        </Box>
      </ConsolePanel>

      <ConsolePanel title="Jira space" sx={{ mb: 3 }}>
        <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
          <TextField size="small" label="Space key" value={setup.jira.space_key} onChange={(e) => persist({ ...setup, jira: { ...setup.jira, space_key: e.target.value } })} />
          <TextField size="small" label="Project ID" value={setup.jira.project_id} onChange={(e) => persist({ ...setup, jira: { ...setup.jira, project_id: e.target.value } })} />
          <TextField size="small" label="Board URL" sx={{ minWidth: 260 }} value={setup.jira.board_url ?? ""} onChange={(e) => persist({ ...setup, jira: { ...setup.jira, board_url: e.target.value } })} />
        </Box>
      </ConsolePanel>

      <ConsolePanel title="Stakeholder register" sx={{ mb: 3 }}>
        <PlanTable>
          <thead><tr><th>Name</th><th>Role</th><th>Team</th><th>Email</th><th /></tr></thead>
          <tbody>
            {setup.stakeholders.map((s) => (
              <tr key={s.id}>
                <td><TextField size="small" variant="standard" value={s.name} onChange={(e) => updateStakeholder(s.id, { name: e.target.value })} /></td>
                <td><TextField size="small" variant="standard" value={s.role} onChange={(e) => updateStakeholder(s.id, { role: e.target.value })} /></td>
                <td><TextField size="small" variant="standard" value={s.team} onChange={(e) => updateStakeholder(s.id, { team: e.target.value })} /></td>
                <td><TextField size="small" variant="standard" value={s.email ?? ""} onChange={(e) => updateStakeholder(s.id, { email: e.target.value })} /></td>
                <td><IconButton size="small" onClick={() => removeStakeholder(s.id)}><span className="material-symbols-outlined" style={{ fontSize: 16 }}>close</span></IconButton></td>
              </tr>
            ))}
          </tbody>
        </PlanTable>
        <Button size="small" sx={{ mt: 1 }} onClick={addStakeholder}>+ Add stakeholder</Button>
      </ConsolePanel>

      <ConsolePanel title="Vendor details" sx={{ mb: 3 }}>
        <PlanTable>
          <thead><tr><th>Vendor</th><th>Type</th><th>Contact</th><th>Status</th><th /></tr></thead>
          <tbody>
            {setup.vendors.map((v) => (
              <tr key={v.id}>
                <td><TextField size="small" variant="standard" value={v.name} onChange={(e) => updateVendor(v.id, { name: e.target.value })} /></td>
                <td><TextField size="small" variant="standard" value={v.type} onChange={(e) => updateVendor(v.id, { type: e.target.value })} /></td>
                <td><TextField size="small" variant="standard" value={v.contact ?? ""} onChange={(e) => updateVendor(v.id, { contact: e.target.value })} /></td>
                <td><TextField size="small" variant="standard" value={v.status ?? ""} onChange={(e) => updateVendor(v.id, { status: e.target.value })} /></td>
                <td><IconButton size="small" onClick={() => removeVendor(v.id)}><span className="material-symbols-outlined" style={{ fontSize: 16 }}>close</span></IconButton></td>
              </tr>
            ))}
          </tbody>
        </PlanTable>
        <Button size="small" sx={{ mt: 1 }} onClick={addVendor}>+ Add vendor</Button>
      </ConsolePanel>

      <ConsolePanel title="Stakeholder reconfirmation — marketing & medical asset availability" sx={{ mb: 3 }}>
        <PlanTable>
          <thead><tr><th>Team</th><th>Item</th><th>Status</th><th>Notes</th><th /></tr></thead>
          <tbody>
            {setup.confirmations.map((c) => (
              <tr key={c.id}>
                <td>
                  <Select size="small" variant="standard" value={c.team} onChange={(e) => updateConfirmation(c.id, { team: e.target.value })}>
                    <MenuItem value="Marketing">Marketing</MenuItem>
                    <MenuItem value="Medical">Medical</MenuItem>
                    <MenuItem value="Legal/Regulatory">Legal/Regulatory</MenuItem>
                    <MenuItem value="Other">Other</MenuItem>
                  </Select>
                </td>
                <td><TextField size="small" variant="standard" value={c.item} onChange={(e) => updateConfirmation(c.id, { item: e.target.value })} /></td>
                <td>
                  <Select size="small" variant="standard" value={c.status} onChange={(e) => updateConfirmation(c.id, { status: e.target.value })}>
                    <MenuItem value="Pending">Pending</MenuItem>
                    <MenuItem value="Confirmed">Confirmed</MenuItem>
                    <MenuItem value="Blocked">Blocked</MenuItem>
                  </Select>
                </td>
                <td><TextField size="small" variant="standard" value={c.notes ?? ""} onChange={(e) => updateConfirmation(c.id, { notes: e.target.value })} /></td>
                <td><IconButton size="small" onClick={() => removeConfirmation(c.id)}><span className="material-symbols-outlined" style={{ fontSize: 16 }}>close</span></IconButton></td>
              </tr>
            ))}
          </tbody>
        </PlanTable>
        <Button size="small" sx={{ mt: 1 }} onClick={addConfirmation}>+ Add reconfirmation item</Button>
      </ConsolePanel>

      <ConsolePanel title="Timeline estimation & RACI assignment" sx={{ mb: 3 }}>
        <PlanTable>
          <thead>
            <tr>
              <th>Activity</th><th>Start</th><th>End</th><th>Duration (days)</th><th>Status</th>
              {setup.stakeholders.map((s) => <th key={s.id}>{s.name || "—"}</th>)}
              <th />
            </tr>
          </thead>
          <tbody>
            {setup.timeline.map((a) => (
              <tr key={a.id}>
                <td><TextField size="small" variant="standard" value={a.activity} onChange={(e) => updateActivity(a.id, { activity: e.target.value })} /></td>
                <td><TextField size="small" variant="standard" type="date" value={a.start ?? ""} onChange={(e) => updateActivity(a.id, { start: e.target.value })} /></td>
                <td><TextField size="small" variant="standard" type="date" value={a.end ?? ""} onChange={(e) => updateActivity(a.id, { end: e.target.value })} /></td>
                <td><TextField size="small" variant="standard" type="number" value={a.duration_days ?? ""} onChange={(e) => updateActivity(a.id, { duration_days: e.target.value ? Number(e.target.value) : undefined })} sx={{ width: 70 }} /></td>
                <td><TextField size="small" variant="standard" value={a.status ?? ""} onChange={(e) => updateActivity(a.id, { status: e.target.value })} /></td>
                {setup.stakeholders.map((s) => (
                  <td key={s.id}>
                    <Select size="small" variant="standard" value={a.raci?.[s.id] ?? ""} onChange={(e) => setActivityRaci(a.id, s.id, e.target.value)} sx={{ minWidth: 50 }}>
                      <MenuItem value="">—</MenuItem>
                      {RACI_LETTERS.map((l) => <MenuItem key={l} value={l}>{l}</MenuItem>)}
                    </Select>
                  </td>
                ))}
                <td><IconButton size="small" onClick={() => removeActivity(a.id)}><span className="material-symbols-outlined" style={{ fontSize: 16 }}>close</span></IconButton></td>
              </tr>
            ))}
          </tbody>
        </PlanTable>
        <Button size="small" sx={{ mt: 1 }} onClick={addActivity}>+ Add activity</Button>
      </ConsolePanel>

      <ConsolePanel title="Resource plan" sx={{ mb: 3 }}>
        <PlanTable>
          <thead><tr><th>Role</th><th>Assigned to</th><th>Allocation %</th><th>Notes</th><th /></tr></thead>
          <tbody>
            {setup.resources.map((r) => (
              <tr key={r.id}>
                <td><TextField size="small" variant="standard" value={r.role} onChange={(e) => updateResource(r.id, { role: e.target.value })} /></td>
                <td>
                  <Select size="small" variant="standard" value={r.stakeholder_id ?? ""} onChange={(e) => {
                    const sid = e.target.value as string;
                    const found = setup.stakeholders.find((s) => s.id === sid);
                    updateResource(r.id, { stakeholder_id: sid || undefined, stakeholder_name: found?.name ?? "" });
                  }} sx={{ minWidth: 140 }}>
                    <MenuItem value="">—</MenuItem>
                    {setup.stakeholders.map((s) => <MenuItem key={s.id} value={s.id}>{s.name || "(unnamed)"}</MenuItem>)}
                  </Select>
                </td>
                <td><TextField size="small" variant="standard" type="number" value={r.allocation_pct ?? ""} onChange={(e) => updateResource(r.id, { allocation_pct: e.target.value ? Number(e.target.value) : undefined })} sx={{ width: 70 }} /></td>
                <td><TextField size="small" variant="standard" value={r.notes ?? ""} onChange={(e) => updateResource(r.id, { notes: e.target.value })} /></td>
                <td><IconButton size="small" onClick={() => removeResource(r.id)}><span className="material-symbols-outlined" style={{ fontSize: 16 }}>close</span></IconButton></td>
              </tr>
            ))}
          </tbody>
        </PlanTable>
        <Button size="small" sx={{ mt: 1 }} onClick={addResource}>+ Add resource</Button>
      </ConsolePanel>

      <ConsolePanel title="RACI" sx={{ mb: 3 }}>
        <Button size="small" variant="outlined" onClick={onGenerateRaci} disabled={generating === "raci"} sx={{ mb: 2 }}>
          {generating === "raci" ? "Generating…" : "Generate RACI from timeline"}
        </Button>
        {setup.raci.length ? (
          <PlanTable>
            <thead><tr><th>Activity</th><th>Responsible</th><th>Accountable</th><th>Consulted</th><th>Informed</th></tr></thead>
            <tbody>
              {setup.raci.map((row, i) => {
                const byLetter: Record<string, string[]> = { R: [], A: [], C: [], I: [] };
                row.assignments.forEach((a) => byLetter[a.letter]?.push(a.name));
                return (
                  <tr key={i}>
                    <td>{row.activity}</td>
                    <td>{byLetter.R.join(", ") || "—"}</td>
                    <td>{byLetter.A.join(", ") || "—"}</td>
                    <td>{byLetter.C.join(", ") || "—"}</td>
                    <td>{byLetter.I.join(", ") || "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </PlanTable>
        ) : (
          <Typography sx={{ color: "text.secondary", fontStyle: "italic" }}>Not generated yet — add timeline activities and RACI letters per stakeholder above, then generate.</Typography>
        )}
      </ConsolePanel>

      <ConsolePanel title="Business Requirements Document (BRD)">
        <Box sx={{ display: "flex", gap: 1.5, alignItems: "center", mb: 2 }}>
          <Button size="small" variant="contained" onClick={onGenerateBrd} disabled={generating === "brd"}>
            {generating === "brd" ? "Generating…" : "Generate BRD"}
          </Button>
          {setup.brd && (
            <Button size="small" component="a" href={`/api/projects/${projectId}/export-brd.docx`} target="_blank" rel="noreferrer">
              Download .docx
            </Button>
          )}
          {saving && <Typography variant="caption" sx={{ color: "text.secondary" }}>Saving…</Typography>}
        </Box>
        {setup.brd ? (
          <Box component="pre" sx={{ whiteSpace: "pre-wrap", fontFamily: "inherit", fontSize: 13, maxHeight: 400, overflowY: "auto", m: 0 }}>
            {setup.brd.markdown}
          </Box>
        ) : (
          <Typography sx={{ color: "text.secondary", fontStyle: "italic" }}>Not generated yet.</Typography>
        )}
      </ConsolePanel>
    </Box>
  );
}
