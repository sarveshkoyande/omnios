import { useState } from "react";
import { refreshAudienceSources } from "../../api";
import { Icon } from "../../components/Icon";
import { Bul, Lbl, Needs, Sec, Shell, SiTag, Src, Tbl, arr, at, txt, useKit, type Any, type PageProps } from "./shared";

/** Audiences: who we are talking to and what moves them. */

function PersonaCard({ x }: { x: Any }) {
  const sis = arr(x.si).map(String);
  return (
    <article className="v3-iq-pcard">
      <header>
        <div className="v3-iq-avatar">{txt(x.name).slice(0, 1)}</div>
        <div className="v3-iq-pcard-title">
          <h3>{txt(x.name)}</h3>
          <span>{txt(x.specialties || x.who)}</span>
        </div>
        {Boolean(x.tier) && <span className={`v3-iq-tier ${txt(x.tier).toLowerCase()}`}>{txt(x.tier)}</span>}
      </header>
      {Boolean(x.voice) && <blockquote title="Illustrative">“{txt(x.voice)}”</blockquote>}
      {sis.length > 0 && <div className="v3-iq-persona-si"><Icon name="target" size={12} />Targeted by {sis.map((s) => <SiTag key={s} id={s} />)}</div>}
      <div className="v3-iq-pcard-grid">
        <div><Lbl icon="eye">How they behave</Lbl>{arr(x.behaviours).length ? <Bul items={arr(x.behaviours)} max={3} /> : <Needs />}</div>
        <div>
          <Lbl icon="alertTriangle">What holds them back</Lbl><p>{txt(x.barrier) || <Needs />}</p>
          <Lbl icon="clock">Moment that matters</Lbl><p>{txt(x.moment) || <Needs />}</p>
        </div>
      </div>
      <div className="v3-iq-pcard-msg">
        <Lbl icon="message">Key message</Lbl><p>{txt(x.key_message) || <Needs />}</p>
        {txt(x.tone) && <div className="v3-iq-pcard-row"><span className="v3-iq-lblrow"><Icon name="mic" size={12} /><b>Tone</b> {txt(x.tone)}</span></div>}
      </div>
      <Src s={x.source} />
    </article>
  );
}

