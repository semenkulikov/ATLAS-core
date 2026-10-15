# FAQ

**How do I install ATLAS?** Download the signed x86_64 archive from [GitHub Releases](https://github.com/semenkulikov/ATLAS-core/releases/latest), verify with minisign and the checksum, extract, then run `sudo ./atlas-1.0.0-linux-x86_64/install.sh`. Details are in the README.

**Does a scan open a port?** No. `atlas scan` writes a report and does not listen.

**Where do secrets go?** They are not stored. Excerpts are masked, `/etc/shadow` and private keys are refused, and `.env` files keep key names only.

**Can I restart a service from the panel?** Only after `atlas control enable` on the host, and only through the helper whitelist. The panel asks you to type the unit name.

**Will alerts phone home?** No channel sends anything until you enable webhook or Telegram.

**What if I am not root?** Missing sources stay unknown, with the reason. The report is still written.
