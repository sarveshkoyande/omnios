import { z } from "zod";

// Section 3.2 node.ports[] — first-class named connection points (Visio "connection points",
// Mermaid has no equivalent — this is where our model exceeds Mermaid's).

export const PortSideSchema = z.enum(["top", "right", "bottom", "left"]);
export const PortDirectionSchema = z.enum(["in", "out"]);

export const PortSchema = z
  .object({
    id: z.string(),
    side: PortSideSchema,
    offset: z.number().min(0).max(1),
    direction: PortDirectionSchema,
    name: z.string().optional(),
  })
  .passthrough();

export type PortSide = z.infer<typeof PortSideSchema>;
export type PortDirection = z.infer<typeof PortDirectionSchema>;
export type Port = z.infer<typeof PortSchema>;
