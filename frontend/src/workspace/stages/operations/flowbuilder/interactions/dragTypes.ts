// Shared dataTransfer MIME keys for the two drag gestures the canvas accepts:
// dragging a palette entry (creates a node, or splits an edge on Insert-between),
// and dragging an AutoConnect arrow (connects to an existing node, no new node).
export const DRAG_NODE_TYPE = "application/x-wf-node-type";
export const DRAG_MASTER_ID = "application/x-wf-master-id";
export const DRAG_AUTOCONNECT_SOURCE = "application/x-wf-autoconnect-source";
