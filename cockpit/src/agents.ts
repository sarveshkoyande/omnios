/** The agent library -- called out explicitly per leadership direction: "the workspace
 *  structure should make the underlying capabilities understandable," not just expose one
 *  orchestrator agent behind a chat. Three workspaces, as described: Strategy & Planning,
 *  Ops / Orchestration, Intelligence & Optimization.
 *
 *  Every entry here is a real, already-built capability in this codebase -- not a roadmap
 *  wishlist. Sources: strategy/orchestrator.py's AGENT_ROSTER, strategy/tab_chat.py's
 *  STAGE_AGENTS (also frontend/src/workspace/types.ts), strategy/hcp_360.py's ask(),
 *  strategy/persona_review.py, strategy/campaign_ops.py, strategy/reporting_insights.py.
 *  Only the Campaign Operations agent can write app state (it edits the campaign flow
 *  WorkflowDocument); every other agent here is grounded, read-only Q&A -- shown as a
 *  visible property on the card rather than left implicit. */

export type Phase = "strategy" | "ops" | "intelligence";

export interface AgentSource {
  label: string;
  detail: string;
}

export interface AgentEntry {
  id: string;
  name: string;
  job: string;
  detail: string;
  access: "read" | "write";
  source: string;
  /** "Read more" detail page: a plausible, internally-consistent recent-activity log and
   *  a breakdown of what the agent actually grounds its answers/edits in. Illustrative
   *  (not live telemetry -- there's no activity-logging store behind this yet), but each
   *  entry is built strictly from what this agent's real job/detail/source above already
   *  establishes -- never invented capability the agent doesn't have. */
  activity: string[];
  sources: AgentSource[];
}

export interface PhaseInfo {
  id: Phase;
  label: string;
  tagline: string;
}

export const PHASES: PhaseInfo[] = [
  { id: "strategy", label: "Strategy & Planning", tagline: "Turns a brief into a grounded, evidence-linked plan." },
  { id: "ops", label: "Ops & Orchestration", tagline: "Turns the plan into a live, running journey." },
  { id: "intelligence", label: "Intelligence & Optimization", tagline: "Watches performance and answers what's actually happening." },
];

export const AGENTS: Record<Phase, AgentEntry[]> = {
  strategy: [
    {
      id: "planning",
      name: "Campaign Planning & Strategy Agent",
      job: "Holds the conversation that builds your Brand Engagement Plan",
      detail: "The one you actually talk to during Stage 1 -- takes your brief, asks what's missing, and narrates the plan as it's composed.",
      access: "read",
      source: "strategy/tab_chat.py -- STAGE_AGENTS.planning",
      activity: [
        "Asked for the target persona after the brand and therapy area were confirmed",
        "Summarized the emerging message hierarchy back to the user for confirmation",
        "Flagged a missing objective figure and asked for it before continuing",
      ],
      sources: [
        { label: "Conversation intake", detail: "The user's own answers so far -- brand, therapy area, persona, objective." },
        { label: "Saved plan snapshot", detail: "The project's plan_markdown as composed so far, so it doesn't re-ask what's already answered." },
        { label: "Prior tab-chat history", detail: "Earlier turns in this same planning conversation, for continuity across the session." },
      ],
    },
    {
      id: "planner",
      name: "Planner",
      job: "Sequences the plan section by section",
      detail: "Owns the run order -- decides what gets composed next and keeps the whole plan internally consistent as sections land.",
      access: "read",
      source: "strategy/orchestrator.py -- AGENT_ROSTER",
      activity: [
        "Sequenced Brand foundation before Message hierarchy since positioning has to land first",
        "Held Activation back until Strategy's message pillars were approved",
        "Re-ordered two sections after an earlier draft failed a phase gate",
      ],
      sources: [
        { label: "AGENT_ROSTER task queue", detail: "The fixed run order agents compose sections in, and each section's declared dependencies." },
        { label: "Phase gate state", detail: "Which phase (align/select/create/deploy) has been human-approved so far." },
        { label: "Section grounding context", detail: "The same process_grounding/external_evidence/audience_profile context every section-writing agent reads from." },
      ],
    },
    {
      id: "intel",
      name: "Intel",
      job: "Gathers the market and competitive picture",
      detail: "Pulls together what's known about the therapy area, the competitive set, and where this brand sits in its lifecycle.",
      access: "read",
      source: "strategy/orchestrator.py -- AGENT_ROSTER",
      activity: [
        "Pulled the current lifecycle stage from the market-intel store and flagged a Growth-vs-Launch mismatch",
        "Compiled the named competitor set with each one's stated threat level",
        "Cross-checked market-share language against the brand's two configured territories",
      ],
      sources: [
        { label: "Brand kit competitors", detail: "config/brand_kits.json's named competitor list -- name, threat, and detail per entry." },
        { label: "Market-intel store", detail: "strategy/brand_lifecycle.py's per-brand lifecycle-stage assessment, grounded in public market evidence." },
        { label: "External evidence", detail: "strategy/external_evidence.py's public-knowledge lookups when the kit has no signal for a question." },
      ],
    },
    {
      id: "strategy-agent",
      name: "Strategy",
      job: "Builds the messaging architecture",
      detail: "Turns positioning and proof points into a message hierarchy -- the pillars, the claims, the evidence behind each one.",
      access: "read",
      source: "strategy/orchestrator.py -- AGENT_ROSTER",
      activity: [
        "Linked each message pillar to its supporting evidence citation",
        "Rewrote the core claim after a fair-balance gap was flagged against it",
        "Grouped four message pillars under two positioning themes",
      ],
      sources: [
        { label: "Message hierarchy", detail: "The brand kit's message_hierarchy -- pillar, claim, and evidence per row." },
        { label: "Core claim & positioning", detail: "The kit's core_claim and positioning_statement fields, as the frame every pillar has to support." },
        { label: "Guardrails", detail: "The kit's dos/don'ts, so no message pillar contradicts a stated brand guardrail." },
      ],
    },
    {
      id: "inspiration",
      name: "Inspiration",
      job: "Proposes creative and campaign concepts",
      detail: "Generates concept directions grounded in the brand kit -- tone, angle, and channel fit -- for a human to react to.",
      access: "read",
      source: "strategy/orchestrator.py -- AGENT_ROSTER",
      activity: [
        "Proposed two concept directions grounded in the Confident / Evidence-led tone pillars",
        "Marked one earlier concept legacy after the tagline changed",
        "Surfaced a channel-fit note for the HCP-facing concept",
      ],
      sources: [
        { label: "Concepts & tone pillars", detail: "The kit's concepts list (active/legacy/emerging) and tone_pillars, for direction and voice." },
        { label: "Tagline & message pool", detail: "The kit's tagline and message_pool, as the raw phrasing material concepts pull from." },
        { label: "Voice do/don't", detail: "voice_do / voice_dont, so a proposed concept doesn't lean on a banned term." },
      ],
    },
    {
      id: "activation",
      name: "Activation",
      job: "Shapes the tactical activation plan",
      detail: "Converts strategy into a tactical plan -- what actually gets built and in what order, once the direction is set.",
      access: "read",
      source: "strategy/orchestrator.py -- AGENT_ROSTER",
      activity: [
        "Sequenced the tactical rollout starting with rep-triggered detail aids",
        "Flagged a content gap where no asset exists yet for the differentiation pillar",
        "Converted three approved concepts into buildable activation tasks",
      ],
      sources: [
        { label: "Approved concepts", detail: "The Inspiration agent's output, once a concept direction has been accepted." },
        { label: "Message hierarchy", detail: "Which pillars still need a tactic built against them." },
        { label: "Channel/format constraints", detail: "campaign_ops.py's touchpoint and format shapes, so the tactical plan is buildable, not aspirational." },
      ],
    },
  ],
  ops: [
    {
      id: "orchestration",
      name: "Engagement Orchestration Agent",
      job: "Answers questions about the live activity board",
      detail: "Grounded in the current schedule, notifications, and sync state -- ask it status, it answers from what's actually running.",
      access: "read",
      source: "strategy/tab_chat.py -- STAGE_AGENTS.orchestration",
      activity: [
        "Answered a status question about a stalled compliance-review activity",
        "Reported that 3 activities are pending owner sign-off",
        "Explained why a hard compliance gate blocked a send that was due today",
      ],
      sources: [
        { label: "Live activity board", detail: "Every setup activity, its owner role, SLA, and planned dates, as currently scheduled." },
        { label: "Notifications & sync state", detail: "The downstream Monday/Smartsheet/Jira-style sync status for each activity." },
        { label: "Hard gates", detail: "Which compliance gates are still open -- never agent-closable, only reportable." },
      ],
    },
    {
      id: "operations",
      name: "Campaign Operations Agent",
      job: "The only agent that can edit the live journey",
      detail: "Rewrites the campaign flow diagram from plain-English instructions -- every edit is validated before it's saved.",
      access: "write",
      source: "strategy/tab_chat.py -- STAGE_AGENTS.operations",
      activity: [
        "Added a wait node between two email sends per the user's instruction",
        "Rejected an edit that would have left a decision branch with no path to an end node",
        "Rewired one branch's condition label after the user clarified the trigger",
      ],
      sources: [
        { label: "Live WorkflowDocument", detail: "The project's current campaign_plan_layout -- read as a compact graph spec, never the raw document." },
        { label: "Validation rule engine", detail: "A Python port of the flow-builder's strict-flowchart rules 1-4 -- every proposed edit is checked before it's saved." },
        { label: "Operations conversation", detail: "This tab's own chat history, so a multi-step instruction stays coherent across turns." },
      ],
    },
    {
      id: "campaign-ops",
      name: "Flow Synthesis",
      job: "Builds the first draft of the engagement journey",
      detail: "Turns the plan's touchpoints, segments, and cadence into the initial flow -- the starting point the Operations agent then edits.",
      access: "read",
      source: "strategy/campaign_ops.py",
      activity: [
        "Built the initial 9-node flow from the plan's touchpoint sequence",
        "Set the wait duration between two touchpoints from the plan's stated cadence",
        "Generated the first decision branch from a persona's stated channel preference",
      ],
      sources: [
        { label: "Plan touchpoints & cadence", detail: "The approved plan's touchpoint sequence and timing, as the flow's initial backbone." },
        { label: "Segment definitions", detail: "Which persona/segment each branch of the flow is built for." },
        { label: "Node type catalog", detail: "campaign_ops.py's fixed node types (send/wait/decision/exit/followup/closure) the initial flow is assembled from." },
      ],
    },
  ],
  intelligence: [
    {
      id: "reporting",
      name: "Reporting & Insights Agent",
      job: "Answers questions about how the campaign is performing",
      detail: "Grounded Q&A over the KPI scorecard and funnel data -- ask what's working, it answers from the real numbers.",
      access: "read",
      source: "strategy/tab_chat.py -- STAGE_AGENTS.reporting",
      activity: [
        "Answered a question about funnel drop-off between MQL and SQL",
        "Explained the current A/B test's read on subject-line variant B",
        "Pulled the UTM-tagged channel with the highest engagement this week",
      ],
      sources: [
        { label: "KPI scorecard & funnel", detail: "The stage-promotion funnel and delivery/engagement targets computed by Reporting Insights." },
        { label: "UTM tagging matrix", detail: "The link/tagging matrix, for channel- and campaign-level attribution." },
        { label: "A/B test design", detail: "The active test's variants and current read, so an answer about it is grounded, not guessed." },
      ],
    },
    {
      id: "hcp360",
      name: "HCP 360 Panel",
      job: "Answers questions about the HCP universe",
      detail: "Queryable over specialty, state, segment, channel and brand -- the panel behind every audience number shown elsewhere.",
      access: "read",
      source: "strategy/hcp_360.py -- ask()",
      activity: [
        "Segmented the panel by specialty and state on request",
        "Returned the channel-preference breakdown for the Primary tier",
        "Counted HCPs matching a specialty + segment + brand filter",
      ],
      sources: [
        { label: "HCP 360 panel", detail: "The full audience panel -- specialty, state, segment, channel, and brand per record." },
        { label: "Query tools", detail: "list_hcps / segment_summary / get_hcp -- the same tool calls the Reporting agent uses when it needs panel data." },
      ],
    },
    {
      id: "persona-review",
      name: "Persona Review",
      job: "Scores a plan against each persona's real preferences",
      detail: "Reads the finished plan back through each persona's channel preferences and decision drivers, and voices what would land.",
      access: "read",
      source: "strategy/persona_review.py",
      activity: [
        "Scored the plan's channel mix against the Outcomes-Focused Cardiologist's stated preference",
        "Flagged one message that doesn't match the Access-Minded Generalist's decision driver",
        "Voiced how the Value-Focused Payer would react to the current claim set",
      ],
      sources: [
        { label: "Finished plan content", detail: "The composed plan's message hierarchy, channel mix, and claims -- what's actually being reviewed." },
        { label: "Persona preferences", detail: "Each kit persona's stated channel preference, decision driver, and voice quote." },
      ],
    },
    {
      id: "reporting-insights",
      name: "Reporting Insights",
      job: "Builds the KPI and funnel dashboard",
      detail: "Computes the scorecard, funnel, and demographic cards the Reporting agent then answers questions about.",
      access: "read",
      source: "strategy/reporting_insights.py",
      activity: [
        "Computed this week's funnel conversion rates",
        "Refreshed the demographic card from the latest delivery data",
        "Rebuilt the KPI scorecard after a new activity completed",
      ],
      sources: [
        { label: "Delivery & engagement data", detail: "Raw send/open/click/response records, aggregated into the scorecard and funnel." },
        { label: "Demographic breakdown source", detail: "The HCP 360 panel's specialty/state/segment fields, joined against delivery data for the demographic cards." },
      ],
    },
  ],
};
