
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
  { id: "strategy", label: "Planning & Strategy", tagline: "Agents that build the brand's knowledge and plan, then turn each campaign into a briefing, a segment and a flow." },
  { id: "ops", label: "Operations & Orchestration", tagline: "Agents that build, check, test and launch the journeys and assets." },
  { id: "intelligence", label: "Reporting & Insights", tagline: "Agents that measure what happened and predict what to run next." },
];

/** Per-phase accent ink, applied to the active phase tab and the hero heading. */
export const PHASE_TINT: Record<Phase, string> = {
  strategy: "#3B4E8C",
  ops: "#206657",
  intelligence: "#6B4FA0",
};

export const AGENTS: Record<Phase, LibraryAgent[]> = {
  strategy: [
    {
      id: "brand-iq", name: "Brand IQ Agent", icon: "sparkles", status: "available",
      summary: "Builds the brand's knowledge base: brand plan, kit, Big Idea, personas, compliance and market intelligence.",
      about: "Reads the brand plan (or, with no plan, public FDA, NIH, PubMed, ClinicalTrials.gov and CDC sources) and proposes the Brand Kit: positioning, evidence, voice, competition, the Big Idea with its reasoning, US geography and client data. Every other agent reads from what it builds.",
      worksFrom: [
        { label: "Brand plan", detail: "An uploaded brand plan deck, when there is one." },
        { label: "Public sources", detail: "FDA label, Drugs@FDA, NIH MeSH, PubMed (US), ClinicalTrials.gov, MedlinePlus, CDC PLACES." },
        { label: "Company SOPs", detail: "config/compliance_profiles.json." },
      ],
      builtOn: "strategy/kit_proposer.py, strategy/brand_builder.py, strategy/public_sources.py, strategy/us_geography.py",
    },
    {
      id: "signal-agent", name: "Signal Scout", icon: "radar", status: "available",
      summary: "What changed in the market, and what should the team do? Signals, competitive landscape and actions.",
      about: "Reads the brand's Brand IQ, then runs nine skills in turn: market and treatment landscape, clinical evidence, competitive set, positioning, message territory, channel activity, signal synthesis, team actions and what changed since the last readout. US market only.",
      worksFrom: [
        { label: "Brand IQ", detail: "Label, clinical data, competitors, audiences, US geography and brand-plan fields." },
        { label: "Your focus", detail: "An optional question to steer the scan." },
        { label: "Previous readout", detail: "The last completed scan, so it can say what's new, persistent or resolved." },
      ],
      builtOn: "strategy/signal_scout.py",
    },
    {
      id: "brand-persona-builder", name: "Audience Segmentation Planner", icon: "persona", status: "available",
      summary: "Builds the brand's HCP and patient personas, shared by every campaign.",
      about: "Drafts HCP, patient and payer persona cards in the brand journey's Audience step (who they are, their tier, the voice that lands) and lets you refine one card by chat.",
      worksFrom: [
        { label: "Brand brief", detail: "Indication, primary audience and objective from the journey's Brief step." },
        { label: "Brand plan documents", detail: "Any plan you upload, read for audience and persona detail." },
        { label: "Persona library", detail: "The app's synthetic persona layer, for depth on drivers and channel preferences." },
      ],
      builtOn: "strategy/brand_journey.py, strategy/personas.py",
    },
    { id: "message-plan", name: "Message Plan", icon: "message", status: "wip", summary: "Builds the message house: core claim, pillars and proof points for each audience segment." },
    {
      id: "engagement-planner", name: "Engagement Planner", icon: "layers", status: "available",
      summary: "Plans the next 6 months for a brand: who to engage, what must change, which campaigns, when.",
      about: "Reads Brand IQ (the brand plan, kit, personas, compliance and market intelligence), asks only what's genuinely missing, reviews its assumptions with you, then drafts objectives, the audience-by-objective shift map, the campaign portfolio, a timeline and a relative budget. Each campaign opens the Campaign Planner.",
      worksFrom: [
        { label: "Brand IQ", detail: "The active brand plan, Brand Kit, Personas, Compliance Guardrails and Market Intelligence." },
        { label: "Industry framework", detail: "config/frameworks/engagement_<industry>.json (pharma, investment banking)." },
      ],
      builtOn: "strategy/engagement_agent.py, strategy/engagement_plans.py",
    },
    {
      id: "engagement-planner-2", name: "Engagement Planner 2", icon: "layers", status: "available",
      summary: "Runs the CampaignFlow framework: objective card, audience, channels, journeys, omnichannel rules and a build-ready brief.",
      about: "Reads the brand plan and Brand IQ, then runs the six CampaignFlow steps for one campaign. Each step reads only the approved step before it; you approve each draft or ask for changes. Gaps become questions, never inventions. Saving puts the campaign and its named journeys into Campaigns & Journeys and Live simulation.",
      worksFrom: [
        { label: "Brand plan", detail: "Uploaded documents and your notes, plus Brand IQ's brand-plan fields." },
        { label: "CampaignFlow framework", detail: "config/frameworks/campaignflow.json: the six steps and their 24 underlying rules." },
        { label: "Client data", detail: "Synthetic HCP counts, reach and field force until real feeds are connected." },
      ],
      builtOn: "strategy/campaignflow.py",
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
    // Card hidden (the agent and its route still work):
    // {
    //   id: "campaign-planner", name: "Campaign Planner", icon: "target", status: "available",
    //   summary: "Decides a campaign's objective, audience, messages, channels and timing, stage by stage.",
    //   about: "Walks the campaign decision spine (campaign frame through risks): pre-fills what the brand kit and campaign already say, recommends what it can, and asks only what only you know. Its plan feeds the Flow Planner and the Brief Compiler.",
    //   worksFrom: [
    //     { label: "Brand kit", detail: "Lifecycle, pillars, core claim, objective, competitors and targets." },
    //     { label: "Campaign decision spine", detail: "config/frameworks/campaign_spine.json (S0-S10)." },
    //   ],
    //   builtOn: "strategy/agent_forms.py, strategy/v3_artifacts.py",
    // },
    {
      id: "briefing-agent", name: "Campaign Agent", icon: "document", status: "available",
      summary: "Turns your campaign brief into an approved briefing document and a deployable Salesforce journey.",
      about: "Reads your brief, typed or uploaded, asks only about what's genuinely missing, reviews the remaining assumptions with you, and writes the Campaign Briefing Document. Once you approve it, seven agents (Document Analyst, Salesforce Architect, Flow QA Tester, Visual Designer, Tester Agent, Flow Validator and Technical Writer) build the Salesforce Flow specification and the journey diagram, ready to deploy to your org. Its briefing feeds the Flow Planner and the Brief Compiler.",
      worksFrom: [
        { label: "Your brief", detail: "Typed requirements or an uploaded PDF, DOCX, TXT or MD brief, plus your answers to the agent's questions." },
        { label: "Brand kit", detail: "The brand's indication, claims, safety reference and guardrails, when the brief is about this brand." },
        { label: "Salesforce org", detail: "The connected org's objects and fields (or the standard objects) for the flow, and the Metadata API for the deploy." },
      ],
      builtOn: "strategy/campaign_creator",
    },
    // Card hidden (the agent and its route still work):
    // {
    //   id: "brief-compiler", name: "Brief Compiler", icon: "document", status: "available",
    //   summary: "Turns the plan's decisions into a campaign brief an agency can execute.",
    //   about: "Writes the Campaign Strategy and Campaign Brief from the plan's decisions: purpose, audience rules, messaging, deliverables, measurement and risks. Every section names the decision it came from.",
    //   worksFrom: [
    //     { label: "Plan decisions", detail: "Each landed decision with its inputs, framework and rationale." },
    //     { label: "Measurement plan", detail: "The KPIs and targets the plan committed to." },
    //   ],
    //   builtOn: "strategy/campaign_artifacts.py",
    // },
    {
      id: "segmentation-planner", name: "Segmentation Agent", icon: "layers", status: "available",
      summary: "Turns a plain-English audience into a sized Salesforce Data Cloud segment.",
      about: "Describe the HCPs you want to reach. The agent asks which email consent statuses to include, writes the Data Cloud SQL on the HCP segmentation data, sizes the segment with a live count, and creates and publishes it in Data Cloud once you confirm. When Data Cloud rejects the SQL, its Tester Agent fixes it and tries again.",
      worksFrom: [
        { label: "Your request", detail: "The audience in your own words, plus the consent statuses you pick and the segment's name." },
        { label: "Data Cloud dataset", detail: "The HCP segmentation data model object's columns and their real values, read from Data Cloud." },
        { label: "Salesforce Data Cloud", detail: "The Query API for the record count and the Segments API to create and publish the segment." },
      ],
      builtOn: "strategy/segmentation",
    },
    {
      id: "flow-planner", name: "Flow Agent", icon: "route", status: "available",
      summary: "Walks brand → engagement plan → campaign, then builds the SOP segmentation + journey diagram.",
      about: "Opens on a blank canvas and asks, step by step, which brand, engagement plan and campaign to build a flow for, then generates the SOP-driven segmentation and journey diagram for it. It also drafts the channel-by-channel flow of sends, waits and decisions from the campaign's brief, audience and message ladder, and applies your changes as structured edits that survive a rebuild.",
      worksFrom: [
        { label: "Your picks", detail: "The brand, engagement plan and campaign you select as the agent asks." },
        { label: "SOP rules", detail: "The Flow Planner SOP's fixed segmentation and journey rules." },
        { label: "Message ladder", detail: "The message pillars, told in order across the sends." },
        { label: "Node catalogue", detail: "Send, wait, decision, follow-up and exit blocks, each with a stable code." },
      ],
      builtOn: "strategy/flow_sop, strategy/campaign_ops.py, strategy/brand_journey.py",
    },
  ],
  ops: [
    { id: "engagement-orchestration", name: "Intake Orchestrator", icon: "users", status: "wip", summary: "Takes in campaign requests and tracks the setup activity board, owners and deadlines." },
    {
      id: "journey-builder", name: "SFMC Journey Builder", icon: "branch", status: "available",
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
    { id: "mlr-review", name: "Content & MLR Review", icon: "eye", status: "wip", summary: "Pre-checks claims against the label and compliance guardrails before medical, legal and regulatory review." },
    { id: "litmus-test-agent", name: "Litmus Test Agent", icon: "flask", status: "wip", summary: "Checks emails render correctly across clients and devices before they go out." },
    { id: "ab-testing", name: "A/B Testing", icon: "zap", status: "wip", summary: "Designs the test, sizes the sample and calls the winner." },
  ],
  intelligence: [
    { id: "reporting-insights", name: "Reporting & Insights", icon: "barChart", status: "wip", summary: "Answers questions about campaign performance from the KPI scorecard." },
    { id: "predictive-campaigns", name: "Predictive Campaigns", icon: "sparkles", status: "wip", summary: "Forecasts campaign results and recommends what to run next, feeding the Engagement Planner." },
    { id: "hcp-360", name: "HCP 360", icon: "users", status: "wip", summary: "Answers questions about the HCP universe: who, where, how they prescribe and engage." },
  ],
};

/** The single agent registry the redesigned Cockpit reads (docs/redesign, F4): every agent
 *  once, tagged with its phase. AGENTS lists "flow-planner" under both Strategy and Ops;
 *  the Ops entry (the SOP segmentation + journey planner that actually exists) wins. */
export interface RegistryAgent extends LibraryAgent {
  phase: Phase;
  /** Where the agent opens today, when it has a working screen of its own. */
  route?: string;
  /** Home's card tags (B5). Only factual ones: NEW = built recently, COMING SOON = not
   *  built yet. POPULAR is left out until there is usage data to back it. */
  tags: ("new" | "coming-soon")[];
}

/** Agents with a redesigned workspace open there; the rest keep their current screen. */
const AGENT_ROUTES: Record<string, string> = {
  "brand-iq": "#/v3/agent/brand-iq",
  "signal-agent": "#/v3/agent/signal-agent",
  "engagement-planner": "#/v3/agent/engagement-planner",
  "engagement-planner-2": "#/v3/agent/engagement-planner-2",
  "campaign-planner": "#/v3/agent/campaign-planner",
  "segmentation-planner": "#/v3/agent/segmentation-planner",
  "flow-planner": "#/v3/agent/flow-planner",
  "briefing-agent": "#/v3/agent/briefing-agent",
  "brief-compiler": "#/v3/agent/brief-compiler",
};
const NEW_AGENTS = new Set(["engagement-planner-2", "engagement-planner", "campaign-planner", "segmentation-planner", "flow-planner", "briefing-agent", "brief-compiler"]);

export const REGISTRY: RegistryAgent[] = (() => {
  const byId = new Map<string, RegistryAgent>();
  for (const p of PHASES) {
    for (const a of AGENTS[p.id]) {
      // Launchable only when a real agent runs behind a screen of its own (AGENT_ROUTES).
      const comingSoon = a.status === "wip" || a.inDevelopment === true || !AGENT_ROUTES[a.id];
      byId.set(a.id, {
        ...a,
        phase: p.id,
        route: AGENT_ROUTES[a.id],
        tags: [...(NEW_AGENTS.has(a.id) ? ["new" as const] : []), ...(comingSoon ? ["coming-soon" as const] : [])],
      });
    }
  }
  return [...byId.values()];
})();
