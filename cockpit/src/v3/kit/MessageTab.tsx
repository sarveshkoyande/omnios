import { BigIdeaTile, Digest, Needs, Sec, Shell, Tbl, arr, txt, useKit, type Any, type PageProps } from "./shared";

/** Message & Voice: what we say, and how. */
export function MessageTab(props: PageProps) {
  const p = useKit(props.activeBrand, props.brands);
  return (
    <Shell tab="message" p={p}>{(k) => {
      const v = (k.voice ?? {}) as Any;
      const use = [...arr(v.vocabulary)];
      const avoid = Array.from(new Set([...arr(v.avoid).map(String), ...((k.voice_dont as string[] | undefined) ?? [])]));
      const doWords = ((k.voice_do as string[] | undefined) ?? []).filter((w) => !use.some((u) => txt(u.use) === w));
      return (<>
        <Sec id="positioning">{() => (
          <div className="v3-iq-posline two">
            <div><em>Positioning</em><Digest path="positioning_statement" text={k.positioning_statement} /></div>
            <div><em>Core claim</em><p>{txt(k.core_claim) || <Needs />}</p></div>
          </div>
        )}</Sec>

        <Sec id="bigidea" sub="Creative platform every campaign expresses">{() => <BigIdeaTile kit={k} p={p} />}</Sec>

        <Sec id="matrix" sub="Pillar → claim → proof">{() => (
          <Tbl rows={arr(k.message_hierarchy)} cols={[["pillar", "Pillar"], ["claim", "Claim"], ["evidence", "Proof"]]} />
        )}</Sec>

        <Sec id="bypersona">{() => (
          <Tbl rows={arr(k.messages_by_persona)} cols={[["persona", "Audience"], ["message", "Message"], ["existing", "Content we have"], ["to_develop", "Content to develop"]]} />
        )}</Sec>

        <Sec id="voice">{() => (<>
          <div className="v3-iq-voice-top">
            <div><em>Personality</em><b>{txt((k.brand_personification as Any | undefined)?.archetype) || "—"}</b>
              <div className="v3-iq-chips">{((k.tone_pillars as string[] | undefined) ?? []).map((t) => <span key={t}>{t}</span>)}</div></div>
            <div><em>Register</em><p>{txt(v.register) || <Needs />}</p></div>
            <div><em>Reading level</em><p>{txt(v.reading_level) || <Needs />}</p></div>
          </div>
          {arr(v.principles).length > 0 && (<>
            <h3 className="v3-iq-h3">Say this, not that</h3>
            <div className="v3-iq-saynot">
              {arr(v.principles).map((x) => (
                <article key={txt(x.principle)}>
                  <b>{txt(x.principle)}</b>
                  <p className="say"><span>Say</span>{txt(x.say)}</p>
                  <p className="not"><span>Not</span>{txt(x.not)}</p>
                </article>
              ))}
            </div>
          </>)}
          {arr(v.by_audience).length > 0 && (<>
            <h3 className="v3-iq-h3">Tone by audience</h3>
            <Tbl rows={arr(v.by_audience)} cols={[["audience", "Audience"], ["tone", "Tone"], ["focus", "Focus"]]} />
          </>)}
        </>)}</Sec>

        <Sec id="words">{() => (
          <div className="v3-iq-words">
            <div><em>Use</em>
              {use.length > 0 && <Tbl rows={use} cols={[["use", "Say"], ["instead_of", "Instead of"]]} />}
              {doWords.length > 0 && <div className="v3-iq-chips">{doWords.map((w) => <span key={w}>{w}</span>)}</div>}
            </div>
            <div><em>Never say</em>{avoid.length ? <div className="v3-iq-chips neg">{avoid.map((w) => <span key={w}>{w}</span>)}</div> : <Needs />}</div>
          </div>
        )}</Sec>
      </>);
    }}</Shell>
  );
}
