# Local SI test

A development loop for the Oracle. You play the cloud SI. The harness
ensures the local model is up, then each thing you type is an `ask`
sent through the protocol path. The Oracle answers. Nothing is emailed.

This is not a unit test. It is a self-hosted chat against the real
Oracle path, so you can change the system prompt, the owner
instructions, or the model and see the effect immediately.

## Run it

```
python3 runner/runner.py --config config.json --local-test
```

Terminal chat. Type a question. `quit` exits.

```
python3 runner/runner.py --config config.json --local-test --browser
```

Opens a loopback page (`http://127.0.0.1:8765/`) so the chat is in a
browser window. The server binds `127.0.0.1` only and refuses to start
if the bind is not loopback.

## What it needs

- `inference.endpoint` and `inference.model` in `config.json`, and the
  endpoint must be loopback. The installer sets this up unless you
  passed `--no-inference`.
- Ollama (or another OpenAI-compatible server) running on that
  endpoint. The harness starts the daemon if it is down.

## Recursive feedback

Use it while developing the Oracle:

1. Run `--local-test`.
2. Ask something. Read the answer.
3. Edit `owner_instructions` or the hard system prompt.
4. The runner hot-reloads config; re-ask and compare.
5. Repeat.

The point is a tight loop between "what the SI would ask" and "what
the Oracle actually says", on one machine, with no mailbox in the way.
