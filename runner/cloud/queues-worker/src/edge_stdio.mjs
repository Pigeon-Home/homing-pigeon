// One verdict per line, for the de_dust edge differential.
// stdin: {"text","secret"}   stdout: {"why":"accept"|"no-sig"|"mismatch"}
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
  const why = await bodyVerdict(msg.secret, msg.text);
  console.log(JSON.stringify({ why }));
}
