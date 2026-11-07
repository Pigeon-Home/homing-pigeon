# Pi Light and the Raspberry Pi AI HAT+ 2: readiness

This page records what the Raspberry Pi AI HAT+ 2 would and would
not change for a Pi Light install, what it costs on 7 November
2026, and whether to buy one. It is a readiness record only: no
purchase was made, and the shipped Pi Light profile is unchanged
by anything on this page.

## Pi Light as it ships today

Pi Light is the Raspberry Pi profile described in INSTALL.md
("Raspberry Pi: Pi Light") and in the support matrix
(docs/support-matrix.md). A Pi install — detected automatically
from the device tree, or chosen anywhere with
`--profile pi-light` — gets the full runner and the full
protocol: signed jobs come in, jobs run, results and
attestations go back, the senses and local signals work, and
the Oracle still watches, wakes on a serious signal, and files
its briefs.

What the Pi does not get is a local model. The installer
installs no Ollama and downloads no model. The Oracle runs in
deterministic mode (`oracle_mode: "deterministic"` in
`config.json`): briefs and answers are assembled from the box's
own records — the job index, retained jobs and their notable
lines, the log tail — instead of a model's narration. The
`ask` op stays off in this mode. Tier-1 Oracle opinions still
file, and the learning loop still records verified facts; the
model-formed opinion note (`oracle_opinion_model`) and the
model channel of the learning loop (`oracle_learning_model`)
stay dark, because deterministic mode never calls a model. The
profile is a config choice, not a separate codebase, and the
mode is read live from `config.json`: editing it flips the mode
without a restart.

The profile already names its own upgrade path, in INSTALL.md's
words: when Pis ship with neural accelerator chips worth using,
the same install upgrades in place — set `oracle_mode` to `llm`
and re-run the installer with `--inference-only` to pull a
model; nothing reinstalls and nothing else changes. The same
section also draws a line: a USB accelerator (Coral, Intel NCS,
Hailo) is not that Pi and is not a computer, and seeing one
does not change the install.

## The AI HAT+ 2

The AI HAT+ 2 is Raspberry Pi's generative AI add-on for
Raspberry Pi 5, released on 15 January 2026. It carries a
Hailo-10H AI accelerator delivering 40 TOPS (INT4) of inference
performance and 8GB of dedicated on-board RAM, and it fits the
Pi 5 as a HAT over PCIe — it is not a USB device. Raspberry
Pi's product page puts the software for compatible generative
AI models in Hailo's own repository, not in the Ollama setup
the installer performs on other machines.

## What changes when the HAT is present

The hardware capability changes; the shipped profile's
behaviour does not change by itself.

- Presence alone changes nothing in the install. Nothing in
  the profile as documented detects a HAT, flips `oracle_mode`,
  or installs a model when one appears. A Pi Light box with a
  HAT fitted still installs with no model and still runs the
  deterministic Oracle until the owner takes the upgrade path
  on purpose.
- What the HAT makes practical is the thing Pi Light
  deliberately does without: a local small-model inference
  option on the Pi itself. Its 8GB of on-board RAM and the
  Hailo-10H are built to run small language and vision-language
  models on the HAT, leaving the Pi 5's own CPU and memory for
  the runner. That is the class of hardware the profile's
  upgrade path is waiting for — "a model worth running", in
  the configuring-the-Oracle guide's words.
- If a box took that path, the pieces that light up are the
  ones deterministic mode keeps dark: the `ask` op, briefs and
  answers narrated by a model instead of assembled from the
  records, the model-formed opinion note, and the model
  channel of the learning loop. Each of those is a config
  change the owner makes (`oracle_mode`, and the model keys
  that default to off), not something the HAT switches on.
- One gap stands between the HAT and that path today. The
  documented inference setup is Ollama serving a pulled model
  on the host; the HAT's models are served through Hailo's
  software stack. Wiring the HAT into the runner's inference
  endpoint is future profile work. This page does not do it,
  and the benchmark below does not prove it done.

## The one benchmark

Raspberry Pi's article on the AI HAT+ 2 (written by Hailo,
published 25 February 2026) gives example benchmark figures
for 96 prefill tokens, measured on the CPU using llama.cpp:

| Model | Raspberry Pi 5 CPU | Hailo-10H |
| --- | --- | --- |
| QWEN2.5-1.5B-4int | 2039ms | 320ms |

