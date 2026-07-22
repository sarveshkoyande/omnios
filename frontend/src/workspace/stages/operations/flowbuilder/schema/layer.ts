import { z } from "zod";

// Section 3.4: "Layers are orthogonal to groups: named sets with visible, printable,
// locked, snap, glue, color flags; nodes/edges can join multiple layers."

export const LayerSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    visible: z.boolean().default(true),
    printable: z.boolean().default(true),
    locked: z.boolean().default(false),
    snap: z.boolean().default(true),
    glue: z.boolean().default(true),
    color: z.string().optional(),
  })
  .passthrough();

export type Layer = z.infer<typeof LayerSchema>;
