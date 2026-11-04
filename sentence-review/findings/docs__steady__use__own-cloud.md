# Findings — docs/steady/use/own-cloud.md

Source: docs/steady/use/own-cloud.md, reviewed at main ff2ea758.
Sentence units: 45. Flagged: 1. Categories: pre-release 45, post-release 0.

A guide to putting a runner on a small machine in the reader's own cloud account: the pieces, the before-you-start list, and the blob rules. 1 markup unit stands where the first sentence should be; the list fragments flow as list entries. All pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->" | pre-release | flagged | An HTML agent-stamp comment standing as the first unit — markup where the document's first sentence should be |
| 2 | "One command puts a Homing Pigeon runner on…" | pre-release | flows |  |
| 3 | "Your account, your bill (a few dollars a…" | pre-release | flows |  |
| 4 | "The runner is installed with the `hosted` profile…" | pre-release | flows |  |
| 5 | "Nobody but you ever holds your cloud token…" | pre-release | flows |  |
| 6 | "The pieces are `runner/hosting/` and the `homing-pigeon-host` command;…" | pre-release | flows |  |
| 7 | "A provider account with an API token: Fly…" | pre-release | flows |  |
| 8 | "The token in an environment variable." | pre-release | flows |  |
| 9 | "It is read from there and never written…" | pre-release | flows |  |
| 10 | "A transport." | pre-release | flows |  |
| 11 | "With the hosted queue (`docs/extend/transports.md`, "Queues") there is…" | pre-release | flows |  |
| 12 | "With a mailbox, a blob file, the runner's…" | pre-release | flows |  |
| 13 | "Leave `shared_secret` out and one is generated and…" | pre-release | flows |  |
| 14 | "A blob may carry only the keys in…" | pre-release | flows |  |
| 15 | "Security modes and the result view are the…" | pre-release | flows |  |
| 16 | "With the hosted queue, first mint the tenant…" | pre-release | flows |  |
| 17 | "It writes the SI token, the runner token…" | pre-release | flows |  |
| 18 | "Then the runner, the Worker URL and the…" | pre-release | flows |  |
| 19 | "`--queue` writes `transports: ["queues"]` and the queue block…" | pre-release | flows |  |
| 20 | "The token goes into the blob itself: the…" | pre-release | flows |  |
| 21 | "`--secret-env` names the shared secret the Worker already…" | pre-release | flows |  |
| 22 | "Leave it out and a secret is generated,…" | pre-release | flows |  |
| 23 | "`--queue` also works on `redeploy` and `rotate`, and…" | pre-release | flows |  |
| 24 | "With a mailbox:" | pre-release | flows |  |
| 25 | "Fly makes an app named `hp-<tenant>` and one…" | pre-release | flows |  |
| 26 | "Hetzner and DigitalOcean make one small VM (`cx23`,…" | pre-release | flows |  |
| 27 | "`up` waits until the machine reports running (`--wait…" | pre-release | flows |  |
| 28 | "Hand the secret to your SI the way…" | pre-release | flows |  |
| 29 | "With the hosted queue, the SI sends and…" | pre-release | flows |  |
| 30 | "A job that ran out of attempts without…" | pre-release | flows |  |
| 31 | "Sending the same id again before that is…" | pre-release | flows |  |
| 32 | "`redeploy` creates the replacement first and destroys the…" | pre-release | flows |  |
| 33 | "`rotate` is a redeploy with a fresh shared…" | pre-release | flows |  |
| 34 | "One resident machine per tenant per provider: `up`…" | pre-release | flows |  |
| 35 | "`up` and `redeploy` also take `--size` (the provider's…" | pre-release | flows |  |
| 36 | "`--inventory PATH` before the subcommand points every command…" | pre-release | flows |  |
| 37 | "`runner/hosting/workflows/hp-ephemeral.yml` is a template for your own repository." | pre-release | flows |  |
| 38 | "Read GitHub's Actions usage policy first; whether your…" | pre-release | flows |  |
| 39 | "Put your blob in a repository secret, copy…" | pre-release | flows |  |
| 40 | "A fresh runner VM boots, installs the release,…" | pre-release | flows |  |
| 41 | "The billable minutes your account paid are recorded…" | pre-release | flows |  |
| 42 | "`--drain N` and `--drain-seconds T` change the one…" | pre-release | flows |  |
| 43 | "`--workflow` names the workflow file if you renamed…" | pre-release | flows |  |
| 44 | "You do, to your provider, on their terms:…" | pre-release | flows |  |
| 45 | "This project runs nothing for you and bills…" | pre-release | flows |  |
