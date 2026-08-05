import { autoLayoutPage } from "./flowbuilder/layout/autoLayout";
import { applyCampaignNodeVisuals } from "./campaignAdapter";
import type { WorkflowDocument } from "./flowbuilder/schema/document";

/**
 * The one place a machine-authored campaign diagram gets its geometry.
 *
 * Every generator of this document draws it flat: campaignAdapter.ts seeds every node at
 * (0,0) because the CampaignFlow it converts has no coordinates, and the Operations agent
 * (strategy/tab_chat.py) writes positions the model invented. Neither is a drawing. Any
 * such document must come through here before it is shown or saved, or it renders as a
 * pile of boxes stacked at one point on the canvas.
 *
 * What must NOT come through here: a document the user has edited by hand. Their positions
 * are the diagram.
 */

/** Nodes sitting on top of each other is the signature of a document that was persisted
 *  without ever being laid out — the origin pile, or a model that reused coordinates. It is
 *  not something manual editing produces, so it is safe to treat as "never drawn". */
export function isUnlaidOut(document: WorkflowDocument): boolean {
  const page = document.pages[0];
  if (!page || page.nodes.length < 2) return false;
  const seen = new Set<string>();
  for (const node of page.nodes) {
    const key = `${Math.round(node.position.x)}:${Math.round(node.position.y)}`;
    if (seen.has(key)) return true;
    seen.add(key);
  }
  return false;
}

/** Lay out page 1 and restore the campaign step's shape/colour/size, which the layout needs
 *  in place first (node size drives rank packing). */
export async function layoutCampaignDocument(document: WorkflowDocument): Promise<WorkflowDocument> {
  const page = document.pages[0];
  if (!page) return document;
  const normalized = { ...page, nodes: page.nodes.map(applyCampaignNodeVisuals) };
  const laidOut = await autoLayoutPage(normalized, document.direction);
  return { ...document, pages: document.pages.map((p, i) => (i === 0 ? laidOut : p)) };
}

/** Lay out only if the document has never been drawn. Used on load, where the document may
 *  equally be the user's own hand-arranged diagram. */
export async function layoutIfUnlaidOut(document: WorkflowDocument): Promise<WorkflowDocument> {
  return isUnlaidOut(document) ? layoutCampaignDocument(document) : document;
}
