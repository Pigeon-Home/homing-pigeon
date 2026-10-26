# Recorded provider responses

<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

One JSON file per provider, each a list of exchanges the suite
replays through `runner.hosting.httpdoor.HttpClient`. The shapes
follow each provider's public API reference as of October 2026; when
a real account exists, re-record them with the real responses
(scrubbed of ids and tokens) and the tests keep running unchanged.

An exchange:

    {"name": "create-ok",
     "request": {"method": "POST", "url": "...machines", "body_has": ["config"]},
     "response": {"status": 200, "headers": {}, "json": {...}}}

`url` is matched as a suffix. `body_has` lists keys the recorded
request body carried; the player asserts they are present.
