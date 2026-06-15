# Getting started

This is the friendly, end-to-end walkthrough: from nothing to *"Claude is building things in my Unreal editor"* in about ten minutes. If you just want the terse reference, see [setup.md](setup.md).

## The mental model

There are three pieces, and you only ever touch the first two:

```
You + Claude   <-->   UEMCP server   <-->   your live Unreal editor
 (chat client)        (this package)        (built-in Python remote exec)
```

- You talk to **Claude** (Claude Code, Claude Desktop, or any MCP client).
- Claude calls the **UEMCP server**, a small Python program that runs on your machine.
- UEMCP drives your **open Unreal editor** over the engine's built-in remote execution, so there is **nothing to install or compile inside Unreal**, and no panel to click. The editor's viewport *is* the UI: it updates live as Claude works, and Claude can take screenshots to see what it did.

## Before you start

- **Unreal Engine 5.0 to 5.7**, Epic Launcher or source build. Have a project open (the project browser screen does not count).
- **Python 3.10+** on the machine running the server.
- **[uv](https://docs.astral.sh/uv/)** (recommended) or pip.
- A **Claude client**: [Claude Code](https://docs.claude.com/en/docs/claude-code) or Claude Desktop.

## Step 1: Turn on Remote Execution in Unreal (about 30 seconds)

This is the *only* Unreal-side step, and it is per project.

1. Open your project in the Unreal editor.
2. **Edit > Project Settings**, search **Python**.
3. Check **Enable Remote Execution**.

That's it. The **Python Editor Script Plugin** ships with the engine and is enabled by default in recent versions, so you usually do not need to touch it. If the *Python* section is missing from Project Settings, enable the plugin first: **Edit > Plugins**, search **Python**, enable **Python Editor Script Plugin**, restart the editor, then do steps 2 and 3.

> You won't see any confirmation: Remote Execution just quietly starts listening. We verify it in Step 3.

## Step 2: Add the server to your client

**Claude Code:**

```sh
claude mcp add unreal -- uvx uemcp
```

**Claude Desktop** (Settings > Developer > Edit Config), add:

```json
{
  "mcpServers": {
    "unreal": {
      "command": "uvx",
      "args": ["uemcp"]
    }
  }
}
```

Then restart the client so it picks up the new server. (Prefer pip or a local clone? See [setup.md](setup.md).)

## Step 3: Say hello

In a fresh chat, ask Claude to check the connection:

> "Run ue_status, then tell me what project and engine version you see."

You should get back your project name and engine version. Now make it do something you can see:

> "Spawn a point light, then take a screenshot of the viewport."

If Claude reports a spawned actor and shows you an image of your level, **you're done**. Everything below is optional polish and power-ups.

> **Tip that saves confusion:** real levels are often built thousands of units from the world origin, so an actor spawned at `[0,0,0]` can be off-screen, a kilometer from your camera. Ask Claude to *"place it in front of my current viewport camera"* or *"next to <some existing actor>"* and it will anchor to the right spot. (The built-in `unreal_workflow_strategy` prompt nudges Claude to do this automatically.)

## If discovery finds nothing

`ue_status` returns no editors? Work down this list. The first item fixes most cases, and the **second fixes most of the rest on Windows.**

1. **Is a project actually open?** The project browser does not answer discovery. And did you check **Enable Remote Execution** (Step 1)?
2. **VPN or virtual adapters (the common one).** NordVPN, Tailscale, VirtualBox, Hyper-V, and WSL adapters can hijack multicast so discovery never reaches an editor sitting on loopback. The fix is to pin both ends to loopback. Recent Unreal already defaults its **Multicast Bind Address** to `127.0.0.1`; match it on the server side by setting `UEMCP_MULTICAST_BIND=127.0.0.1`:

   **Claude Code:**
   ```sh
   claude mcp add unreal -e UEMCP_MULTICAST_BIND=127.0.0.1 -- uvx uemcp
   ```
   **Claude Desktop:**
   ```json
   {
     "mcpServers": {
       "unreal": {
         "command": "uvx",
         "args": ["uemcp"],
         "env": { "UEMCP_MULTICAST_BIND": "127.0.0.1" }
       }
     }
   }
   ```

3. **Firewall.** Allow `UnrealEditor.exe` (and the Python/uvx process) through Windows Defender.

More detail and other symptoms: [troubleshooting.md](troubleshooting.md).

## Going further

Once the basics work, you can unlock more:

- **Drop in assets from Sketchfab.** Search is free and needs no key:
  > "Search Sketchfab for a wooden barrel and list a few with their licenses."

  To actually import one, set `SKETCHFAB_API_TOKEN` (sketchfab.com, Settings > API) in the server's `env`, then:
  > "Import that barrel and place it on the floor in front of the camera."

- **Generate models with AI (Meshy).** Set `MESHY_API_KEY` (meshy.ai, Settings > API), then:
  > "Generate a mossy stone golem, wait for it to finish, and import it."

  Generation is asynchronous: Claude starts the task, polls it, then imports. Generated models come in normalized, so ask Claude to rescale to taste.

- **Use the recipes.** [cookbook.md](cookbook.md) has ready-made prompts for lighting rigs, greyboxing, and asset audits.

- **See every tool.** [tools.md](tools.md) is the full reference for all 37 tools.

## A few good first prompts

- "List every static mesh asset with 'rock' in the name, then scatter 20 of them in a rough circle around the origin."
- "Build a three-point lighting rig around the selected actor and screenshot it."
- "Create a BP_Collectible blueprint with a static mesh component and a sphere collision."
- "Fly the camera to a nice 3/4 view of the level and take a high-res screenshot."

Have fun. When something breaks, `ue_status` and [troubleshooting.md](troubleshooting.md) are your friends.
