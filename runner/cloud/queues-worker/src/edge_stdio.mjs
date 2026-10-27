// One verdict per line, for the de_dust edge differential.
// stdin: {"text","secret"}   stdout: {"why":"accept"|"no-sig"|"mismatch"}
// The text is a body. It goes to the gate the way a client sends it,
// under a job subject and a blank line, so a body with a blank line
// of its own (a trailer) is split where fetch and the runner split it.
import readline from "node:readline";
import { bodyVerdict } from "./index.js";

const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of rl) {
  if (!line) continue;
  let msg;
  try {
    msg = JSON.parse(line);
  } catch {
    console.log(JSON.stringify({ why: "mismatch" }));
    continue;
  }
  const why = await bodyVerdict(msg.secret, "[HOMING-PIGEON] job dust\n\n" + (typeof msg.text === "string" ? msg.text : ""));
  console.log(JSON.stringify({ why }));
}
