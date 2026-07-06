# Copilot manual test — how to run

This folder holds the live-Copilot verification prompt. It exercises exactly the
things automated tests cannot: skill discovery, live hook wiring (the real tool
names and payload fields), `/init` end-to-end, and the Stage 2 handoffs.

## Steps (on the machine with Copilot)

1. Clone this kit repo somewhere, e.g. `~/akm-kit`.
2. Create a **scratch repo** (or a throwaway branch of a small internal repo):
   ```bash
   mkdir akm-live-test && cd akm-live-test && git init
   ```
3. Install the kit into it from your local clone:
   ```bash
   uvx --from ~/akm-kit akmaestro init
   ```
   (or from git, if reachable:
   `uvx --refresh --from git+https://github.com/AbbasKMoussa/akm-murex-starter-kit.git akmaestro init`)
4. Copy the prompt into the scratch repo:
   ```bash
   cp ~/akm-kit/copilot-manual-test/PROMPT.md .
   ```
5. Open a **fresh** Copilot session (VS Code window or CLI) at the scratch repo
   root and say:

   > Follow the instructions in PROMPT.md and work through the phases with me.

6. When it finishes, send back `copilot-test-results.md` (and the redacted audit
   lines it contains — those are the most valuable part).

Phases 5–7 are interactive: the agent will ask you questions (that *is* the
flow being tested). Budget ~30–45 minutes for phases 0–6; phase 7 (Stage 2) is
optional and takes longer.
