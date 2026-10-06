import { useEffect, useState } from "react";
import { getChannelPlaybook, getClientData } from "../../api";
import { Icon } from "../../components/Icon";
import { Bul, Lbl, Sec, Seg, Shell, SiTag, Tbl, arr, sourcesOf, txt, useKit, type Any, type IconName, type PageProps } from "./shared";

/** Channels: where and when we reach each audience. Two layers:
 *  - the best-practice framework (config/frameworks/channel_playbook.json): channel jobs by adoption stage,
 *    the playbook of channels, lifecycle mix, orchestration rules and measurement -- there for every brand;
 *  - the brand's own channel plan (the `channels` skill, built from the brand plan's activities, which win):
 *    strategy, mix by audience, journey, moments, plus the plan's committed activities.
 *  Where both exist, the brand's specifics sit inside the framework's cards. */

const ROLE_ORDER = ["awareness", "education", "conversion", "retention"];
const STAGES = ["launch", "growth", "mature", "loe"];
const WEIGHT_LABEL: Record<string, string> = { lead: "Lead", support: "Support", light: "Light" };

export function ChannelsTab(props: PageProps) {
  const p = useKit(props.activeBrand, props.brands);
  const [pb, setPb] = useState<Any | null>(null);
  const [reach, setReach] = useState<Record<string, Record<string, number>> | null>(null);
  const [aud, setAud] = useState("All");
  useEffect(() => { getChannelPlaybook().then(setPb).catch(() => setPb(null)); }, []);
  useEffect(() => {
    if (!p.brand) return;
    getClientData(p.brand).then((d) => setReach((d.channel_reach_pct ?? null) as Record<string, Record<string, number>> | null)).catch(() => setReach(null));
  }, [p.brand]);

  return (
    <Shell tab="channels" p={p}>{(k) => {
      const ch = (k.channels ?? {}) as Any;
      const mix = arr(ch.mix);
      const audiences = Array.from(new Set(mix.map((m) => txt(m.audience))));
      const moments = arr(ch.moments);
      const acts = arr(k.activities);
      const brandCards = arr(ch.cards);
      const stage = txt(ch.stage).toLowerCase();
      const pbChannels = arr(pb?.channels);
      const nameOf = (id: string) => txt(pbChannels.find((c) => c.id === id)?.name) || id;
      const iconOf = (id: string) => (txt(pbChannels.find((c) => c.id === id)?.icon) || "mail") as IconName;
      const brandCardFor = (c: Any) => brandCards.find((b) => txt(b.framework_id) === txt(c.id));
      const unmatched = brandCards.filter((b) => !pbChannels.some((c) => c.id === b.framework_id));
      const focus = arr(ch.ladder_focus);
      const shown = pbChannels.filter((c) => aud === "All" ? true : aud === "In the plan" ? Boolean(brandCardFor(c)) : txt(c.audience) === aud || txt(c.audience) === "Both");

      return (<>
        <Sec id="chstrategy" sub={stage ? `Lifecycle stage: ${txt(arr(pb?.lifecycle).find((l) => l.id === stage)?.name) || stage}` : undefined}>{() => (<>
          <Bul items={arr(ch.brief)} />
          {txt(ch.stage_why) && <p className="v3-iq-note">{txt(ch.stage_why)}</p>}
        </>)}</Sec>

        {pb && (
          <Sec id="chladder" sub="What each channel has to do as an HCP moves from aware to advocate" foot={txt(pb.source)}>{() => (
            <ol className="v3-iq-ladder">
              {arr(pb.ladder).map((r, i) => {
                const f = focus.find((x) => txt(x.rung) === txt(r.id));
                return (
                  <li key={txt(r.id)} className={f ? "focus" : ""}>
                    <header><span>{i + 1}</span><b>{txt(r.name)}</b></header>
                    <p>{txt(r.goal)}</p>
                    <Lbl icon="persona">HCP</Lbl>
                    <div className="v3-iq-mini">{arr(r.hcp).map((id) => <span key={String(id)}><Icon name={iconOf(String(id))} size={11} />{nameOf(String(id))}</span>)}</div>
                    <Lbl icon="heartPulse">Patient</Lbl>
                    <div className="v3-iq-mini">{arr(r.patient).map((id) => <span key={String(id)}><Icon name={iconOf(String(id))} size={11} />{nameOf(String(id))}</span>)}</div>
                    <Lbl icon="target">Success</Lbl>
                    <small>{txt(r.success)}</small>
                    {f && (
                      <div className="v3-iq-ladder-you">
                        <Lbl icon="users">Your segments here</Lbl>
                        <small>{arr(f.segments).map(String).join(" · ")}</small>
                        {txt(f.why) && <small className="why">{txt(f.why)}</small>}
                      </div>
                    )}
                  </li>
                );
              })}
            </ol>
          )}</Sec>
        )}

        <Sec id="chmix" sub="Colour shows the channel's job for that audience" foot={sourcesOf(mix)}>{() => (<>
          <div className="v3-iq-chmx">
            {audiences.map((a) => (
              <div key={a} className="v3-iq-chmx-row">
                <b>{a}</b>
                <div>{mix.filter((m) => txt(m.audience) === a)
                  .sort((x, y) => ROLE_ORDER.indexOf(txt(x.role).toLowerCase()) - ROLE_ORDER.indexOf(txt(y.role).toLowerCase()))
                  .map((m) => (
                    <span key={txt(m.channel)} className={`v3-iq-chip-role ${txt(m.role).toLowerCase()}`} title={txt(m.role)}>
                      {txt(m.channel)}{m.reach_pct != null && <small>{txt(m.reach_pct)}%</small>}
                    </span>
                  ))}</div>
              </div>
            ))}
          </div>
          <div className="v3-iq-rolelegend">{ROLE_ORDER.map((r) => <span key={r} className={`v3-iq-role ${r}`}>{r}</span>)}</div>
          {reach && Object.keys(reach).length > 0 && (<>
            <h3 className="v3-iq-h3">Reach by HCP segment <span className="v3-iq-srcbadge synthetic">Synthetic</span></h3>
            <Tbl rows={Object.entries(reach).map(([seg, r]) => ({ seg, ...Object.fromEntries(Object.entries(r).map(([c, v]) => [c, `${v}%`])) }))}
              cols={[["seg", "Segment"], ...Object.keys(Object.values(reach)[0] ?? {}).map((c) => [c, c] as [string, string])]} />
          </>)}
        </>)}</Sec>

        {pb && (
          <Sec id="chplaybook" sub={brandCards.length ? `${brandCards.length} in ${p.brand}'s plan` : "Best practice for each channel"}
            action={<Seg options={["All", "HCP", "Patient", ...(brandCards.length ? ["In the plan"] : [])]} value={aud} onChange={setAud} />}>{() => (<>
            <div className="v3-iq-chcards">
              {shown.map((c) => {
                const b = brandCardFor(c);
                const w = (c.lifecycle as Record<string, string> | undefined)?.[stage];
                return (
                  <article key={txt(c.id)} className={b ? "inplan" : ""}>
                    <header>
                      <span className="v3-iq-chcards-ic"><Icon name={(txt(c.icon) || "mail") as IconName} size={16} /></span>
                      <b>{txt(c.name)}</b>
                      <span className="v3-iq-chcards-tags">
                        <small className="aud">{txt(c.audience)}</small>
                        {b && <small className="plan">In plan</small>}
                        {w && <small className={`w ${w}`} title="For this brand's lifecycle stage">{WEIGHT_LABEL[w]}</small>}
                      </span>
                    </header>
                    <ul className="v3-iq-fields">
                      <li><Lbl icon="target">Use when</Lbl><span>{txt(c.use_when)}</span></li>
                      <li><Lbl icon="layers">Formats</Lbl><span>{arr(c.formats).map(String).join(" · ")}</span></li>
                      <li><Lbl icon="calendar">Cadence</Lbl><span>{txt(c.cadence)}</span></li>
                      <li><Lbl icon="barChart">Measure</Lbl><span>{arr(c.kpis).map(String).join(" · ")}</span></li>
                      <li className="warn"><Lbl icon="alertTriangle">Watch out</Lbl><span>{txt(c.watch_out)}</span></li>
                    </ul>
                    {b && (
                      <div className="v3-iq-chcards-brand">
                        <Lbl icon="document">For {p.brand}</Lbl>
                        <ul className="v3-iq-bul">
                          {txt(b.role) && <li><b>Job</b> {txt(b.role)}{arr(b.audiences).length ? ` · ${arr(b.audiences).map(String).join(", ")}` : ""}</li>}
                          {arr(b.formats).length > 0 && <li><b>Formats</b> {arr(b.formats).map(String).join(", ")}</li>}
                          {txt(b.cadence) && <li><b>Cadence</b> {txt(b.cadence)}</li>}
                          {txt(b.kpi) && <li><b>Watch</b> {txt(b.kpi)}</li>}
                          {txt(b.worked) && <li><b>Has worked</b> {txt(b.worked)}</li>}
                          {txt(b.rule) && <li><b>Rule</b> {txt(b.rule)}</li>}
                        </ul>
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
            {unmatched.length > 0 && aud !== "HCP" && aud !== "Patient" && (<>
              <h3 className="v3-iq-h3">Also in {p.brand}'s plan</h3>
              <div className="v3-iq-chcards">
                {unmatched.map((b) => (
                  <article key={txt(b.channel)} className="inplan">
                    <header><span className="v3-iq-chcards-ic"><Icon name="document" size={16} /></span><b>{txt(b.channel)}</b>
                      {txt(b.role) && <span className="v3-iq-chcards-tags"><small className="plan">{txt(b.role)}</small></span>}</header>
                    <ul className="v3-iq-fields">
                      {arr(b.formats).length > 0 && <li><Lbl icon="layers">Formats</Lbl><span>{arr(b.formats).map(String).join(" · ")}</span></li>}
                      {txt(b.cadence) && <li><Lbl icon="calendar">Cadence</Lbl><span>{txt(b.cadence)}</span></li>}
                      {txt(b.kpi) && <li><Lbl icon="barChart">Measure</Lbl><span>{txt(b.kpi)}</span></li>}
                      {txt(b.worked) && <li><Lbl icon="star">Has worked</Lbl><span>{txt(b.worked)}</span></li>}
                      {txt(b.rule) && <li className="warn"><Lbl icon="shield">Rule</Lbl><span>{txt(b.rule)}</span></li>}
                    </ul>
                  </article>
                ))}
              </div>
            </>)}
          </>)}</Sec>
        )}

        {pb && (
          <Sec id="chlife" sub={stage ? "Highlighted: this brand's stage" : "Which channels lead at each stage of a brand's life"}>{() => (<>
            <div className="v3-iq-tablewrap">
              <table className="v3-iq-life">
                <thead><tr><th>Channel</th>{arr(pb.lifecycle).map((l) => <th key={txt(l.id)} className={txt(l.id) === stage ? "now" : ""} title={txt(l.focus)}>{txt(l.name)}</th>)}</tr></thead>
                <tbody>{pbChannels.map((c) => (
                  <tr key={txt(c.id)}>
                    <td><Icon name={(txt(c.icon) || "mail") as IconName} size={13} /> {txt(c.name)} <small>{txt(c.audience)}</small></td>
                    {STAGES.map((s) => {
                      const w = txt((c.lifecycle as Any | undefined)?.[s]);
                      return <td key={s} className={s === stage ? "now" : ""}><i className={`v3-iq-dot ${w}`} title={WEIGHT_LABEL[w]} /></td>;
                    })}
                  </tr>
                ))}</tbody>
              </table>
            </div>
            <div className="v3-iq-lifelegend"><span><i className="v3-iq-dot lead" />Lead</span><span><i className="v3-iq-dot support" />Support</span><span><i className="v3-iq-dot light" />Light</span></div>
            <ul className="v3-iq-bul" style={{ marginTop: 10 }}>
              {arr(pb.lifecycle).map((l) => <li key={txt(l.id)} className={txt(l.id) === stage ? "now" : ""}><b>{txt(l.name)}</b> {txt(l.focus)}</li>)}
            </ul>
          </>)}</Sec>
        )}

        <Sec id="chjourney">{() => (
          <ol className="v3-iq-journey">
            {arr(ch.journey).map((j, i) => (
              <li key={i}>
                <span>{i + 1}</span><b>{txt(j.stage)}</b>
                <small className="v3-muted"> · {txt(j.audience)}</small>
                <div className="v3-iq-chips" style={{ marginTop: 6 }}>{arr(j.channels).map((c) => <span key={String(c)}>{String(c)}</span>)}</div>
                {txt(j.why) && <p>{txt(j.why)}</p>}
              </li>
            ))}
          </ol>
        )}</Sec>

        <Sec id="moments" foot={sourcesOf(moments)}>{() => (
          <ul className="v3-iq-moments">
            {moments.map((m, i) => (
              <li key={i}><time>{txt(m.when)}</time><b>{txt(m.name)}</b><small>{txt(m.type)}</small></li>
            ))}
          </ul>
        )}</Sec>

        <Sec id="activities" sub={`${acts.length} in the brand plan`} foot={sourcesOf(acts)}>{() => (
          <div className="v3-iq-tablewrap">
            <table className="v3-iq-table">
              <thead><tr><th>Activity</th><th>Channel</th><th>Audience</th><th>When</th></tr></thead>
              <tbody>{acts.map((a, i) => (
                <tr key={i}><td>{Boolean(a.si) && <><SiTag id={a.si} /> </>}{txt(a.activity || a.name)}</td><td>{txt(a.channel)}</td><td>{txt(a.audience)}</td><td>{txt(a.timing)}</td></tr>
              ))}</tbody>
            </table>
          </div>
        )}</Sec>

        {pb && (
          <Sec id="chorch" sub="How the channels work together">{() => (
            <div className="v3-iq-rules">
              {arr(pb.orchestration).map((r, i) => (
                <article key={i}><span>{i + 1}</span><div><b>{txt(r.rule)}</b><p>{txt(r.detail)}</p></div></article>
              ))}
            </div>
          )}</Sec>
        )}

        {pb && (
          <Sec id="chmeasure" sub="From reach to business result">{() => (
            <ol className="v3-iq-measure">
              {arr(pb.measurement).map((m) => (
                <li key={txt(m.level)}>
                  <b>{txt(m.level)}</b>
                  <p>{txt(m.question)}</p>
                  <small>{arr(m.metrics).map(String).join(" · ")}</small>
                </li>
              ))}
            </ol>
          )}</Sec>
        )}
      </>);
    }}</Shell>
  );
}
