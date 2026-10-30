"""The subject grammar, in one place (Q121).

Every transport and the hosted queue's Worker read a message's kind
and id from its subject: ``[HOMING-PIGEON] <words> job <id>``,
``result <id>``, ``qresult <id>``, ``determination <id>`` and so on.
The Worker is JavaScript. Its ``\\s`` and Python's differ: Python's
counts the information-separator controls ``\\x1c``-``\\x1f`` and
``\\x85`` (NEL) as whitespace, JavaScript's does not, and JavaScript's
counts ``\\ufeff`` and Python's does not. A subject separated by one
of those routed at the runner and not at the gate, or the other way.

So the separator is spelled out here as ECMAScript's ``\\s`` set, and
a token as its complement, and every reader builds its pattern from
these two. The Worker (``runner/cloud/queues-worker/src/index.js``)
keeps ``\\s``/``\\S``, which is this set by definition. A subject that
separates its words with a control character is not routed by
either side.
"""

import re

# ECMAScript WhiteSpace + LineTerminator: what the Worker's \s matches.
SPACE = ("\\t\\n\\x0b\\x0c\\r \\xa0\\u1680\\u2000-\\u200a"
         "\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff")
SPACE_CLASS = "[" + SPACE + "]"
TOKEN_CLASS = "[^" + SPACE + "]"

MARKER = r"\[HOMING-PIGEON\]"


def pattern(kinds):
    """The subject pattern for one or more kinds: the marker, any
    words, the kind, the id. ``kinds`` is a regex alternation body
    such as ``"job"`` or ``"result|qresult"``. Group 1 is the kind
    only when the alternation captures; the id is the last group."""
    return (MARKER + "(?:" + SPACE_CLASS + "+" + TOKEN_CLASS + "+)*"
            + SPACE_CLASS + "+(?:" + kinds + ")" + SPACE_CLASS + "+("
            + TOKEN_CLASS + "+)")


def pattern_kind(kinds):
    """As ``pattern``, with the kind captured as group 1 and the id as
    group 2."""
    return (MARKER + "(?:" + SPACE_CLASS + "+" + TOKEN_CLASS + "+)*"
            + SPACE_CLASS + "+(" + kinds + ")" + SPACE_CLASS + "+("
            + TOKEN_CLASS + "+)")


JOB_ID_RE = re.compile(pattern("job"), re.I)
RESULT_ID_RE = re.compile(pattern("result|qresult"), re.I)
