import { useEffect, useState } from "react";
import { getBrandTree, listBrands } from "../../api";
import type { BrandSummary, BrandTree, TreeCampaign, TreePlan } from "../../types";
import { Icon } from "../Icon";
import { SopDiagramViewer } from "../hierarchy/SopDiagramViewer";
import { periodLabel } from "../hierarchy/shared";
import { FlowEditorChat } from "./FlowEditorChat";
import { PickerModal, type PickerItem } from "./PickerModal";

/**
 * Flow Planner wizard: an empty page until the flow is ready, and BrandOverview's own
 * "build something" launcher card (plan-launcher-backdrop/plan-launcher-card, wiz-choice-grid)
 * reused verbatim for the chat step -- centered, dimmed backdrop, a two-card choice grid, plus
 * a free-text fallback row under the cards. Walks brand -> engagement plan -> campaign, each
 * pick made through a list+detail popup (the same master-detail layout as BrandOverview's plan
 * list), then generates the SOP flow diagram onto the canvas that was blank until then.
 *
 * "New brand" and "Ad-hoc campaign" are stubbed (say so, go no further) -- only the
 * existing-brand / existing-engagement / existing-campaign path is real, by design (this
 * is the path worth shipping first; the other branches are a separate pass).
 *
 * What is picked drives navigation and the on-screen recap only. The generated diagram
 * itself still comes from strategy/flow_sop/demo_brief.py regardless of which campaign was
 * selected -- wiring the picked campaign's own data into the generator is a later step
 * (see strategy/flow_sop's own scope note).
 */

/** The free-text fallback under the two choice cards. Not just a binary "new"/"existing"
 *  read -- if the text also names a real plan and/or campaign (e.g. "Cardiovex, Q4 2026
 *  launch, payer follow-up"), resolveText() below jumps straight past those steps instead of
 *  asking them one at a time. A brief "thinking" state stands in for the grounding lookups
 *  that answer actually requires (brand tree fetch, name matching), rather than snapping to
 *  the result instantly. */
function FlowPlannerTextRow({ text, setText, onSend, thinking, placeholder }: {
  text: string; setText: (v: string) => void; onSend: () => void; thinking: boolean; placeholder: string;
}) {
  return (
    <div className="wiz-or-block">
      <div className="wiz-or-divider"><span>or</span></div>
      <form className="wiz-text-row" onSubmit={(e) => { e.preventDefault(); onSend(); }}>
        <input className="wiz-text-input" placeholder={placeholder} value={text} disabled={thinking}
          onChange={(e) => setText(e.target.value)} />
        <button type="submit" className="wiz-text-send" disabled={thinking || !text.trim()} aria-label="Send">
          <Icon name="arrowRight" size={15} />
        </button>
      </form>
      {thinking && <div className="wiz-thinking"><span /><span /><span /> Thinking&hellip;</div>}
    </div>
  );
}

/** A stable 0..1 value from a seed string, same idea as BrandOverview's own `seeded()` --
 *  used only to pick a consistent illustrative filler per brand, never anything that
 *  pretends to be a measured number. */
function seeded(seed: string): number {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  return (h % 1000) / 1000;
}

const ILLUSTRATIVE_COMPANIES = ["Aurelia Biosciences", "Meridian Therapeutics", "Northgate Pharma", "Solace Bio", "Vantree Sciences"];
const ILLUSTRATIVE_FOCUS = ["cardiometabolic disease", "oncology", "immunology", "neurology", "rare disease"];
const ILLUSTRATIVE_STAGE = ["pre-launch", "early launch", "in-market growth", "lifecycle expansion", "loss-of-exclusivity defense"];

/** A brand's picker detail card, filled in with a plausible illustrative placeholder
 *  wherever the real brand kit has nothing (several demo brands here have no company/
 *  generic/therapy area set) -- so the right pane is never left looking empty, and every
 *  filled-in field is tagged the same way the rest of this app marks placeholder content. */
function brandDetail(b: BrandSummary) {
  const real = Boolean(b.company || b.generic || b.therapy_area);
  const r = seeded(b.brand);
  const company = b.company || ILLUSTRATIVE_COMPANIES[Math.floor(r * ILLUSTRATIVE_COMPANIES.length)];
  const generic = b.generic || `${b.brand.toLowerCase()}umab — illustrative compound name`;
  const focus = b.therapy_area || ILLUSTRATIVE_FOCUS[Math.floor(seeded(b.brand + "focus") * ILLUSTRATIVE_FOCUS.length)];
  const stage = ILLUSTRATIVE_STAGE[Math.floor(seeded(b.brand + "stage") * ILLUSTRATIVE_STAGE.length)];
  const indication = b.indication || `A representative patient population in ${focus}.`;
  return { real, company, generic, focus, stage, indication };
}

