import { GLOSSARY } from "@omni-frontend/glossary";

/** The Agent Library. Each card is kept to an icon, a name and one short line. The agents
 *  on the product list are "available" (they open a Read more page); every other agent the
 *  app already runs is shown as "wip". A Read more page only lists inputs the agent really
 *  uses in this codebase (`builtOn` names where); an agent that isn't built yet says so
 *  (`inDevelopment`) instead of showing invented activity. */
export type Phase = "strategy" | "ops" | "intelligence";

export type AgentIcon =
  | "target" | "radar" | "persona" | "layers" | "smartphone" | "route" | "document"
  | "branch" | "mail" | "flask" | "refresh" | "users" | "sparkles" | "wallet"
  | "star" | "palette" | "zap" | "eye" | "barChart" | "message";

export interface AgentInput {
  label: string;
  detail: string;
}

export interface LibraryAgent {
  id: string;
  name: string;
  icon: AgentIcon;
  /** The card line: one or two short sentences. */
  summary: string;
  status: "available" | "wip";
  /** Read more: what it does, in a few sentences. */
  about?: string;
  /** Read more: what it works from. */
  worksFrom?: AgentInput[];
  /** Where it runs in this codebase. */
  builtOn?: string;
  /** On the product list but not built yet. */
  inDevelopment?: boolean;
}

export interface PhaseInfo {
  id: Phase;
  label: string;
  tagline: string;
}

export const PHASES: PhaseInfo[] = [
  { id: "strategy", label: "Strategy & Planning", tagline: "Agents that turn a brief into a grounded, evidence-linked plan." },
  { id: "ops", label: "Ops", tagline: "Agents that turn the plan into journeys, assets and live segments." },
  { id: "intelligence", label: "Intelligence", tagline: "Agents that read the market, the HCP universe and the spend." },
];

