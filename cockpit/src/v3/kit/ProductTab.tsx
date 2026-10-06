import { useState } from "react";
import { refreshPublicSources } from "../../api";
import { Digest, LabelText, Lbl, Needs, Sec, Shell, Tbl, arr, needs, txt, useKit, type Any, type PageProps } from "./shared";

/** Product & Proof: what we can claim, and what backs it. */
export function ProductTab(props: PageProps) {
  const p = useKit(props.activeBrand, props.brands);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const refresh = () => {
    if (!p.brand) return;
    setRefreshing(true); setRefreshError(null);
    refreshPublicSources(p.brand).then((r) => p.setRaw(r.kit as unknown as Any))
      .catch((e) => setRefreshError(String(e))).finally(() => setRefreshing(false));
  };
  return (
    <Shell tab="product" p={p}>{(k) => {
      const pp = (k.product_profile ?? {}) as Record<string, Any>;
      const struct = (pp.structure?.value ?? null) as Any | null;
      const mesh = (pp.mesh_condition?.value ?? null) as Any | null;
      const approval = (pp.us_approval?.value ?? null) as Any | null;
      return (<>
        {refreshError && <p className="v3-iq-err">Couldn't refresh: {refreshError}</p>}
        <Sec id="profile" sub="FDA label, Drugs@FDA, NIH MeSH, PubChem"
          action={<button type="button" className="v3-iq-btn" onClick={refresh} disabled={refreshing}>{refreshing ? "Refreshing…" : "Refresh"}</button>}
          foot={Object.keys((pp.errors as Any) ?? {}).length ? `Didn't answer: ${Object.keys(pp.errors as Any).join(", ")}` : undefined}>{() => (<>
          <dl className="v3-iq-idfacts flat">
            <div><dt>Condition (NIH MeSH)</dt><dd>{mesh ? <>{txt(mesh.name)} <code>{txt(mesh.id)}</code></> : <Needs />}</dd></div>
            <div><dt>US approval</dt><dd>{approval?.date ? <>{txt(approval.date)} <code>{txt(approval.application)}</code></> : <Needs />}</dd></div>
          </dl>
          <div className="v3-iq-pp">
            <div className="v3-iq-pp-mol">
              <Lbl icon="flask">Molecule & structure</Lbl>
              {struct?.kind === "small_molecule" ? (<>
                <img src={txt(struct.image)} alt={`${txt(k.generic)} 2D structure`} />
                <p><b>{txt(struct.formula)}</b> · {txt(struct.weight)} g/mol</p>
              </>) : (<>
                <div className="v3-iq-bio">Biologic</div>
                <LabelText k={k} field="molecule_description" />
              </>)}
            </div>
            <div className="v3-iq-pp-grid">
              <div><Lbl icon="zap">How it works</Lbl><LabelText k={k} field="mechanism_of_action" /></div>
              <div><Lbl icon="check">Approved for</Lbl><LabelText k={k} field="indication" /></div>
              <div><Lbl icon="clock">Dosing & forms</Lbl><LabelText k={k} field="dosing" /></div>
            </div>
          </div>
        </>)}</Sec>

        <Sec id="indications" sub={`${arr(k.indications).length} on the label`}>{() => (
          <Tbl rows={arr(k.indications).map((i) => ({ ...i, line: i.line || "—", criteria: i.criteria || "—" }))} cols={[["name", "Indication"], ["population", "Population"], ["line", "Line / setting"], ["criteria", "Criteria"]]} />
        )}</Sec>

        <Sec id="label">{() => (<>
          <div className="v3-iq-label">
            <article className={needs(k.approved_indication) ? "missing" : "ok"}>
              <Lbl icon="check">Approved indication</Lbl>
              {needs(k.approved_indication) ? <p>Not captured yet — the agents won't check copy against it until it's added.</p> : <Digest path="approved_indication" text={k.approved_indication} />}
            </article>
            <article className={needs(k.safety_reference) ? "missing" : "ok"}>
              <Lbl icon="shield">Safety reference</Lbl>
              {needs(k.safety_reference) ? <p>Not captured yet.</p> : <Digest path="safety_reference" text={k.safety_reference} />}
            </article>
          </div>
          {Boolean(pp.warnings?.value) && (
            <div style={{ marginTop: 12 }}>
              <em className="v3-iq-kicker">{txt(pp.boxed_warning?.value).startsWith("No boxed") ? "Key safety · no boxed warning" : "Key safety · boxed warning"}</em>
              <LabelText k={k} field="warnings" />
            </div>
          )}
        </>)}</Sec>

        <Sec id="clinical">{() => (
          <Tbl rows={arr(k.clinical_data)} cols={[["study", "Study"], ["stat", "Result"], ["context", "Source"]]} />
        )}</Sec>

        <Sec id="references" sub="What claims may cite">{() => (
          <Tbl rows={arr(k.references).map((r) => ({ ...r, promo: r.promo_eligible ? "Promo eligible" : "Not for promo" }))} cols={[["id", "ID"], ["title", "Reference"], ["type", "Type"], ["key_data", "Key data"], ["promo", "Use"]]} />
        )}</Sec>
      </>);
    }}</Shell>
  );
}
