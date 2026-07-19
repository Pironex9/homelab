# topology

Interactive network topology map of the homelab. Static build, no backend: `build.js` bakes `nodes.yml` into `dist/index.html`, served by `caddy:alpine` on port 3009.

```bash
npm install
npm test        # build verification + validation tests
npm run build   # nodes.yml -> dist/
```

Edit `nodes.yml` to add/change hosts, then rebuild. `dist/` is gitignored - deploy by rsyncing it to the repo clone on LXC 100 (see `docs/proxmox/27_Network_Topology_Map.md`).
