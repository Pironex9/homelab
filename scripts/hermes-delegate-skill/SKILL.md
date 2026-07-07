---
name: delegate-to-claude-code
description: Delegate a bounded coding or documentation task to the homelab's Claude Code environment on LXC 109 (claude-mgmt), which has the full homelab git repo checked out.
---

When a task involves reading, editing, or committing files in the
`/root/homelab` git repository, delegate it - that repo lives on LXC 109,
not here. Run this via your shell tool:

    ssh -i /root/.ssh/hermes-to-109 root@192.168.0.204 "<one clear, self-contained task description>"

The task description is the entire message the remote Claude Code instance
will see - be specific and complete, it has no memory of this conversation
and no access to anything outside `/root/homelab`. It can read, edit, and
git-commit files in that repo, but cannot run arbitrary shell commands or
reach the network - keep tasks to "read/find/fix/document" requests, never
"install a package," "run this command," or "fetch this URL."
