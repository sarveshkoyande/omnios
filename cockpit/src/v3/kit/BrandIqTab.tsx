import { useContext } from "react";
import { Icon } from "../../components/Icon";
import {
  KitCtx, Needs, Sec, Shell, SiTag, SI_TONE, TABS, Tbl, arr, at, filled, needs, sectionsOf, sourcesOf, txt, useKit,
  Digest, Lbl, type Any, type IconName, type PageProps,
} from "./shared";

/** Brand IQ: the brand on a page. Identity, the one-page brief (problem → watch-outs), unmet need,
 *  objectives, the current plan, and how complete each tab of the kit is. */

const ONE_PAGE: [string, string, IconName][] = [
  ["problem", "Problem", "alertTriangle"], ["objective", "Objective", "target"], ["audience", "Audience", "users"], ["message", "Message", "message"],
  ["channels", "Channels", "megaphone"], ["proof", "Proof", "flask"], ["watch_outs", "Watch-outs", "shield"],
];

/** Each tile: the model's condensed line when the briefs exist, else the kit field it rests on. */
function onAPage(k: Any): Record<string, string> {
  const op = (at(k, "context.on_a_page") ?? {}) as Any;
  const acts = arr(k.activities);
  const chans = Array.from(new Set([...arr(at(k, "channels.cards")).map((c) => txt(c.channel)), ...acts.map((a) => txt(a.channel))].filter(Boolean))).slice(0, 4);
  const fallback: Record<string, string> = {
    problem: txt(at(k, "unmet_need.summary")) || (typeof k.unmet_need === "string" ? txt(k.unmet_need) : ""),
    objective: txt(arr(k.key_objectives)[0]?.objective) || (needs(k.key_objective) ? "" : txt(k.key_objective)),
    audience: needs(k.primary_audience) ? "" : txt(k.primary_audience),
    message: txt(k.core_claim) || txt(k.tagline),
    channels: chans.join(" · "),
    proof: txt(arr(k.clinical_data)[0]?.stat),
    watch_outs: txt(arr(at(k, "guardrails.donts"))[0]?.text),
  };
  return Object.fromEntries(ONE_PAGE.map(([id]) => [id, txt(op[id]) || fallback[id]]));
}

function Completeness() {
  const kit = useContext(KitCtx);
  return (
    <section className="v3-iq-complete" aria-label="How complete the kit is">
      {TABS.filter((t) => t.id !== "brandiq").map((t) => {
        const secs = sectionsOf(t.id).filter(([, d]) => typeof d.keys !== "string");
        const have = secs.filter(([, d]) => filled(kit, d.keys)).length;
        const pct = secs.length ? Math.round((have / secs.length) * 100) : 100;
        return (
          <a key={t.id} href={`#/v3/${t.route}`} className={pct === 100 ? "full" : pct < 50 ? "low" : ""}>
            <span className="v3-iq-complete-top"><Icon name={t.icon} size={13} />{t.title}</span>
            <i><s style={{ width: `${pct}%` }} /></i>
            <small>{secs.length ? `${have} of ${secs.length} sections` : "Company SOPs"}</small>
          </a>
        );
      })}
    </section>
  );
}