export const AGENTS: Record<Phase, LibraryAgent[]> = {
  strategy: [
    {
      id: "engagement-plan-builder", name: "Engagement Plan Builder", icon: "target", status: "available",
      summary: "Builds a brand's engagement plan section by section, from brief to a reviewed, evidence-linked document.",
      about: `The shared planning engine behind every ${GLOSSARY.campaign_plan.label}. It takes the brief through chat, asks for what's missing, then composes the plan one section at a time, pausing at each decision for your answer.`,
      worksFrom: [
        { label: "Your brief", detail: "Brand, indication, lifecycle stage, audience, objective and budget, captured in the conversation." },
        { label: "Brand kit", detail: "The brand's approved message house, personas and guardrails." },
        { label: "Planning toolkit", detail: "The Customer Engagement Planning Toolkit's sections and the process knowledge behind them." },
      ],
      builtOn: "strategy/studio_run.py, strategy/orchestrator.py, strategy/plan_document.py",
    },
    {
      id: "signal-agent", name: "Signal Agent", icon: "radar", status: "available",
      summary: "Surfaces the market and competitive signals that should shape the plan.",
      about: "Pulls together what's known about the therapy area, the competitive set and where the brand sits in its lifecycle, so the plan starts from the market as it is.",
      worksFrom: [
        { label: "Brand kit competitors", detail: "The named competitors in the brand kit, with threat level and detail." },
        { label: "Market-intel store", detail: "Each brand's lifecycle-stage assessment, grounded in public market evidence." },
        { label: "External evidence", detail: "Public-knowledge lookups when the kit has no signal for a question." },
      ],
      builtOn: "strategy/brand_lifecycle.py, strategy/external_evidence.py",
    },
    {
      id: "brand-persona-builder", name: "Brand Persona Builder", icon: "persona", status: "available",
      summary: "Builds the brand's HCP and patient personas, shared by every campaign.",
      about: "Drafts HCP, patient and payer persona cards in the brand journey's Audience step (who they are, their tier, the voice that lands) and lets you refine one card by chat.",
      worksFrom: [
        { label: "Brand brief", detail: "Indication, primary audience and objective from the journey's Brief step." },
        { label: "Brand plan documents", detail: "Any plan you upload, read for audience and persona detail." },
        { label: "Persona library", detail: "The app's synthetic persona layer, for depth on drivers and channel preferences." },
      ],
      builtOn: "strategy/brand_journey.py, strategy/personas.py",
    },
    {
      id: "segmentation-planner", name: "Segmentation Planner", icon: "layers", status: "available",
      summary: "Sizes and chooses the HCP segments a campaign should lead with.",
      about: "Proposes segments inside your broad audience, sized against the addressable HCP universe, and asks which to lead with before the plan's targeting sections are written.",
      worksFrom: [
        { label: "HCP 360 panel", detail: "Specialty, geography, segment and prescribing data behind every audience count." },
        { label: "Target Customer Group template", detail: "The toolkit's ABCD segmentation, adoption ladder and digital-preference split." },
      ],
      builtOn: "strategy/segment_profile.py, strategy/hcp_panel_metrics.py",
    },
    {
      id: "channel-planner", name: "Channel Planner", icon: "smartphone", status: "available",
      summary: "Chooses the channel mix and budget split for how the campaign goes to market.",
      about: "Scores channels on purpose, availability, preference and potential, then offers go-to-market postures (field-led, event-led and so on), each with its own budget split.",
      worksFrom: [
        { label: "Channel Selection template", detail: "The toolkit's six named channels, scored by the channel-mix engine." },
        { label: "Your brief", detail: "The channels and budget you named, as the starting lean." },
      ],
      builtOn: "strategy/channel_selection.py, strategy/rules.py",
    },
    {
      id: "flow-planner", name: "Flow Planner", icon: "route", status: "available",
      summary: "Drafts the channel-by-channel flow for a campaign by rules, then edits it by chat.",
      about: "Builds a reproducible flow of sends, waits and decisions from the brand's confirmed brief, audience and message, and applies your changes as structured edits that survive a rebuild.",
      worksFrom: [
        { label: "Campaign snapshot", detail: "The brand content the campaign was built from." },
        { label: "Message ladder", detail: "The message pillars, told in order across the sends." },
        { label: "Node catalogue", detail: "Send, wait, decision, follow-up and exit blocks, each with a stable code." },
      ],
      builtOn: "strategy/campaign_ops.py, strategy/brand_journey.py",
    },
    {
      id: "briefing-agent", name: "Briefing Agent", icon: "document", status: "available",
      summary: "Turns the plan's decisions into a campaign brief an agency can execute.",
      about: "Writes the Campaign Strategy and Campaign Brief from the plan's decisions: purpose, audience rules, messaging, deliverables, measurement and risks. Every section names the decision it came from.",
      worksFrom: [
        { label: "Plan decisions", detail: "Each landed decision with its inputs, framework and rationale." },
        { label: "Measurement plan", detail: "The KPIs and targets the plan committed to." },
      ],
      builtOn: "strategy/campaign_artifacts.py",
    },
    { id: "plan-composer", name: "Plan Composer", icon: "document", status: "wip", summary: "Sequences the plan's sections and keeps them consistent as they land." },
    { id: "messaging-strategist", name: "Messaging Strategist", icon: "message", status: "wip", summary: "Turns positioning and proof points into a message hierarchy." },
    { id: "creative-inspiration", name: "Creative Inspiration", icon: "palette", status: "wip", summary: "Proposes creative concepts grounded in the brand kit." },
    { id: "activation-planner", name: "Activation Planner", icon: "zap", status: "wip", summary: "Converts the strategy into a tactical build order." },
  ],
  ops: [
    {
      id: "journey-builder", name: "Journey Builder", icon: "branch", status: "available",
      summary: "Builds and edits the live engagement journey diagram from plain-English instructions.",
      about: "Edits the Campaign Plan's journey diagram from what you tell it, and checks every change against the flowchart rules before saving it.",
      worksFrom: [
        { label: "Journey diagram", detail: "The campaign's current diagram, read as a compact graph." },
        { label: "Validation rules", detail: "The flow builder's flowchart rules, applied to every proposed edit." },
      ],
      builtOn: "strategy/tab_chat.py, frontend flow builder",
    },
    {
      id: "email-template-builder", name: "Email Template Builder", icon: "mail", status: "available", inDevelopment: true,
      summary: "Builds on-brand, compliant email templates for each send in a journey.",
      about: "Will assemble email templates for each send in a flow from the brand's approved message house and claims, in the brand's voice.",
      worksFrom: [
        { label: "Brand kit", detail: "Message house, approved claims, voice do's and don'ts." },
        { label: "Flow sends", detail: "Each email step in the campaign's flows." },
      ],
    },
    {
      id: "litmus-test-agent", name: "Litmus Test Agent", icon: "flask", status: "available", inDevelopment: true,
      summary: "Checks emails render correctly across clients and devices before they go out.",
      about: "Will run each email template through rendering checks across mail clients and devices, and report what breaks before launch.",
      worksFrom: [{ label: "Email templates", detail: "The templates the Email Template Builder produces." }],
    },
    {
      id: "segment-update-agent", name: "Segment Update Agent", icon: "refresh", status: "available", inDevelopment: true,
      summary: "Keeps campaign segments current as HCP data and engagement change.",
      about: "Will refresh each campaign's segment membership as the HCP panel and engagement data change, and flag shifts worth acting on.",
      worksFrom: [
        { label: "HCP 360 panel", detail: "The latest HCP data behind each segment." },
        { label: "Segment definitions", detail: "The segments each campaign was planned against." },
      ],
    },
    { id: "engagement-orchestration", name: "Engagement Orchestration", icon: "users", status: "wip", summary: "Tracks the setup activity board, owners and deadlines." },
  ],
  intelligence: [
    {
      id: "hcp-360", name: "HCP 360", icon: "users", status: "available",
      summary: "Answers questions about the HCP universe: who, where, how they prescribe and engage.",
      about: "A queryable panel of HCPs by specialty, state, segment, channel and brand. It's the source behind every audience number elsewhere in the app.",
      worksFrom: [{ label: "HCP 360 store", detail: "Demographics, channel affinity, prescribing and writer status per HCP." }],
      builtOn: "strategy/hcp_360.py",
    },
    {
      id: "nba-for-platform", name: "NBA for Platform", icon: "sparkles", status: "available", inDevelopment: true,
      summary: "Recommends the next best action for each HCP across channels.",
      about: "Will recommend each HCP's next best action (channel, message and timing) from their engagement history and the plan's rules.",
      worksFrom: [
        { label: "HCP 360 panel", detail: "Each HCP's channel affinity and engagement." },
        { label: "Campaign flows", detail: "The actions each campaign makes available." },
      ],
    },
    {
      id: "budget-agent", name: "Budget Agent", icon: "wallet", status: "available",
      summary: "Allocates the campaign budget across channels to match the plan's posture.",
      about: "Splits the campaign budget across channels, weighted by the chosen go-to-market posture and each channel's role in the plan.",
      worksFrom: [
        { label: "Your budget", detail: "The total budget from the brief." },
        { label: "Channel posture", detail: "The channel mix and weights the Channel Planner settled on." },
      ],
      builtOn: "strategy/autorun.py (budget allocation)",
    },
    { id: "reporting-insights", name: "Reporting & Insights", icon: "barChart", status: "wip", summary: "Answers questions about campaign performance from the KPI scorecard." },
    { id: "persona-review", name: "Persona Review", icon: "eye", status: "wip", summary: "Reads a finished plan back through each persona's eyes." },
    { id: "kpi-dashboard", name: "KPI Dashboard", icon: "star", status: "wip", summary: "Builds the scorecard, funnel and demographic cards." },
  ],
};
