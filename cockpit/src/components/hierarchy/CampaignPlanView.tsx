import type { TreeCampaign } from "../../types";

/** The Campaign Plan inside the Cockpit (KTD10): the frontend/ workspace for the campaign's
 *  project, framed under the Cockpit's breadcrumb until it is ported. */
export function CampaignPlanView({ campaign }: { campaign: TreeCampaign }) {
  if (!campaign.project_id) {
    return <div className="hier-page"><div className="jc-empty">This campaign has no Campaign Plan yet.</div></div>;
  }
  return (
    <iframe className="campaign-plan-frame" title={`${campaign.name} — Campaign Plan`}
      src={`/campaign-plan-view?project=${encodeURIComponent(campaign.project_id)}&embed=1`} />
  );
}
