# FAQ

**How do I install ATLAS?** One command as root: `curl -fsSL https://raw.githubusercontent.com/semenkulikov/ATLAS-core/main/packaging/get-atlas.sh | sudo sh`. Remove with `packaging/remove-atlas.sh` the same way.

**Does a scan open a port?** No. `atlas scan` writes a report and does not listen.

**Where do secrets go?** They are not stored. Excerpts are masked, `/etc/shadow` and private keys are refused, and `.env` files keep key names only.

**Can I restart a service from the panel?** Only after `atlas control enable` on the host, and only through the helper whitelist. The panel asks you to type the unit name.

**Will alerts phone home?** No channel sends anything until you enable webhook or Telegram.

**What if I am not root?** Missing sources stay unknown, with the reason. The report is still written.
