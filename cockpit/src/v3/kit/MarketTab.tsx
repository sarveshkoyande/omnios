import { useEffect, useState } from "react";
import { getClientData } from "../../api";
import { Digest, Needs, Sec, Shell, SiTag, SI_TONE, Tbl, arr, sourcesOf, txt, useKit, type Any, type PageProps } from "./shared";

/** Market: where we are winning and losing, and where the headroom is. */

const THREAT_TONE = (t: string) => (t.startsWith("High") ? "high" : t.startsWith("Medium") ? "med" : "low");

function UsGeography({ kit }: { kit: Any }) {
  const layers = arr((kit.us_geography as Any | undefined)?.layers);
  const [i, setI] = useState(0);
  const layer = layers[Math.min(i, layers.length - 1)];
  return (
    <Sec id="geo" foot={layer ? <a href={txt(layer.url)} target="_blank" rel="noreferrer">{txt(layer.source) || "CDC PLACES"} ↗</a> : null}>{() => {
      const states = arr(layer.states);
      const byCases = [...states].sort((a, b) => Number(b.est_cases) - Number(a.est_cases)).slice(0, 10);
      const maxCases = Math.max(1, ...byCases.map((s) => Number(s.est_cases)));
      const byRate = [...states].sort((a, b) => Number(b.prevalence_pct) - Number(a.prevalence_pct)).slice(0, 6);
      return (<>
        {layers.length > 1 && (
          <div className="v3-ep-tabs" style={{ marginBottom: 10 }}>
            {layers.map((l, j) => <button key={txt(l.measure)} type="button" className={j === i ? "active" : ""} onClick={() => setI(j)}>{txt(l.measure)}</button>)}
          </div>
        )}
        <div className="v3-iq-tf">
          <div>
            <em>Most adults affected (estimated)</em>
            <div className="v3-iq-hbars">
              {byCases.map((s) => <div key={txt(s.state)}><span>{txt(s.name)}</span><i style={{ width: `${(Number(s.est_cases) / maxCases) * 100}%` }} /><b>{(Number(s.est_cases) / 1000).toFixed(0)}k</b></div>)}
            </div>
          </div>
          <div>
            <em>Highest prevalence</em>
            {byRate.map((s) => <div key={txt(s.state)} className="v3-iq-ref"><code>{txt(s.state)}</code><div><b>{txt(s.prevalence_pct)}%</b><span>{txt(s.name)} · {txt(s.region)}</span></div></div>)}
          </div>
        </div>
      </>);
    }}</Sec>
  );
}

function ClientData({ brand }: { brand: string }) {
  const [d, setD] = useState<Any | null>(null);
  useEffect(() => { getClientData(brand).then(setD).catch(() => setD(null)); }, [brand]);
  return (
    <Sec id="clientdata" foot={d?.synthetic ? txt(d.note) : undefined}>{() => {
      if (!d) return <p className="v3-muted">Loading…</p>;
      const field = (d.field_force ?? {}) as Any;
      const segs = (d.hcps_by_segment ?? {}) as Record<string, Any>;
      return (<>
        <div className="v3-iq-stats">
          <div><em>Field force</em><b>{txt(field.reps)} reps</b><span>~{Number(field.capacity_calls_per_month).toLocaleString()} calls / month</span></div>
          <div><em>Market share by region</em><b className="sm">{Object.entries((d.market_share_pct_by_region ?? {}) as Record<string, number>).map(([r, v]) => `${r} ${v}%`).join(" · ")}</b></div>
        </div>
        <div className="v3-iq-dodont" style={{ marginTop: 12 }}>
          <div><h3 className="v3-iq-h3">HCPs by segment</h3><Tbl rows={Object.entries(segs).map(([name, v]) => ({ name, hcps: Number(v.hcps).toLocaleString(), top: Number(v.top3_deciles).toLocaleString() }))} cols={[["name", "Segment"], ["hcps", "HCPs"], ["top", "Top 3 deciles"]]} /></div>
          <div><h3 className="v3-iq-h3">Lowest formulary access</h3><Tbl rows={arr(d.lowest_access_states).map((x) => ({ ...x, u: `${x.unrestricted_pct}%`, pa: `${x.pa_required_pct}%` }))} cols={[["state", "State"], ["u", "Unrestricted"], ["pa", "Prior auth"]]} /></div>
        </div>
        <p className="v3-iq-note">Channel reach by segment is on the <a href="#/v3/iq/channels">Channels</a> tab.</p>
      </>);
    }}</Sec>
  );
}

export function MarketTab(props: PageProps) {
  const p = useKit(props.activeBrand, props.brands);
  return (
    <Shell tab="market" p={p}>{(k) => {
      const fc = k.forecast as { patients?: Record<string, number>; sales_meur?: Record<string, number>; source?: string } | undefined;
      const years = fc?.sales_meur ? Object.keys(fc.sales_meur) : [];
      const max = Math.max(1, ...years.map((y) => fc!.sales_meur![y]));
      const growth = arr(k.growth_opportunities);
      const ms = k.market_share as Any | undefined;
      return (<>
        <Sec id="situation" foot={sourcesOf(arr((k.brand_situation as Any)?.evidence))}>{() => {
          const bs = k.brand_situation as Any;
          return (<>
            <div className="v3-iq-facts">
              <div><em>Lifecycle</em><span>{txt(bs.lifecycle) || <Needs />}</span></div>
              <div><em>Therapy type</em><span>{txt(bs.archetype) || <Needs />}</span></div>
              <div><em>Access</em><span>{txt(bs.access) || <Needs />}</span></div>
            </div>
            {txt(bs.narrative) && <div style={{ marginTop: 10 }}><Digest path="brand_situation.narrative" text={bs.narrative} /></div>}
            {arr(bs.drivers).length + arr(bs.barriers).length > 0 && (
              <div className="v3-iq-dodont" style={{ marginTop: 10 }}>
                <div><h3 className="v3-iq-h3">Working for us</h3><ul className="v3-iq-bul">{arr(bs.drivers).map((x, i) => <li key={i}>{txt(typeof x === "object" ? (x as Any).point ?? (x as Any).text : x)}</li>)}</ul></div>
                <div><h3 className="v3-iq-h3">Working against us</h3><ul className="v3-iq-bul">{arr(bs.barriers).map((x, i) => <li key={i}>{txt(typeof x === "object" ? (x as Any).point ?? (x as Any).text : x)}</li>)}</ul></div>
              </div>
            )}
            {arr(bs.evidence).length > 0 && <ul className="v3-iq-bul" style={{ marginTop: 10 }}>{arr(bs.evidence).map((e, i) => <li key={i}>{txt(e.point)}</li>)}</ul>}
          </>);
        }}</Sec>

        <Sec id="flow" sub="Each figure checked as a match or a proxy">{() => arr(k.patient_flow).map((f) => (
          <div key={txt(f.indication_id)} style={{ marginBottom: 14 }}>
            <h3 className="v3-iq-h3">{txt(arr(k.indications).find((i) => i.id === f.indication_id)?.name) || txt(f.indication_id)}</h3>
            <ol className="v3-iq-funnel">
              {arr(f.stages).map((st) => (
                <li key={txt(st.stage)}>
                  <b>{st.value != null && st.value !== "" ? `${txt(st.value)} ${txt(st.unit)}` : "Gap"}</b>
                  <span>{txt(st.stage)}</span>
                  <small>{txt(st.what)}{st.verdict === "proxy" ? ` · proxy: ${txt(st.caveat)}` : ""}</small>
                  {st.url ? <a className="v3-iq-src" href={txt(st.url)} target="_blank" rel="noreferrer">{txt(st.source)} ↗</a> : <small className="v3-iq-src">{txt(st.source)}</small>}
                </li>
              ))}
            </ol>
          </div>
        ))}</Sec>

        <UsGeography kit={k} />

        <Sec id="competition" sub="Our brand first">{() => {
          const self = k.competition_self as Any | undefined;
          const cols = [...(self ? [{ ...self, _self: true }] : []), ...arr(k.competitors)];
          const rows: [string, string][] = [["type", "Type"], ["status", "Status"], ["strength", "Strength"], ["weakness", "Weakness"], ["counter", "How we win"], ["threat", "Threat"]];
          return (
            <div className="v3-iq-tablewrap">
              <table className="v3-iq-grid">
                <thead><tr><th />{cols.map((c) => <th key={txt(c.name)} className={c._self ? "self" : ""}>{txt(c.name)}</th>)}</tr></thead>
                <tbody>{rows.map(([f, l]) => (
                  <tr key={f}><th>{l}</th>{cols.map((c) => (
                    <td key={txt(c.name)} className={c._self ? "self" : ""}>
                      {f === "threat" ? (c._self ? "—" : <span className={`v3-iq-threat ${THREAT_TONE(txt(c.threat))}`} title={txt(c.threat_reason)}>{txt(c.threat) || "—"}{c.threat_status === "proposed" ? " · proposed" : ""}</span>)
                        : f === "counter" && c._self ? "—" : (txt(c[f] ?? (f === "counter" ? c.differentiation : "")) || <Needs />)}
                    </td>))}</tr>
                ))}</tbody>
              </table>
            </div>
          );
        }}</Sec>

        <Sec id="access" foot={txt((k.market_access as Any)?.source)}>{() => {
          const m = k.market_access as Any;
          return (
            <div className="v3-iq-access">
              <div><em>Value story</em><Digest path="market_access.value_story" text={m.value_story} /></div>
              <div><em>Access barriers</em><ul className="v3-iq-bul">{arr(m.barriers).map((b) => <li key={String(b)}>{String(b)}</li>)}</ul></div>
              <div><em>Launches</em><ul className="v3-iq-bul">{arr(m.launches).map((l) => <li key={txt(l.country)}><b>{txt(l.country)}</b> {txt(l.timing)}</li>)}</ul></div>
            </div>
          );
        }}</Sec>

        <Sec id="forecast" sub="M€ and patients" foot={txt(fc?.source)}>{() => (
          <div className="v3-iq-bars">
            {years.map((y) => (
              <div key={y} className="v3-iq-bar">
                <b>{fc!.sales_meur![y]}</b>
                <div style={{ height: `${(fc!.sales_meur![y] / max) * 140}px` }} />
                <span>{y}</span><small>{fc!.patients?.[y]?.toLocaleString()} pts</small>
              </div>
            ))}
          </div>
        )}</Sec>

        <Sec id="growth">{() => (<>
          <div className="v3-iq-split">
            {growth.map((g) => <div key={txt(g.id)} className={`v3-iq-si-${SI_TONE[txt(g.id)] ?? "other"}`} style={{ flex: parseFloat(txt(g.share)) || 1 }}><b>{txt(g.share)}</b><span>{txt(g.id)}</span></div>)}
          </div>
          <div className="v3-iq-split-legend">{growth.map((g) => <span key={txt(g.id)}><SiTag id={g.id} /> {txt(g.name)}{g.value ? ` · ${txt(g.value)}` : ""}</span>)}</div>
        </>)}</Sec>

        <Sec id="kpis" sub="Baseline → target" foot={sourcesOf(arr(k.kpis), "data_source")}>{() => (<>
          {(ms || txt(k.success_measure)) && (
            <div className="v3-iq-stats" style={{ marginBottom: 12 }}>
              <div><em>Market share</em><b>{ms ? txt(ms.current) : <Needs />}</b>{ms && <span>Target: {txt(ms.target)}</span>}</div>
              <div><em>Success measure</em><b className="sm">{txt(k.success_measure) || <Needs />}</b></div>
            </div>
          )}
          {arr(k.kpis).length > 0 && (
            <div className="v3-iq-kpis">
              {arr(k.kpis).map((x, i) => (
                <article key={i}>{Boolean(x.si) && <SiTag id={x.si} />}<b>{txt(x.kpi)}</b>
                  <span>{[txt(x.baseline) && `Now ${txt(x.baseline)}`, txt(x.target) && `Target ${txt(x.target)}`].filter(Boolean).join(" → ")}</span></article>
              ))}
            </div>
          )}
        </>)}</Sec>

        {p.brand && <ClientData brand={p.brand} />}

        <Sec id="proof" sub="Past campaigns" foot={sourcesOf(arr(k.proof_points))}>{() => (
          <div className="v3-iq-comp">{arr(k.proof_points).map((c) => (
            <article key={txt(c.name)}><div><b>{txt(c.name)}</b></div><p>{txt(c.result)}</p></article>
          ))}</div>
        )}</Sec>
      </>);
    }}</Shell>
  );
}
