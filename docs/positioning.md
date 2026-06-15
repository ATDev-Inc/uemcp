# How UEMCP compares

UEMCP is **infrastructure, not a product**. It is an open MCP server that exposes a live Unreal Engine 5 editor to any MCP client (Claude Code, Claude Desktop, or anything else that speaks MCP). It ships no model and no UI of its own: you bring the client and the LLM.

A growing category of tools takes the opposite approach: **embedded AI agents** that bundle their own model, their own chat UI, and a deep editor plugin. [Aura](https://www.tryaura.dev/) (Unreal + Unity; Blueprint, C++, and C# generation) is one example of that category.

Neither approach is strictly better. They optimize for different things.

## The tradeoffs

| Dimension | UEMCP (MCP server) | Embedded agent (e.g. Aura) |
|---|---|---|
| Shape | Infrastructure / protocol | End-to-end product |
| Model and client | Bring your own | Bundled |
| Openness | Open source | Commercial / closed |
| Composability | Runs alongside any other MCP server in one client | Self-contained |
| Editor coupling | Python remote execution, no UE-side plugin | Deep plugin integration |
| Engines | UE5 | UE and Unity |
| Code generation | Blueprints + arbitrary editor Python | Blueprints + C++ / C# |

## When each fits

Choose **UEMCP** when you want to drive Unreal from the same agent that already touches your repo, issue tracker, and other MCP tools; when you want an open, auditable, scriptable surface; or when you want to pick your own model.

Choose an **embedded agent** when you want a turnkey in-editor copilot with no setup, native C++/C# generation, and cross-engine support, and you are comfortable with a closed, bundled stack.

## What we take from the category

Embedded agents are a useful signal for UEMCP's roadmap. Gaps they highlight:

- **C++ generation** - UEMCP has none today (Blueprints and editor Python only).
- **Batch editing** - apply one change across many actors or assets in a single call. See [proposals/batch-editing.md](proposals/batch-editing.md).
- **Higher-level authoring** - for example a Blueprint-from-description helper layered on the existing primitives.