export function AudiencesTab(props: PageProps) {
  const p = useKit(props.activeBrand, props.brands);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const refresh = () => {
    if (!p.brand) return;
    setBusy(true); setErr(null);
    refreshAudienceSources(p.brand).then((r) => p.setRaw(r.kit as unknown as Any)).catch((e) => setErr(String(e))).finally(() => setBusy(false));
  };
  return (
    <Shell tab="audiences" p={p}>{(k) => {
      const ps = (k.personas ?? {}) as { hcp?: Any[]; patient?: Any[]; caregiver?: Any[] };
      const stages = arr(at(k, "care_continuum.stages"));
      const ai = (k.audience_intel ?? null) as Record<string, Any> | null;
      const kol = ai?.kol_publications?.value as Any | undefined;
      const tf = ai?.trial_footprint?.value as Any | undefined;
      const pr = arr(ai?.patient_resources?.value);
      const maxPapers = Math.max(1, ...arr(kol?.authors).map((a) => Number(a.papers)));
      const maxSites = Math.max(1, ...arr(tf?.sites_by_country).map((c) => Number(c.sites)));
      const refreshBtn = <button type="button" className="v3-iq-btn" onClick={refresh} disabled={busy}>{busy ? "Refreshing…" : "Refresh"}</button>;
      return (<>
        <div className="v3-iq-aud-summary">
          <div><Icon name="users" size={16} /><b>{ps.hcp?.length ?? 0}</b><span>HCP personas</span></div>
          <div><Icon name="heartPulse" size={16} /><b>{(ps.patient?.length ?? 0) + (ps.caregiver?.length ?? 0)}</b><span>Patient & caregiver</span></div>
          <div><Icon name="star" size={16} /><b>{arr(kol?.authors).length || "—"}</b><span>Opinion leaders</span></div>
          <div><Icon name="map" size={16} /><b>{arr(tf?.sites_by_country).length || "—"}</b><span>Countries with trial sites</span></div>
        </div>
        {txt(k.primary_audience) && !txt(k.primary_audience).startsWith("Needs input") && <p className="v3-iq-lede"><b>Primary audience:</b> {txt(k.primary_audience)}</p>}
        {err && <p className="v3-iq-err">Couldn't refresh: {err}</p>}

        <Sec id="segments" sub="On the adoption ladder">{() => (
          <Tbl rows={arr(k.audience_segments)} cols={[["name", "Segment"], ["who", "Who"], ["ladder_rung", "Ladder rung"], ["ladder_reason", "Why that rung"]]} />
        )}</Sec>

        <Sec id="hcp" sub={`${ps.hcp?.length ?? 0} personas`}>{() => (
          <div className="v3-iq-pcards">{(ps.hcp ?? []).map((x) => <PersonaCard key={txt(x.name)} x={x} />)}</div>
        )}</Sec>

        <Sec id="patients">{() => (
          <div className="v3-iq-pcards">{[...(ps.patient ?? []), ...(ps.caregiver ?? [])].map((x) => <PersonaCard key={txt(x.name)} x={x} />)}</div>
        )}</Sec>

        <Sec id="journey">{() => (
          <ol className="v3-iq-journey">
            {stages.map((s, i) => (<li key={i}><span>{i + 1}</span><b>{txt(s.stage)}</b><p>{txt(s.patient)}</p></li>))}
          </ol>
        )}</Sec>

        <Sec id="kols" sub="Most-published, last 6 years" action={refreshBtn}
          foot={<a href={txt(ai?.kol_publications?.url)} target="_blank" rel="noreferrer">PubMed · {txt(kol?.papers_scanned)} papers scanned · {txt(ai?.kol_publications?.fetched_at)} ↗</a>}>{() => (
          <div className="v3-iq-tablewrap">
            <table className="v3-iq-table">
              <thead><tr><th>Author</th><th>Papers</th><th>Most recent</th></tr></thead>
              <tbody>{arr(kol!.authors).map((a) => (
                <tr key={txt(a.author)}>
                  <td>{txt(a.author)}</td>
                  <td className="v3-iq-barcell"><i style={{ width: `${(Number(a.papers) / maxPapers) * 100}%` }} /><span>{txt(a.papers)}</span></td>
                  <td><a href={txt(a.url)} target="_blank" rel="noreferrer">{txt(a.latest_title)}</a> <small>({txt(a.latest_year)})</small></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}</Sec>

        <Sec id="treaters" sub="Trial sites" foot={<a href={txt(ai?.trial_footprint?.url)} target="_blank" rel="noreferrer">{txt(tf?.studies)} studies · ClinicalTrials.gov ↗</a>}>{() => (
          <div className="v3-iq-tf">
            <div className="v3-iq-hbars">
              {arr(tf!.sites_by_country).slice(0, 10).map((c) => (
                <div key={txt(c.country)}><span>{txt(c.country)}</span><i style={{ width: `${(Number(c.sites) / maxSites) * 100}%` }} /><b>{txt(c.sites)}</b></div>
              ))}
            </div>
            <div>
              <Lbl icon="persona">Principal investigators</Lbl>
              {arr(tf!.investigators).length ? arr(tf!.investigators).map((i) => (
                <div key={txt(i.nct)} className="v3-iq-ref"><code>{txt(i.nct)}</code><div><b>{txt(i.name)}</b><span>{txt(i.affiliation)}</span></div></div>
              )) : <p className="v3-iq-note">Most trials list a sponsor contact rather than a named investigator.</p>}
            </div>
          </div>
        )}</Sec>

        <Sec id="education" foot="MedlinePlus, National Library of Medicine · patient advocacy groups are added by hand">{() => (
          <ul className="v3-iq-bul">{pr.map((r) => <li key={txt(r.url)}><a href={txt(r.url)} target="_blank" rel="noreferrer">{txt(r.title)} ↗</a></li>)}</ul>
        )}</Sec>
      </>);
    }}</Shell>
  );
}
