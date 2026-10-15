# Transport implementation status

Contract: `send`, `poll`, `ack`. Blobs are opaque signed JSON.
Code: `runner/transports.py`.

| Transport | send | poll | ack | Config |
|-----------|------|------|-----|--------|
| email | yes | runner IMAP loop | runner marks seen | smtp_*, mailbox_* |
| local_socket | yes | yes | n/a | port 8766, test only |
| cloudflare | yes | yes | yes | cf_account_id, cf_api_token, cf_queue_id |
| nats | yes | later | later | nats_host, nats_port |
| mqtt | yes | later | later | mqtt_host, mqtt_port |
| redis | yes | later | later | redis_host, redis_port |
| postgres | config-ready | later | later | pg_dsn (wire protocol not bundled) |
| durable_objects | yes | later | later | do_url, cf_api_token |

Testing plan: email is what we exercise. Cloudflare is ready for a
live try. The others are wired so a configured box can send; poll
paths land as each one is exercised.
