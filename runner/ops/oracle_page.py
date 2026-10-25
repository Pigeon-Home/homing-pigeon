"""Oracle chat page HTML.

Extracted from runner.py to keep that file under the line budget.
"""
import json


def _text(value) -> str:
    return value if isinstance(value, str) else ""


def oracle_page(token: str, model: str, ready: bool) -> str:
    """One chat page. No remote assets. The token never goes in the URL."""
    def _text(value):
        if isinstance(value, str):
            return value
        if value is None:
            return ""
        try:
            return str(value)
        except Exception:
            return ""
    payload = json.dumps(
        {"token": _text(token), "model": _text(model), "ready": bool(ready)}
    ).replace("<", "\\u003c")
    return """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Oracle</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin: 0; min-height: 100vh; background: #0e1013; color: #e8eaed;
         font: 16px/1.55 ui-sans-serif, system-ui, -apple-system,
               "Segoe UI", sans-serif; }
  main { max-width: 46rem; margin: 0 auto; padding: 1.6rem 1.1rem 7rem; }
  h1 { font-weight: 650; font-size: 1.3rem; letter-spacing: 0.01em;
       margin: 0 0 0.25rem; }
  .note { color: #9aa0a6; font-size: 13px; margin: 0 0 1.1rem; }
  .role { color: #aeb4bc; font-size: 13.5px; line-height: 1.55;
          margin: 0 0 1.4rem; padding: 0.75rem 0.9rem;
          border: 1px solid #23262d; border-radius: 0.8rem;
          background: #14161a; }
  #log { display: flex; flex-direction: column; gap: 0.9rem;
         min-height: 12rem; }
  .bubble { white-space: pre-wrap; overflow-wrap: anywhere;
            padding: 0.65rem 0.85rem 0.75rem; border-radius: 1rem;
            max-width: 85%; }
  .who { display: block; font-size: 10.5px; font-weight: 600;
         letter-spacing: 0.12em; text-transform: uppercase; color: #8b9096;
         margin-bottom: 0.35rem; }
  .stamp { letter-spacing: 0.03em; text-transform: none; font-weight: 400;
           font-variant-numeric: tabular-nums; }
  .oracle { align-self: flex-start; background: #17191f;
            border: 1px solid #262a33; border-bottom-left-radius: 0.35rem; }
  .you { align-self: flex-end; background: #1e3a5f; color: #eaf1ff;
         border: 1px solid #2e5079; border-bottom-right-radius: 0.35rem; }
  .you .who { color: #9db8dd; }
  .working { animation: pulse 1.8s ease-in-out infinite; }
  @keyframes pulse { 50% { border-color: #454c61; } }
  form { position: sticky; bottom: 0; display: flex; gap: 0.55rem;
         padding: 1rem 0 1.2rem;
         background: linear-gradient(#0e101300, #0e1013 30%); }
  textarea { flex: 1; resize: none; min-height: 3.1rem; max-height: 8rem;
             font: 15.5px/1.45 ui-sans-serif, system-ui, sans-serif;
             background: #17191f; color: inherit; border: 1px solid #2a2e38;
             border-radius: 0.9rem; padding: 0.7rem 0.85rem; outline: none; }
  textarea:focus { border-color: #3d6fb8; }
  button { font: 15px ui-sans-serif, system-ui, sans-serif; font-weight: 600;
           background: #2f6fd0; color: #ffffff; border: 0;
           border-radius: 0.9rem; padding: 0 1.2rem; cursor: pointer; }
  button:disabled { opacity: 0.45; cursor: default; }
</style>
<main>
  <h1>Oracle</h1>
  <p class="note" id="note"></p>
  <p class="role">The Oracle watches this machine's Homing Pigeon jobs. Ask
  about recent job activity &mdash; what ran, what failed, what the log says.
  It reads the retained job outputs and the runner log, and can read files
  and run commands on this box to investigate. It knows only this machine;
  nothing leaves it.</p>
  <div id="log"></div>
  <form id="f">
    <textarea id="q" rows="2" autofocus placeholder="Ask what it thinks is going on — e.g. Give me a summary of the job status of what you found on this system."></textarea>
    <button id="send" type="submit">Send</button>
  </form>
</main>
<script>
const boot = __BOOT__;
const note = document.getElementById("note");
note.textContent = boot.ready
  ? ("Local model " + boot.model + ". This window stays on this machine. "
     + "The Oracle can read files and run commands on this box while it works.")
  : "No loopback model is configured, so Ask stays off. To fix it, re-run install.exe "
    + "--inference-only (it keeps your config and finishes the model setup), or point "
    + "inference.endpoint in config.json at your local Ollama server and restart the runner.";
const log = document.getElementById("log");
const q = document.getElementById("q");
const send = document.getElementById("send");
function stamp(d) {
  const p = (n) => String(n).padStart(2, "0");
  return p(d.getHours()) + ":" + p(d.getMinutes()) + ":" + p(d.getSeconds());
}
function took(ms) {
  const s = Math.max(0, Math.round(ms / 1000));
  return Math.floor(s / 60) + "m " + String(s % 60).padStart(2, "0") + "s";
}
const KEEP = 40;
const BUBBLE = 4000;
function trimLog() {
  while (log.children.length > KEEP) log.removeChild(log.firstChild);
  let note = document.getElementById("cut");
  if (log.children.length >= KEEP) {
    if (!note) {
      note = document.createElement("p");
      note.id = "cut";
      note.className = "note";
      note.textContent = "Older turns were dropped from this page. "
        + "The full exchange is in oracle-chat.jsonl.";
      log.parentNode.insertBefore(note, log);
    }
  }
}
function fit(text) {
  if (text.length <= BUBBLE) return text;
  return text.slice(0, BUBBLE) + "\\n… cut. The full answer is in oracle-chat.jsonl.";
}
function add(who, text, cls, note) {
  const wrap = document.createElement("div");
  wrap.className = "bubble " + cls;
  const label = document.createElement("span");
  label.className = "who";
  label.textContent = who;
  if (note) {
    const st = document.createElement("span");
    st.className = "stamp";
    st.textContent = " \\u00b7 " + note;
    label.appendChild(st);
  }
  wrap.appendChild(label);
  wrap.appendChild(document.createTextNode(fit(text)));
  log.appendChild(wrap);
  trimLog();
  wrap.scrollIntoView({block: "nearest"});
  return wrap;
}
// Enter sends. Shift+Enter is a newline. A bare Enter in a textarea
// does not submit the form, so the button looked dead and the log
// stayed quiet.
q.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    document.getElementById("f").requestSubmit();
  }
});
document.getElementById("f").onsubmit = async (e) => {
  e.preventDefault();
  const text = q.value.trim();
  if (!text || send.disabled) return;
  const t0 = Date.now();
  add("You", text, "you", stamp(new Date(t0)));
  q.value = "";
  send.disabled = true;
  const pending = add("Oracle", "Working…", "oracle working", stamp(new Date(t0)));
  const pendingText = pending.childNodes[1];
  let stepText = "";
  const paint = () => {
    const s = Math.floor((Date.now() - t0) / 1000);
    pendingText.textContent = "Working… " + s + "s."
      + (stepText ? " Current step: " + stepText + "."
                  : " This machine's model often takes a few minutes per step.")
      + " The answer replaces this line.";
  };
  paint();
  const tick = setInterval(paint, 1000);
  const poll = setInterval(async () => {
    try {
      const sr = await fetch("/status", {headers: {"X-Oracle-Token": boot.token}});
      const sd = await sr.json().catch(() => null);
      if (sd && sd.active && sd.step) stepText = sd.step;
    } catch (err) {}
  }, 3000);
  try {
    const r = await fetch("/ask", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Oracle-Token": boot.token
      },
      body: JSON.stringify({question: text})
    });
    const data = await r.json().catch(() => null);
    clearInterval(tick);
    clearInterval(poll);
    pending.remove();
    const done = stamp(new Date()) + " \\u00b7 took " + took(Date.now() - t0);
    if (data && data.answer) add("Oracle", data.answer, "oracle", done);
    else if (data && data.detail) add("Oracle", data.detail, "oracle", done);
    else if (r.status === 403) add("Oracle", "The chat session expired. Reload the page and ask again.", "oracle", done);
    else add("Oracle", "The page could not reach the local Oracle.", "oracle", done);
  } catch (err) {
    clearInterval(tick);
    clearInterval(poll);
    pending.remove();
    add("Oracle", "The page could not reach the local Oracle.", "oracle",
        stamp(new Date()) + " \\u00b7 took " + took(Date.now() - t0));
  }
  send.disabled = false;
  q.focus();
};
</script>
</html>
""".replace("__BOOT__", payload)
