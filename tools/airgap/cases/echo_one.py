"""One short question. No project context. One user message. No system message.
"""

import json
import os
import unittest
import urllib.request

QUESTION = "Reply with the single word one."
ENDPOINT = "http://127.0.0.1:11434/v1"


def minimal_payload(model):
    """The smallest chat the local model can be given."""
    return {
        "model": model,
        "messages": [{"role": "user", "content": QUESTION}],
        "temperature": 0,
        "keep_alive": "30m",
    }


def ask():
    model = os.environ.get("TOPAZ_MODEL") or "qwen3:1.7b"
    endpoint = os.environ.get("TOPAZ_ENDPOINT") or ENDPOINT
    timeout = int(os.environ.get("TOPAZ_TIMEOUT") or "180")
    body = json.dumps(minimal_payload(model)).encode("utf-8")
    req = urllib.request.Request(
        endpoint.rstrip("/") + "/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    answer = data["choices"][0]["message"].get("content") or ""
    if not answer.strip():
        raise AssertionError("empty reply")
    return answer


class EchoOneTest(unittest.TestCase):
    def test_echo_01(self):
        ask()

    def test_echo_02(self):
        ask()

    def test_echo_03(self):
        ask()

    def test_echo_04(self):
        ask()

    def test_echo_05(self):
        ask()

    def test_echo_06(self):
        ask()

    def test_echo_07(self):
        ask()

    def test_echo_08(self):
        ask()

    def test_echo_09(self):
        ask()

    def test_echo_10(self):
        ask()

