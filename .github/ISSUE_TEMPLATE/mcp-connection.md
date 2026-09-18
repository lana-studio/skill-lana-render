---
name: MCP connection problem
about: You cannot authorize, or a tool refuses the call
title: "[mcp] "
labels: mcp
---

**Never paste tokens or signed URLs.** An access token, an `upload_url` or a `read_url` gives
whoever reads this issue access to your account or your files. The error code and the scope
names are all we need.

## Where it stops

<!-- Tick the last step that worked -->

- [ ] Created a Lana Studio account
- [ ] `claude mcp add --transport http lana https://mcp.lanastudio.pe/mcp`
- [ ] `/mcp` → `lana` → Authenticate finished in the browser
- [ ] `lana_get_capabilities(topic="limits")` answered
- [ ] The hello render succeeded

## The error

```
code:
message:
field_path:
guidance:
retryable:
```

## Scopes

<!-- What `/mcp` shows as granted for `lana`. Names only. -->

```
```

## Environment

- OS and version:
- Claude Code version:
