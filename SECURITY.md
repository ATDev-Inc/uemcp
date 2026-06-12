# Security policy

## The threat model, plainly

UEMCP executes Python inside your Unreal Editor process. That is its purpose, not a vulnerability. The things worth understanding:

- **The remote execution protocol has no authentication.** Anything on the local network segment that can speak the protocol can run code in an editor that has remote execution enabled. UEMCP's defaults (localhost command channel, multicast TTL 0) keep traffic on the local machine, and Unreal's own defaults do the same. Raising the TTL or binding non-loopback interfaces extends that trust to the whole network segment. Do not do that on networks you do not control.
- **The MCP client decides what runs.** UEMCP does not sandbox or filter the Python it is asked to execute; `ue_python` is an explicit full-access escape hatch. Permissioning belongs in the MCP client (Claude Code and Claude Desktop both prompt for tool use).
- **Project content is at stake, not your OS account.** Tools can modify, delete, and save project assets. Use source control on your Unreal project.

## Reporting a vulnerability

If you find a vulnerability in UEMCP itself (for example: the server can be made to execute code from an unexpected source, snippet interpolation can be escaped, or the protocol client mishandles hostile responses), please report it privately:

- GitHub: use [private vulnerability reporting](https://github.com/ATDev-Inc/uemcp/security/advisories/new)
- Email: owenpkent@gmail.com

Please include a reproduction. You can expect an acknowledgment within a week. Please do not open public issues for unpatched vulnerabilities.

## Supported versions

The latest release on PyPI. There is no backporting; fixes ship as new releases.
