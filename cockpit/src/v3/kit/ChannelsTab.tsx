import { useEffect, useState } from "react";
import { getClientData } from "../../api";
import { Bul, Sec, Shell, SiTag, Tbl, arr, at, sourcesOf, txt, useKit, type Any, type PageProps } from "./shared";

/** Channels: where and when we reach each audience. Built by the `channels` skill from the brand plan's
 *  activities (source of truth), the client reach data (synthetic), proof points and compliance rules. */

const ROLE_ORDER = ["awareness", "education", "conversion", "retention"];

export function ChannelsTab(props: PageProps) {
  const p = useKit(props.activeBrand, props.brands);
  const [reach, setReach] = useState<Record<string, Record<string, number>> | null>(null);
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
      return (<>
        <Sec id="chstrategy">{() => <Bul items={arr(ch.brief)} />}</Sec>

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

        <Sec id="chcards" foot={sourcesOf(arr(ch.cards))}>{() => (
          <div className="v3-iq-chcards">
            {arr(ch.cards).map((c) => (
              <article key={txt(c.channel)}>
                <header><b>{txt(c.channel)}</b>{txt(c.role) && <span className={`v3-iq-role ${txt(c.role).toLowerCase()}`}>{txt(c.role)}</span>}</header>
                {arr(c.audiences).length > 0 && <small className="v3-iq-chcards-aud">{arr(c.audiences).map(String).join(" · ")}</small>}
                <ul className="v3-iq-bul">
                  {arr(c.formats).length > 0 && <li><b>Formats</b> {arr(c.formats).map(String).join(", ")}</li>}
                  {txt(c.cadence) && <li><b>Cadence</b> {txt(c.cadence)}</li>}
                  {txt(c.kpi) && <li><b>Watch</b> {txt(c.kpi)}</li>}
                  {txt(c.worked) && <li><b>Has worked</b> {txt(c.worked)}</li>}
                </ul>
                {txt(c.rule) && <p className="v3-iq-chcards-rule">{txt(c.rule)}</p>}
              </article>
            ))}
          </div>
        )}</Sec>

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
        {!at(k, "channels.generated_at") && acts.length > 0 && <p className="v3-iq-note">The channel view is built from these activities — use "Draft it" under Still needed.</p>}
      </>);
    }}</Shell>
  );
}
