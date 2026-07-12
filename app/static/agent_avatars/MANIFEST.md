---
type: Concept
title: Agent avatar drop folder
timestamp: 2026-07-12T09:02:38Z
---

# Agent avatar drop folder

Drop the 5 robot avatar PNGs here using the **exact filenames** below. They render as each
agent's avatar in the team panel and chat (served at `/static/agent_avatars/<file>`), and the
agent name + accent colour are themed to match each image (already wired in `index.html`:
`AGENT_COLORS` + `AGENT_PEOPLE`).

| # | Colour | Filename | Agent |
|---|---|---|---|
| A1 | Blue | `agent-1-blue.png` | Engagement Planner Agent |
| A2 | Red | `agent-2-red.png` | Market & Competitive Intelligence Agent |
| A3 | Green | `agent-3-green.png` | Strategy & Positioning Agent |
| A4 | Orange | `agent-4-orange.png` | Creative Inspiration Agent |
| A5 | Purple | `agent-5-purple.png` | Activation Planning Agent |

If a file is missing, the agent falls back to its monogram (EP / MC / SP / CI / AP) on the
themed gradient — nothing breaks. To host elsewhere instead, set each agent's `photo` field in
`index.html` to a full URL.
