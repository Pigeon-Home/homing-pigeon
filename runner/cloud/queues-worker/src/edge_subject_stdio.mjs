// Agent-Stamp: 80000aeb-9c1f-49ad-aeee-fa0855092587
// One subject verdict per line, for the de_dust edge_subject
// differential (de_dust2). The gate routes a message by the id it
// reads from the subject; the runner reads the same subject with the
// same two regexes (runner/wire/transports.py). This bridge returns
// what the Worker's jobIdOf and resultIdOf read, so de_dust can hold
// the two implementations to the same id.
// stdin: {"subject"}   stdout: {"job": <id|null>, "result": <id|null>}
import readline from "node:readline";
import { jobIdOf, resultIdOf } from "./index.js";

const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of rl) {
  if (!line) continue;
  let msg;
  try {
    msg = JSON.parse(line);
  } catch {
    console.log(JSON.stringify({ job: null, result: null }));
    continue;
  }
  const subject = typeof msg.subject === "string" ? msg.subject : "";
  console.log(JSON.stringify({ job: jobIdOf(subject), result: resultIdOf(subject) }));
}
