# FAQ

**What is ATLAS?**  
A single panel for one Linux server: inventory, live metrics, project dashboards, logs, alerts, and optional host control.

**How do I install it?**

```bash
curl -fsSL https://raw.githubusercontent.com/semenkulikov/ATLAS-core/main/packaging/get-atlas.sh | sudo sh
```

**How do I remove it?**

```bash
curl -fsSL https://raw.githubusercontent.com/semenkulikov/ATLAS-core/main/packaging/remove-atlas.sh | sudo sh
```

**Is data sent to the cloud?**  
No. Everything stays on the server until you enable Telegram or webhook alerts.

**Can I restart services from the UI?**  
Yes, after you turn control on. Dangerous actions ask for confirmation.
