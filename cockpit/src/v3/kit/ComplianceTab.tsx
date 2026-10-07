import { useEffect, useState } from "react";
import { getCompliance, getCompliancePlaybook } from "../../api";
import { Icon } from "../../components/Icon";
import { Bul, Lbl, Needs, Sec, Seg, Shell, Src, Tbl, arr, txt, useKit, type Any, type IconName, type PageProps } from "./shared";

/** Compliance: what every campaign must respect. Three layers, in priority order:
 *  - the brand: do and don't from the label, and a claim check drafted for MLR (the `compliance` skill);
 *  - the company's SOPs (config/compliance_profiles.json), when the brand has them;
 *  - the best-practice framework (config/frameworks/compliance_playbook.json): claims & fair balance, rules by
 *    channel, the review cycle, data & consent, adverse events and the regulations -- there for every brand.
 *  Label & safety is on Product & Proof. */

const VERDICT: Record<string, { label: string; icon: IconName }> = {
  ok: { label: "Looks fine", icon: "check" }, caution: { label: "Caution", icon: "alertTriangle" }, risk: { label: "Risk", icon: "close" },
};

export function ComplianceTab(props: PageProps) {
  const p = useKit(props.activeBrand, props.brands);
  const [cp, setCp] = useState<Any | null | undefined>(undefined);
  const [pb, setPb] = useState<Any | null>(null);
  const [sopAud, setSopAud] = useState("DTC");
  const [supAud, setSupAud] = useState("DTC");
  const [chFilter, setChFilter] = useState("All");
  useEffect(() => { getCompliancePlaybook().then(setPb).catch(() => setPb(null)); }, []);
  useEffect(() => {
    if (!p.brand) return;
    setCp(undefined);
    getCompliance(p.brand).then((r) => setCp(r.profile as Any | null)).catch(() => setCp(null));
  }, [p.brand]);
  return (
    <Shell tab="compliance" p={p}>{(k) => {
      const g = (k.guardrails ?? {}) as { dos?: Any[]; donts?: Any[] };
      const cc = (k.compliance_check ?? {}) as Any;
      const notes = arr(cc.channel_notes);
      const noteFor = (id: string) => notes.find((n) => txt(n.channel_id) === id);
      const inPlan = new Set(arr((k.channels as Any | undefined)?.cards).map((c) => txt(c.framework_id)).filter(Boolean));
      const sops = arr(cp?.campaign_sops);
      const sop = sops.find((s) => s.audience === sopAud) ?? sops[0];
      const sup = ((cp?.suppressions ?? {}) as Record<string, Any>)[supAud];
      const wf = arr((cp?.approval_workflow as Any | undefined)?.steps);
      const pbChannels = arr(pb?.channels).filter((c) => chFilter === "All" ? true : chFilter === "In the plan" ? inPlan.has(txt(c.id)) || Boolean(noteFor(txt(c.id))) : true);
      const regs = arr(cp?.regulatory_baseline).length ? arr(cp?.regulatory_baseline) : arr(pb?.regulations);
      return (<>
        <Sec id="dodont" sub="From the label">{() => (
          <div className="v3-iq-dodont">
            <div>{g.dos?.length ? g.dos.map((r, i) => <div key={i} className="v3-iq-rule do"><span>✓</span><div><em>{txt(r.category)}</em><p>{txt(r.text)}</p></div></div>) : <Needs />}</div>
            <div>{g.donts?.length ? g.donts.map((r, i) => <div key={i} className="v3-iq-rule dont"><span>✕</span><div><em>{txt(r.category)}</em><p>{txt(r.text)}</p></div></div>) : <Needs />}</div>
          </div>
        )}</Sec>

        <Sec id="claimcheck" sub="A first read for MLR, not an approval" foot={txt(cc.generated_at) ? `Drafted by Omni ${txt(cc.generated_at)} from the FDA label and this kit` : undefined}>{() => (<>
          <ul className="v3-iq-claims">
            {arr(cc.claim_checks).map((c, i) => {
              const v = VERDICT[txt(c.verdict)] ?? VERDICT.caution;
              return (
                <li key={i} className={txt(c.verdict) || "caution"}>
                  <span className="v"><Icon name={v.icon} size={12} />{v.label}</span>
                  <div>
                    <small>{txt(c.where)}</small>
                    <p>“{txt(c.claim)}”</p>
                    {txt(c.why) && <span className="why">{txt(c.why)}</span>}
                    {txt(c.fix) && <span className="fix"><b>Try:</b> {txt(c.fix)}</span>}
                  </div>
                </li>
              );
            })}
          </ul>
          {arr(cc.key_risks).length > 0 && (
            <div className="v3-iq-keyrisks">
              <Lbl icon="alertTriangle">Risks fair balance must carry</Lbl>
              <Bul items={arr(cc.key_risks)} />
            </div>
          )}
        </>)}</Sec>

        {pb && (
          <Sec id="cmpclaims" sub="Every claim, every piece">{() => (
            <div className="v3-iq-rules">
              {arr(pb.claims).map((r, i) => <article key={i}><span>{i + 1}</span><div><b>{txt(r.rule)}</b><p>{txt(r.detail)}</p></div></article>)}
            </div>
          )}</Sec>
        )}

        {pb && (
          <Sec id="cmpchannels" sub={notes.length ? `With notes for ${p.brand}` : "What each channel must respect"} foot={txt(pb.source)}
            action={notes.length || inPlan.size ? <Seg options={["All", "In the plan"]} value={chFilter} onChange={setChFilter} /> : undefined}>{() => (
            <div className="v3-iq-chcards">
              {pbChannels.map((c) => {
                const n = noteFor(txt(c.id));
                return (
                  <article key={txt(c.id)} className={n || inPlan.has(txt(c.id)) ? "inplan" : ""}>
                    <header>
                      <span className="v3-iq-chcards-ic"><Icon name={(txt(c.icon) || "mail") as IconName} size={16} /></span>
                      <b>{txt(c.name)}</b>
                      {inPlan.has(txt(c.id)) && <span className="v3-iq-chcards-tags"><small className="plan">In plan</small></span>}
                    </header>
                    <ul className="v3-iq-bul">{arr(c.rules).map((r) => <li key={String(r)}>{String(r)}</li>)}</ul>
                    {n && <div className="v3-iq-chcards-brand"><Lbl icon="document">For {p.brand}</Lbl><span className="v3-iq-note-sm">{txt(n.note)}</span></div>}
                    <small className="v3-iq-refs"><Icon name="link" size={11} />{txt(c.refs)}</small>
                  </article>
                );
              })}
            </div>
          )}</Sec>
        )}

        {pb && (
          <Sec id="cmpcycle" sub="From brief to withdrawal">{() => (
            <ol className="v3-iq-flow">
              {arr(pb.review_cycle).map((s, i) => (
                <li key={txt(s.step)}><span>{i + 1}</span><b>{txt(s.step)}</b><small>{txt(s.owner)}</small><p>{txt(s.what)}</p></li>
              ))}
            </ol>
          )}</Sec>
        )}

        {cp === undefined ? <p className="v3-empty">Loading company SOPs…</p> : cp === null ? (
          <div className="v3-iq-banner warn"><b>No company SOPs assigned to {p.brand}.</b> The best practice on this page applies until the company's SOPs are uploaded.</div>
        ) : (<>
          {cp.status === "template" && <div className="v3-iq-banner warn"><b>Template: {txt(cp.company)} SOPs.</b> {txt(cp.status_note)}</div>}

          <Sec id="approval" sub="The company's MLR workflow" foot={txt((cp.approval_workflow as Any | undefined)?.source)}>{() => (
            <ol className="v3-iq-flow">
              {wf.map((s, i) => (
                <li key={txt(s.step)}><span>{i + 1}</span><b>{txt(s.step)}</b><small>{txt(s.owner)}{s.sla && s.sla !== "—" ? ` · ${txt(s.sla)}` : ""}</small><p>{txt(s.what)}</p></li>
              ))}
            </ol>
          )}</Sec>

          <Sec id="prelaunch" sub="Every campaign, before it goes live">{() => (
            <ul className="v3-iq-check">
              {arr(cp.prelaunch_checklist).map((c) => <li key={txt(c.item)}><span>✓</span><div><p>{txt(c.item)}</p><small>{txt(c.source)}</small></div></li>)}
            </ul>
          )}</Sec>

          <Sec id="sops" sub={arr(cp.documents).map((d) => `${txt(d.id)} ${txt(d.version)}`).join(" · ")}>{() => (<>
            <Seg options={sops.map((s) => txt(s.audience))} value={txt(sop?.audience)} onChange={setSopAud} />
            {sop && (
              <div className="v3-iq-sop">
                <div className="v3-iq-sop-head">
                  <b>{txt(sop.name)}</b>
                  <span>Applies when: {txt(sop.applies_when)}</span>
                </div>
                <ol className="v3-iq-steps">
                  {arr(sop.steps).map((s) => <li key={txt(s.n)}><span>{txt(s.n)}</span><div><b>{txt(s.title)}</b><p>{txt(s.rule)}</p></div></li>)}
                </ol>
                {arr(sop.open_items).length > 0 && (
                  <div className="v3-iq-open"><em>Open items in this SOP</em><ul>{arr(sop.open_items).map((o) => <li key={String(o)}>{String(o)}</li>)}</ul></div>
                )}
                <Src s={sop.source} />
              </div>
            )}
          </>)}</Sec>

          <Sec id="eligibility" sub="Checked in this order before anyone enters a flow" foot={txt(sup?.source)}>{() => (<>
            <Seg options={Object.keys((cp.suppressions ?? {}) as Any)} value={supAud} onChange={setSupAud} />
            {sup ? <div style={{ marginTop: 12 }}><Tbl rows={arr(sup.rules).map((r, i) => ({ ...r, n: i + 1 }))} cols={[["n", "#"], ["check", "Check"], ["code", "Where it comes from"], ["why", "Why"]]} /></div> : <Needs />}
          </>)}</Sec>

          <Sec id="chrules" sub="The company's own channel rules">{() => <Tbl rows={arr(cp.channel_rules)} cols={[["channel", "Channel"], ["rule", "Rule"], ["source", "Source"]]} />}</Sec>
        </>)}

        {pb && (
          <Sec id="cmpdata">{() => (
            <div className="v3-iq-rules">
              {arr(pb.data_privacy).map((r, i) => <article key={i}><span>{i + 1}</span><div><b>{txt(r.rule)}</b><p>{txt(r.detail)}</p></div></article>)}
            </div>
          )}</Sec>
        )}

        {pb && (
          <Sec id="cmpae" sub="Pharmacovigilance across every channel">{() => (
            <div className="v3-iq-rules">
              {arr(pb.adverse_events).map((r, i) => <article key={i}><span>{i + 1}</span><div><b>{txt(r.rule)}</b><p>{txt(r.detail)}</p></div></article>)}
            </div>
          )}</Sec>
        )}

        {regs.length > 0 && (
          <Sec id="regs" sub={arr(cp?.regulatory_baseline).length ? "From the company's profile" : "US regulations every campaign must respect"}>{() => (
            <div className="v3-iq-tablewrap">
              <table className="v3-iq-table">
                <thead><tr><th>Regulation</th><th>What it requires</th><th>Reference</th></tr></thead>
                <tbody>{regs.map((r) => (
                  <tr key={txt(r.name)}><td><b>{txt(r.name)}</b></td><td>{txt(r.what)}</td>
                    <td>{r.url ? <a href={txt(r.url)} target="_blank" rel="noreferrer">{txt(r.ref) || "Open"} ↗</a> : txt(r.ref)}</td></tr>
                ))}</tbody>
              </table>
            </div>
          )}</Sec>
        )}

        <p className="v3-iq-note">Label & safety and references are on <a href="#/v3/iq/product">Product & Proof</a>. Best practice here is guidance, not legal advice: the company's SOPs and MLR decide.</p>
      </>);
    }}</Shell>
  );
}