Quoted the short way: Qwen2.5-1.5B prefill 320 ms on the HAT
vs 2,039 ms on Pi 5 CPU.

That is one model, at one size, in one measurement, of the
prefill phase only. It says nothing about any other model, any
other size, token-by-token generation speed, or how a model
served this way would behave as the runner's Oracle. It is
evidence that prefill for a 1.5B-class model is far faster on
the accelerator than on the Pi 5 CPU — and it is only that.

## What stays the same without the HAT

Everything Pi Light already ships. Without the HAT, a Pi Light
install keeps the full runner and the full protocol, the
senses and local signals, the Oracle's watch and wake gate,
briefs and answers assembled deterministically from the box's
own records, tier-1 opinions, and learning from verified facts
only. The `ask` op stays off, no model is installed or ever
called, and answers a Pi Light box cannot form on its own can
still go up to a laptop or a cloud SI under protocol version 2,
as the FAQ describes. The deterministic profile is the shipped
default, not a degraded mode, and it loses nothing by the HAT
existing.

## Price and availability, checked 7 November 2026

AI HAT+ 2:

- Launched at $130 in January 2026.
- Raspberry Pi's own product page, checked 7 November 2026,
  says "Available now for $200", and the July 2026 product
  brief lists the price as $200.
- A check of reseller listings on 12 October 2026 found about
  $200 at approved resellers, the bare HAT out of stock on
  Amazon, and third-party kits there at about $340.
- One US reseller (Vilros) listed the bare HAT at $236, in
  stock, when checked on 7 November 2026.

So the HAT is available, but not at $130: the official price
has moved $70 above the launch price, and street prices run
higher still.

ASUS UGen300: this comparison no longer waits on a price. The
UGen300 has been priced and has shipped. ASUS Japan put the
range on sale on 16 October 2026 (the 8GB USB model at 49,800
yen; the 8GB M.2 model at 45,980 yen), and US listings checked
on 7 November 2026 price the same Hailo-10H chip with 8GB of
memory at $299.99 for the USB model and $259.99 for the M.2
model (Newegg). It is the same accelerator in a form for
x86 and ARM hosts generally — a USB stick or an M.2 card, not
a Pi HAT. For a Pi Light install it also falls under the
profile's existing line: a USB accelerator does not change
the install.

## Recommendation: wait

Wait. Do not buy the AI HAT+ 2 at the current price.

- The buying case was made at $130. At $200 official — and
  $236 at the US reseller checked — the price has moved away
  from that case, not toward it. A genuine listing at $130
  would meet the original terms; nothing checked on
  7 November 2026 is at $130.
- Waiting no longer buys an answer about the UGen300: its
  price is known, it costs more than the HAT, and its form
  factors do not fit a Pi the way a HAT does. Waiting buys
  only the chance that the HAT's price or approved-reseller
  stock moves back toward the launch price.
- Waiting costs an option, not a capability. Until a HAT is
  fitted and the profile work above is done, a Pi Light box
  has no local small-model inference — and it runs, complete,
  on the deterministic profile it already ships. Nothing that
  works today stops working while the owner waits.

## Sources

- Raspberry Pi, "Buy a Raspberry Pi AI HAT+ 2" (price and
  specification, checked 7 November 2026):
  https://www.raspberrypi.com/products/ai-hat-plus-2/
- Raspberry Pi, "When and why you might need the Raspberry Pi
  AI HAT+ 2", 25 February 2026 (the benchmark table):
  https://www.raspberrypi.com/news/when-and-why-you-might-need-the-raspberry-pi-ai-hat-plus-2/
- ComputingForGeeks, "Jetson Orin Nano Super vs AI HAT+ 2 vs
  Hailo-10H for LLMs" (prices checked 12 October 2026):
  https://computingforgeeks.com/edge-llm-jetson-orin-vs-ai-hat-2-vs-hailo-10h/
- Vilros, "Raspberry Pi AI HAT+ 2" ($236, in stock, checked
  7 November 2026):
  https://vilros.com/products/raspberry-pi-ai-hat-2
- Newegg, "Edge AI Accelerator Cards" (ASUS UGen300 USB
  $299.99 and M.2 $259.99, checked 7 November 2026):
  https://www.newegg.com/Edge-AI-Accelerator-Cards/EventSaleStore/ID-2697
