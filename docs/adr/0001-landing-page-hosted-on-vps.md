# Landing page is self-hosted on the VPS, not on GitHub Pages

The documentation site runs on GitHub Pages, so the obvious move was to put the landing page there too. We deliberately did not. GitHub Pages allows only one custom domain per repository, which would have forced either a second repository or moving the docs onto a subpath; more importantly, a page whose entire pitch is "I run this infrastructure" is more credible when it is actually served from that infrastructure. It runs as a Caddy container on the Hetzner VPS, deployed through the existing Komodo GitOps flow.

## Considered Options

The homelab (LXC 100) was the first self-hosting candidate and was rejected: it would have tied the landing page's availability to the homelab's, which has two documented recurring failure modes (LVM thin-pool exhaustion, an ARP conflict incident). The usual mitigation - Cloudflare proxying with stale-on-error caching - is unavailable here, because this setup mandates gray-cloud DNS throughout (orange cloud breaks Traefik's Let's Encrypt challenge, per `docs/vps/01_Hetzner_VPS_Pangolin_Jellyfin_Setup.md`).

The VPS avoids that trade entirely: it is already the always-on public gateway, already runs Komodo Periphery, and already hosts Uptime Kuma.

## Consequences

Uptime Kuma runs on the same host, so the live-status widget reaches it over the local Docker bridge rather than back out through the public tunnel. This removes the cross-origin problem that would otherwise have forced either a Traefik CORS middleware or a scheduled build that bakes in stale numbers.

It also produces the honest failure mode: when the homelab goes down, the landing page stays up and correctly reports it as down. That is a better story than an uptime figure that can only ever be green.

The cost is one additional container on the security-hardened public gateway. It serves static files behind Traefik with no backend, which is the lowest-risk shape available, but it is still a new service on that host.
