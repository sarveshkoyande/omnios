import type { CampaignFlow, CampaignFlowNodeType } from "../../types";
import type { WorkflowNode } from "./flowbuilder/schema/node";
import type { WorkflowDocument } from "./flowbuilder/schema/document";
import { createEmptyDocument, createNode, createEdge } from "./flowbuilder/schema/factories";
import { defaultDataFor } from "./flowbuilder/schema/nodeDefaults";
import type { NodeType } from "./flowbuilder/schema/nodeTypes";
import { tokens, shade } from "../../../theme/tokens";

// One-time seed conversion: the campaign-ops backend (strategy/campaign_ops.py) still
// emits the original CampaignFlow shape (send/wait/decision/exit/followup/closure) for
// a project's *base* plan — that generator is untouched. This adapter maps it into the
// workflow tool's Section-3 WorkflowDocument schema the first time a project is opened
// in the new builder. Every edit after that is saved as a WorkflowDocument directly
// (see saveCampaignFlowDocument in ../../api) — there is no path back to CampaignFlow.

const TYPE_MAP: Record<CampaignFlowNodeType, NodeType> = {
  entry: "start",
  send: "process",
  wait: "delay",
  decision: "decision",
  // The behavioural split is an exclusive gateway, not a yes/no diamond: exactly one
  // message-ladder track is taken, chosen by what the HCP actually clicked.
  branch: "gateway.exclusive",
  exit: "end",
  followup: "process",
  closure: "end",
};

const ACCENT: Record<CampaignFlowNodeType, string> = {
  entry: tokens.color.success,
  send: tokens.color.primary,
  wait: tokens.color.secondary,
  decision: tokens.color.warning,
  branch: tokens.color.warning,
  exit: tokens.color.success,
  followup: tokens.color.secondary,
  closure: shade(0.55),
};

const FILL: Record<CampaignFlowNodeType, string> = {
  entry: "#EAF7EF",
  send: "#FFFFFF",
  wait: "#FFF7ED",
  decision: "#FFF9DB",
  branch: "#FFF9DB",
  exit: "#EFF6FF",
  followup: "#F8FBFF",
  closure: "#F1F5F9",
};

const SIZE: Record<CampaignFlowNodeType, { w: number; h: number; resizable: true }> = {
  entry: { w: 72, h: 72, resizable: true },
  send: { w: 220, h: 96, resizable: true },
  wait: { w: 132, h: 64, resizable: true },
  decision: { w: 168, h: 112, resizable: true },
  branch: { w: 168, h: 112, resizable: true },
  exit: { w: 76, h: 76, resizable: true },
  followup: { w: 220, h: 96, resizable: true },
  closure: { w: 76, h: 76, resizable: true },
};

export function applyCampaignNodeVisuals(node: WorkflowNode): WorkflowNode {
  const field = node.data?.campaignStepKind;
  const kind = field && typeof field === "object" && "value" in field ? field.value : null;
  if (typeof kind !== "string" || !(kind in SIZE)) return node;
  const campaignKind = kind as CampaignFlowNodeType;
  return {
    ...node,
    size: SIZE[campaignKind],
    style: {
      ...node.style,
      stroke: ACCENT[campaignKind],
      fill: FILL[campaignKind],
      strokeWidth: campaignKind === "entry" || campaignKind === "closure" || campaignKind === "exit" ? 3 : 2,
    },
  };
}

export function campaignFlowToDocument(flow: CampaignFlow, docName = "Campaign Operations"): WorkflowDocument {
  const doc = createEmptyDocument(docName);
  const page = doc.pages[0];

  for (const n of flow.nodes) {
    const workflowType = TYPE_MAP[n.type];
    const node = createNode(workflowType, n.data.label, { x: 0, y: 0 }, {
      id: n.id,
      size: SIZE[n.type],
      style: { stroke: ACCENT[n.type], fill: FILL[n.type], strokeWidth: n.type === "entry" || n.type === "closure" || n.type === "exit" ? 3 : 2 },
      data: {
        ...defaultDataFor(),
        campaignStepKind: { type: "fixedList", value: n.type, options: Object.keys(TYPE_MAP), label: "Campaign step kind" },
        ...(n.data.day != null ? { day: { type: "number", value: n.data.day, label: "Day" } } : {}),
        ...(n.data.channel ? { channel: { type: "string", value: n.data.channel, label: "Channel" } } : {}),
        ...(n.data.detail ? { detail: { type: "string", value: n.data.detail, label: "Detail" } } : {}),
        ...(n.data.segment_key ? { segment_key: { type: "string", value: n.data.segment_key, label: "Segment" } } : {}),
        ...(n.data.content_ref
          ? {
              content_ref_label: { type: "string", value: n.data.content_ref.label, label: "Content" },
              content_ref_ready: { type: "boolean", value: n.data.content_ref.ready, label: "Content ready" },
            }
          : {}),
      },
    });
    page.nodes.push(node);
  }

  for (const e of flow.edges) {
    const edge = createEdge(e.source, e.target, {
      label: e.label,
      glue: "dynamic",
    });
    page.edges.push({ ...edge, id: e.id });
  }

  return doc;
}
