# Pi 1 Research Agent

A small scheduler that runs on a Raspberry Pi and, once an hour, asks a local OpenClaw agent to scan the web for software product opportunities (problems people complain about where a tool could earn revenue), score each one for monetizability and feasibility, drop near-duplicates, and write an engineering requirements document for every new candidate. The agent itself does the searching and writing; this repository holds the orchestration, the prompt/skill files and the install scripts.

## How a cycle works

1. `opportunity-scanner` skill: web research, returns a JSON array of candidates scored out of 10,000.
2. Candidates below the configured thresholds are discarded; the rest are checked against existing requirements docs with a Jaccard title-similarity test (`deduplicator.py`) and saved as JSON in `pending/`.
3. `requirements-writer` skill: turns each research file into a Markdown requirements document in the handoff folder, then moves the research file to `done/`.
4. `cycle_logger.py` writes a per-cycle summary to the log.

The agent is invoked through the `openclaw agent ... --json` CLI (`openclaw_client.py`); the `skills/*.md` files are passed to it as instructions. The `workspace/` files are agent persona/procedure documents (research, digest, and page-creation roles).

## Stack

- Python 3 (standard library plus PyYAML)
- OpenClaw CLI as the AI gateway
- systemd service for the always-on loop
- A separate blocklist HTTP API (not included) that the agent consults to skip domains that block automated access

## Running

On a Raspberry Pi with the `openclaw` CLI installed and configured:

```bash
sudo ./install.sh                       # installs to /opt/pi1-research-agent, creates a venv and the systemd unit
sudoedit /etc/pi1-research-agent.env    # set your API key variable
sudoedit /opt/pi1-research-agent/config.yaml
sudo systemctl start pi1-research-agent
journalctl -u pi1-research-agent -f
```

Or run directly for development:

```bash
pip install -r requirements.txt
python main.py        # reads config.yaml from the current directory
```

Edit `config.yaml` before use: `blocklist_api_url` is set to a documentation address (`192.0.2.99`) and must be replaced with your own LAN address; also adjust the thresholds, cycle interval and the `/shared/...` folder paths.

## Project layout

```
main.py             scheduler and three-phase cycle
openclaw_client.py  runs a skill via the OpenClaw CLI, extracts JSON
deduplicator.py     Jaccard similarity check against existing docs
cycle_logger.py     per-cycle summary logging
skills/             instruction files for the scanner and requirements writer
workspace/          agent role/procedure documents
systemd/            service unit
install.sh          Raspberry Pi installer
```
