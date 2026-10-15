# Transport implementation status

The contract is in TRANSPORTS.md: `send`, `poll`, `ack`. Blobs are
opaque signed JSON.

| Transport | Status | Notes |
|-----------|--------|-------|
| email | implemented | SMTP send via the runner helpers. Poll is the runner's IMAP loop. |
| local_socket | implemented | Loopback TCP, length-prefixed. Test harness only. Not for deployment. |
| cloudflare | send implemented | HTTP API, stdlib. Needs `cf_account_id`, `cf_api_token`, `cf_queue_id`. Pull/ack next. |
| nats | interface only | NotYetTransport |
| mqtt | interface only | NotYetTransport |
| redis | interface only | NotYetTransport |
| postgres | interface only | NotYetTransport |
| durable_objects | interface only | NotYetTransport |

The mock SI (`--local-test`) can send through email and the local
socket today. Cloudflare send is available to anything that calls
`get_transport("cloudflare", cfg)`.

Code: `runner/transports.py`.
