# Accessing the panel

After install, reach ATLAS through an SSH tunnel:

```bash
ssh -L 127.0.0.1:8765:/run/atlas/web.sock root@YOUR_HOST
```

Then open http://127.0.0.1:8765.

Do not put the panel on the public internet without TLS and a trusted reverse proxy you already control.