export function BrandIqTab(props: PageProps) {
  const p = useKit(props.activeBrand, props.brands);
  return (
    <Shell tab="brandiq" p={p}>{(k) => {
      const pp = (k.product_profile ?? {}) as Record<string, Any>;
      const mesh = (pp.mesh_condition?.value ?? null) as Any | null;
      const approval = (pp.us_approval?.value ?? null) as Any | null;
      const plan = k.plan_meta as Any | null;
      const sis = arr(k.strategic_imperatives);
      const fc = k.forecast as { sales_meur?: Record<string, number> } | undefined;
      const years = fc?.sales_meur ? Object.keys(fc.sales_meur) : [];
      const maxSale = Math.max(1, ...years.map((y) => fc!.sales_meur![y]));
      const objectives = arr(k.key_objectives);
      const page = onAPage(k);
      return (<>
        <section className="v3-iq-profile v3-iq-id2">
          <div className="v3-iq-profile-id">
            <div className="v3-iq-profile-mark">{txt(p.brand).slice(0, 1)}</div>
            <div>
              <h2>{p.brand}</h2>
              <p>{needs(k.generic) ? <Needs what="generic" /> : txt(k.generic)}</p>
              <div className="v3-iq-profile-tags">
                {!needs(k.company) && <span>{txt(k.company)}</span>}
                {!needs(k.lifecycle_stage) && <span className="stage">{txt(k.lifecycle_stage)}</span>}
                {!needs(k.therapy_area) && <span>{txt(k.therapy_area)}</span>}
                {arr(k.territories).length > 0 && <span>{(k.territories as string[]).join(" · ")}</span>}
              </div>
            </div>
          </div>
          <dl className="v3-iq-idfacts">
            <div><dt>Indication</dt><dd>{needs(k.indication) ? <Needs /> : txt(k.indication)}</dd></div>
            <div><dt>Condition</dt><dd>{mesh ? txt(mesh.name) : <Needs />}</dd></div>
            <div><dt>US approval</dt><dd>{approval?.date ? txt(approval.date) : <Needs />}</dd></div>
            <div><dt>Labeler</dt><dd>{txt(pp.labeler?.value) || <Needs />}</dd></div>
          </dl>
        </section>

        <section className="v3-iq-onpage" aria-label="The brand on a page">
          {ONE_PAGE.map(([id, label, icon]) => (
            <article key={id} className={id === "watch_outs" ? "watch" : ""}>
              <Lbl icon={icon}>{label}</Lbl>
              <p>{page[id] || <Needs />}</p>
            </article>
          ))}
        </section>

        <Completeness />

        <Sec id="unmet" foot={sourcesOf(arr(at(k, "unmet_need.facts")))}>{() => {
          const u = (typeof k.unmet_need === "string" ? { summary: k.unmet_need } : k.unmet_need) as Any;
          return (<>
            <Digest path="unmet_need.summary" text={u.summary} />
            {arr(u.facts).length > 0 && (
              <div className="v3-iq-factrow">
                {arr(u.facts).map((f) => (<div key={txt(f.label)} title={txt(f.source)}><b>{txt(f.value)}</b><span>{txt(f.label)}</span></div>))}
              </div>
            )}
            {arr(u.gaps).length > 0 && <Tbl rows={arr(u.gaps)} cols={[["gap", "Gap"], ["detail", "What happens today"], ["who", "Who it affects"]]} />}
          </>);
        }}</Sec>

        <Sec id="objectives" foot={sourcesOf(objectives)}>{() => objectives.length ? (
          <ol className="v3-iq-objlist">
            {objectives.map((o, i) => (
              <li key={i}>
                <b>{txt(o.objective)}</b>
                <span>{[txt(o.measure), txt(o.target_date) && `by ${txt(o.target_date)}`].filter(Boolean).join(" · ")}</span>
                {txt(o.priority) && <small>{txt(o.priority)}</small>}
              </li>
            ))}
          </ol>
        ) : <p className="v3-iq-lede">{txt(k.key_objective)}</p>}</Sec>

        {plan && (
          <Sec id="plan" sub={`${txt(plan.name)} · ${txt(plan.scope)}`}>{() => (<>
            <div className="v3-iq-si-grid">
              {sis.map((si) => (
                <article key={txt(si.id)} className={`v3-iq-si-card v3-iq-si-${SI_TONE[txt(si.id)] ?? "other"}`}>
                  <SiTag id={si.id} />
                  <h3>{txt(si.imperative)}</h3>
                  <ul className="v3-iq-bul">
                    {txt(si.segment) && <li><b>Who</b> {txt(si.segment)}</li>}
                    {txt(si.driver) && <li><b>Driver</b> {txt(si.driver)}</li>}
                    {txt(si.barrier) && <li><b>Barrier</b> {txt(si.barrier)}</li>}
                  </ul>
                </article>
              ))}
            </div>
            {years.length > 0 && (
              <div className="v3-iq-plangrow">
                <em>Growth frame</em>
                <div className="v3-iq-profile-nums"><b>{fc!.sales_meur![years[0]]}</b><span>→</span><b>{fc!.sales_meur![years[years.length - 1]]}</b><small>M€ · {years[0]}–{years[years.length - 1]}</small></div>
                <div className="v3-iq-spark">{years.map((y) => <i key={y} title={`${y}: ${fc!.sales_meur![y]} M€`} style={{ height: `${(fc!.sales_meur![y] / maxSale) * 100}%` }} />)}</div>
                <small>Forecast, growth split and KPIs are on the <a href="#/v3/iq/market">Market</a> tab</small>
              </div>
            )}
          </>)}</Sec>
        )}
      </>);
    }}</Shell>
  );
}