type Step =
  | { kind: "ask-brand" }
  | { kind: "ask-engagement" }
  | { kind: "ask-campaign" }
  | { kind: "grounding" }
  | { kind: "ready" }
  | { kind: "stub"; message: string };

type PickerKind = "brand" | "engagement" | "campaign" | null;

const GROUNDING_LINES = [
  "Reading the campaign's brand kit and engagement plan context…",
  "Checking the SOP segmentation rules for this audience…",
  "Building the segmentation and journey regions…",
];

export function FlowPlannerPage() {
  const [step, setStep] = useState<Step>({ kind: "ask-brand" });
  const [picker, setPicker] = useState<PickerKind>(null);
  const [text, setText] = useState("");
  const [thinking, setThinking] = useState(false);
  const [readyCardOpen, setReadyCardOpen] = useState(true);
  const [editedMarkup, setEditedMarkup] = useState<string | null>(null);

  const [brands, setBrands] = useState<BrandSummary[] | null>(null);
  const [brand, setBrand] = useState<BrandSummary | null>(null);
  const [tree, setTree] = useState<BrandTree | null>(null);
  const [plan, setPlan] = useState<TreePlan | null>(null);
  const [campaign, setCampaign] = useState<TreeCampaign | null>(null);
  const [groundingLine, setGroundingLine] = useState(0);

  useEffect(() => { listBrands().then((r) => setBrands(r.brands)).catch(() => setBrands([])); }, []);

  useEffect(() => {
    if (step.kind !== "grounding") return;
    setGroundingLine(0);
    const id = setInterval(() => {
      setGroundingLine((i) => {
        if (i + 1 >= GROUNDING_LINES.length) {
          clearInterval(id);
          setTimeout(() => { setReadyCardOpen(true); setStep({ kind: "ready" }); }, 500);
        }
        return i + 1;
      });
    }, 700);
    return () => clearInterval(id);
  }, [step.kind]);

  const chooseBrandKind = (kind: "new" | "existing") => {
    if (kind === "new") { setStep({ kind: "stub", message: "New-brand flows aren't built yet -- pick an existing brand instead." }); return; }
    setPicker("brand");
  };
  const chooseEngagementKind = (kind: "new" | "existing") => {
    if (kind === "new") { setStep({ kind: "stub", message: "New-engagement flows aren't built yet -- pick an existing engagement plan instead." }); return; }
    setPicker("engagement");
  };
  const chooseCampaignKind = (kind: "existing" | "adhoc") => {
    if (kind === "adhoc") { setStep({ kind: "stub", message: "Ad-hoc campaign flows aren't built yet -- pick an existing campaign instead." }); return; }
    setPicker("campaign");
  };

  const onPickBrand = (b: BrandSummary) => {
    setBrand(b);
    setPicker(null);
    setTree(null);
    getBrandTree(b.brand).then(setTree).catch(() => setTree({ brand: b.brand, engagement_plans: [] }));
    setStep({ kind: "ask-engagement" });
  };
  const onPickPlan = (p: TreePlan) => {
    setPlan(p);
    setPicker(null);
    setStep({ kind: "ask-campaign" });
  };
  const onPickCampaign = (c: TreeCampaign) => {
    setCampaign(c);
    setPicker(null);
    setStep({ kind: "grounding" });
  };

  const restart = () => {
    setStep({ kind: "ask-brand" });
    setBrand(null); setTree(null); setPlan(null); setCampaign(null); setText(""); setThinking(false);
    setReadyCardOpen(true); setEditedMarkup(null);
  };

  const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

  /** Resolves as far forward as the typed text actually names -- brand, then (if the same
   *  text also names a real plan) engagement, then (if it also names a real campaign)
   *  campaign, landing straight on grounding when all three are there. Falls back to the
   *  matching picker popup the moment a level can't be resolved from the text alone. */
  const send = async () => {
    const raw = text.trim();
    if (!raw || thinking) return;
    const t = raw.toLowerCase();
    setText("");
    setThinking(true);
    await sleep(650);

    try {
      if (step.kind === "ask-brand") {
        if (t.includes("new")) { chooseBrandKind("new"); return; }
        const b = (brands ?? []).find((x) => t.includes(x.brand.toLowerCase()));
        if (!b) { setPicker("brand"); return; }
        setBrand(b);
        const bt = await getBrandTree(b.brand).catch(() => ({ brand: b.brand, engagement_plans: [] }) as BrandTree);
        setTree(bt);
        const p = bt.engagement_plans.find((x) => t.includes(x.name.toLowerCase()));
        if (!p) { setStep({ kind: "ask-engagement" }); return; }
        setPlan(p);
        const c = p.campaigns.find((x) => t.includes(x.name.toLowerCase()));
        if (!c) { setStep({ kind: "ask-campaign" }); return; }
        setCampaign(c);
        setStep({ kind: "grounding" });
      } else if (step.kind === "ask-engagement") {
        if (t.includes("new")) { chooseEngagementKind("new"); return; }
        const p = (tree?.engagement_plans ?? []).find((x) => t.includes(x.name.toLowerCase()));
        if (!p) { setPicker("engagement"); return; }
        setPlan(p);
        const c = p.campaigns.find((x) => t.includes(x.name.toLowerCase()));
        if (!c) { setStep({ kind: "ask-campaign" }); return; }
        setCampaign(c);
        setStep({ kind: "grounding" });
      } else if (step.kind === "ask-campaign") {
        if (t.includes("adhoc") || t.includes("ad-hoc") || t.includes("ad hoc")) { chooseCampaignKind("adhoc"); return; }
        const c = (plan?.campaigns ?? []).find((x) => t.includes(x.name.toLowerCase()));
        if (!c) { setPicker("campaign"); return; }
        setCampaign(c);
        setStep({ kind: "grounding" });
      }
    } finally {
      setThinking(false);
    }
  };

  const brandItems: PickerItem<BrandSummary>[] = (brands ?? []).map((b) => ({
    id: b.brand, title: b.brand, subtitle: b.indication || b.therapy_area, value: b,
  }));
  const planItems: PickerItem<TreePlan>[] = (tree?.engagement_plans ?? []).map((p) => ({
    id: String(p.id), title: p.name, subtitle: periodLabel(p.period_start, p.period_end) ?? p.status, value: p,
  }));
  const campaignItems: PickerItem<TreeCampaign>[] = (plan?.campaigns ?? []).map((c) => ({
    id: String(c.id), title: c.name, subtitle: `${c.status} · ${c.flow_count} flow${c.flow_count === 1 ? "" : "s"}`, value: c,
  }));

  return (
    <div className="hier-page flow-planner-page">
      <div className="hier-head">
        <div>
          <div className="kit-update-eyebrow">Agent Library</div>
          <h1 className="kit-update-title">Flow Planner</h1>
        </div>
      </div>

      {step.kind === "ready" && campaign && (
        <div className="flow-planner-canvas">
          <SopDiagramViewer alt="SOP segmentation + journey diagram" overrideMarkup={editedMarkup}
            src={`/api/campaigns/${campaign.id}/flow-sop/diagram.svg?audience=HCP`} />
          <FlowEditorChat campaignId={campaign.id} audience="HCP" onMarkup={setEditedMarkup} />
        </div>
      )}

      {/* Once the flow is ready, the card only covers the screen while the user hasn't
       *  dismissed it -- closing it (or it never opening a backdrop at all) leaves the
       *  diagram fully interactive, which a permanent full-page dim would otherwise block. */}
      {(step.kind !== "ready" || readyCardOpen) && <div className="plan-launcher-backdrop" />}
      {(step.kind !== "ready" || readyCardOpen) && (
      <div className="plan-launcher-card" role="dialog" aria-modal="true" aria-label="Flow Planner">
        {step.kind === "ready" && (
          <button type="button" className="plan-launcher-close" aria-label="Close" onClick={() => setReadyCardOpen(false)}>
            <Icon name="close" size={16} />
          </button>
        )}
        {step.kind === "ask-brand" && (
          <>
            <h3>Let&rsquo;s build a flow journey.</h3>
            <div className="wiz-choice-grid">
              <button type="button" className="wiz-choice-card" disabled={thinking} onClick={() => chooseBrandKind("new")}>
                <Icon name="sparkles" size={22} />
                <b>New brand</b>
                <span>Not built yet.</span>
              </button>
              <button type="button" className="wiz-choice-card" disabled={thinking} onClick={() => chooseBrandKind("existing")}>
                <Icon name="target" size={22} />
                <b>Existing brand</b>
                <span>Pick from your brand kits.</span>
              </button>
            </div>
            <FlowPlannerTextRow text={text} setText={setText} onSend={send} thinking={thinking}
              placeholder={`Or name a brand, e.g. "${brands?.[0]?.brand ?? "Cardiovex"}"`} />
          </>
        )}
        {step.kind === "ask-engagement" && (
          <>
            <h3>Grounded on {brand?.brand}.</h3>
            <div className="wiz-choice-grid">
              <button type="button" className="wiz-choice-card" disabled={thinking} onClick={() => chooseEngagementKind("new")}>
                <Icon name="sparkles" size={22} />
                <b>New engagement</b>
                <span>Not built yet.</span>
              </button>
              <button type="button" className="wiz-choice-card" disabled={thinking} onClick={() => chooseEngagementKind("existing")}>
                <Icon name="document" size={22} />
                <b>Existing engagement</b>
                <span>Pick from {brand?.brand}&rsquo;s plans.</span>
              </button>
            </div>
            <FlowPlannerTextRow text={text} setText={setText} onSend={send} thinking={thinking}
              placeholder={`Or name a plan, e.g. "${tree?.engagement_plans[0]?.name ?? "Q4 2026 Launch Push"}"`} />
          </>
        )}
        {step.kind === "ask-campaign" && (
          <>
            <h3>Under {plan?.name}.</h3>
            <div className="wiz-choice-grid">
              <button type="button" className="wiz-choice-card" disabled={thinking} onClick={() => chooseCampaignKind("existing")}>
                <Icon name="route" size={22} />
                <b>Existing campaign</b>
                <span>Pick from this plan&rsquo;s campaigns.</span>
              </button>
              <button type="button" className="wiz-choice-card" disabled={thinking} onClick={() => chooseCampaignKind("adhoc")}>
                <Icon name="zap" size={22} />
                <b>Ad-hoc campaign</b>
                <span>Not built yet.</span>
              </button>
            </div>
            <FlowPlannerTextRow text={text} setText={setText} onSend={send} thinking={thinking}
              placeholder={`Or name a campaign, e.g. "${plan?.campaigns[0]?.name ?? "Payer Access Follow-up"}"`} />
          </>
        )}
        {step.kind === "grounding" && (
          <>
            <h3>Building the flow&hellip;</h3>
            <div className="flow-planner-grounding">
              {GROUNDING_LINES.slice(0, groundingLine + 1).map((line, i) => <p key={i}>{line}</p>)}
            </div>
          </>
        )}
        {step.kind === "ready" && (
          <>
            <h3>Flow ready for {campaign?.name}.</h3>
            <p className="flow-planner-ready-hint">Close this card to pan and zoom the diagram.</p>
            <button type="button" className="wiz-big-btn" onClick={restart}>
              Start another flow <Icon name="arrowRight" size={16} />
            </button>
          </>
        )}
        {step.kind === "stub" && (
          <>
            <h3>{step.message}</h3>
            <button type="button" className="wiz-big-btn" onClick={restart}>
              Start over <Icon name="arrowRight" size={16} />
            </button>
          </>
        )}
      </div>
      )}

      {picker === "brand" && (
        <PickerModal title="Select a brand" items={brandItems} onSelect={onPickBrand} onClose={() => setPicker(null)}
          renderDetail={(b) => {
            const d = brandDetail(b);
            return (
              <div className="hier-detail-card">
                <div className="hier-detail-head">
                  <div><span className="hier-detail-name">{b.brand}</span></div>
                  {!d.real && <span className="illustrative-tag">Illustrative</span>}
                </div>
                <p className="hier-detail-summary">{d.indication}</p>
                <div className="hier-punch-card">
                  <span className="hier-punch-icon"><Icon name="target" size={18} /></span>
                  <div className="hier-punch-body">
                    <div className="hier-detail-subhead">Brand</div>
                    <p className="hier-objective-text">{d.company} · {d.generic}</p>
                  </div>
                </div>
                <div className="hier-punch-card">
                  <span className="hier-punch-icon"><Icon name="layers" size={18} /></span>
                  <div className="hier-punch-body">
                    <div className="hier-detail-subhead">Focus &amp; stage</div>
                    <p className="hier-objective-text">{d.focus}, {d.stage}</p>
                  </div>
                </div>
                <div>
                  <div className="hier-detail-subhead">Territories</div>
                  <p className="hier-detail-summary">
                    {b.territories.length > 0 ? b.territories.join(", ") : "Not yet configured for a territory."}
                  </p>
                </div>
              </div>
            );
          }} />
      )}
      {picker === "engagement" && (
        <PickerModal title={`Select an engagement plan in ${brand?.brand}`} items={planItems} onSelect={onPickPlan} onClose={() => setPicker(null)}
          renderDetail={(p) => (
            <div className="hier-detail-card">
              <div className="hier-detail-head"><div><span className="hier-detail-name">{p.name}</span></div></div>
              <p className="hier-detail-summary">{periodLabel(p.period_start, p.period_end) ?? "No period set"} · {p.status}</p>
              <p className="hier-detail-summary">{p.campaigns.length} campaign{p.campaigns.length === 1 ? "" : "s"}</p>
            </div>
          )} />
      )}
      {picker === "campaign" && (
        <PickerModal title={`Select a campaign in ${plan?.name}`} items={campaignItems} onSelect={onPickCampaign} onClose={() => setPicker(null)}
          renderDetail={(c) => (
            <div className="hier-detail-card">
              <div className="hier-detail-head"><div><span className="hier-detail-name">{c.name}</span></div></div>
              <p className="hier-detail-summary">{c.status} · {c.flow_count} flow{c.flow_count === 1 ? "" : "s"}</p>
            </div>
          )} />
      )}
    </div>
  );
}
