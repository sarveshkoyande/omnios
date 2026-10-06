import { useEffect, useState } from "react";
import { getCompliance } from "../../api";
import { Needs, Sec, Seg, Shell, Src, Tbl, arr, txt, useKit, type Any, type PageProps } from "./shared";

/** Compliance: what every campaign must respect. Company SOPs come from the compliance profile; the
 *  brand's do and don't from the kit. Label & safety is on Product & Proof. */
export function ComplianceTab(props: PageProps) {
  const p = useKit(props.activeBrand, props.brands);
  const [cp, setCp] = useState<Any | null | undefined>(undefined);
  const [sopAud, setSopAud] = useState("DTC");
  const [supAud, setSupAud] = useState("DTC");
  useEffect(() => {
    if (!p.brand) return;
    setCp(undefined);
    getCompliance(p.brand).then((r) => setCp(r.profile as Any | null)).catch(() => setCp(null));
  }, [p.brand]);
  return (
    <Shell tab="compliance" p={p}>{(k) => {
      const g = (k.guardrails ?? {}) as { dos?: Any[]; donts?: Any[] };
      const sops = arr(cp?.campaign_sops);
      const sop = sops.find((s) => s.audience === sopAud) ?? sops[0];
      const sup = ((cp?.suppressions ?? {}) as Record<string, Any>)[supAud];
      const wf = arr((cp?.approval_workflow as Any | undefined)?.steps);
      return (<>
        <Sec id="dodont" sub="From the label">{() => (
          <div className="v3-iq-dodont">
            <div>{g.dos?.length ? g.dos.map((r, i) => <div key={i} className="v3-iq-rule do"><span>✓</span><div><em>{txt(r.category)}</em><p>{txt(r.text)}</p></div></div>) : <Needs />}</div>
            <div>{g.donts?.length ? g.donts.map((r, i) => <div key={i} className="v3-iq-rule dont"><span>✕</span><div><em>{txt(r.category)}</em><p>{txt(r.text)}</p></div></div>) : <Needs />}</div>
          </div>
        )}</Sec>
        <p className="v3-iq-note">Label & safety and references are on <a href="#/v3/iq/product">Product & Proof</a>; words to use and avoid on <a href="#/v3/iq/message">Message & Voice</a>.</p>

        {cp === undefined ? <p className="v3-empty">Loading compliance profile…</p> : cp === null ? (
          <div className="v3-iq-banner warn"><b>No company SOPs assigned to {p.brand}.</b> Upload the company's campaign SOPs to fill this part.</div>
        ) : (<>
          {cp.status === "template" && <div className="v3-iq-banner warn"><b>Template: {txt(cp.company)} SOPs.</b> {txt(cp.status_note)}</div>}

          <Sec id="approval" sub="Medical, legal, regulatory review" foot={txt((cp.approval_workflow as Any | undefined)?.source)}>{() => (
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

          <Sec id="chrules">{() => <Tbl rows={arr(cp.channel_rules)} cols={[["channel", "Channel"], ["rule", "Rule"], ["source", "Source"]]} />}</Sec>

          {arr(cp.regulatory_baseline).length > 0 && (
            <Sec id="regs" sub="Public regulations every campaign must respect">{() => (
              <div className="v3-iq-tablewrap">
                <table className="v3-iq-table">
                  <thead><tr><th>Regulation</th><th>Region</th><th>What it requires</th><th>Reference</th></tr></thead>
                  <tbody>{arr(cp.regulatory_baseline).map((r) => (
                    <tr key={txt(r.name)}><td>{txt(r.name)}</td><td>{txt(r.region)}</td><td>{txt(r.what)}</td>
                      <td><a href={txt(r.url)} target="_blank" rel="noreferrer">{txt(r.ref)} ↗</a></td></tr>
                  ))}</tbody>
                </table>
              </div>
            )}</Sec>
          )}
        </>)}
      </>);
    }}</Shell>
  );
}
