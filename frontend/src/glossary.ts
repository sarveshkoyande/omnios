/**
 * The product's vocabulary (N-R1 in docs/brainstorms/2026-09-24-brand-campaign-ia-ideas-2-7-requirements.md):
 * one meaning per term. strategy/glossary.py is the backend's copy; scripts/verify_brand_hierarchy.py
 * checks the two stay identical. The cockpit imports this file through its @omni-frontend alias.
 */
export const GLOSSARY = {
  brand: { label: "Brand", definition: "The owning entity, with its brief and brand kit." },
  brand_kit: { label: "Brand kit", definition: "The brand's approved content: audiences, message house, compliance." },
  engagement_plan: { label: "Engagement Plan", definition: "A brand's programme of campaigns for a period, for example Q3 2026. A brand has many." },
  campaign: { label: "Campaign", definition: "One initiative inside an engagement plan." },
  campaign_plan: { label: "Campaign Plan", definition: "The phased planning document for one campaign. Optional." },
  flow: { label: "Flow", definition: "One channel-by-channel sequence inside a campaign. A campaign has many." },
} as const;

export type GlossaryKey = keyof typeof GLOSSARY;
