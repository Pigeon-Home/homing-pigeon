# Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab
"""Project Platinum, wire/: the DTLS record layer from a mutated seed corpus.

Queue P targets (docs/reports/v3.13.8/coverage-gaps.md):
`wire/dtlsproto.py:_RecordSealer.open` (9 missing), `_split_records`
(6) and `_parse_extensions` (2). test_dtls_fuzz drives these with
random bytes, and random bytes almost never get past the first
header octet, which is why the lines stay dark. Here the corpus is
real: records sealed by `_RecordSealer.seal` (with and without a
connection id, several epochs), plaintext records, and extension
blocks built by `_extensions_bytes`. Each is mutated the ordinary
ways (truncation, a bit flipped, a boundary octet, the length field
rewritten, a byte dropped or doubled, the record repeated, junk
appended) and the contract is asserted, never the implementation:

- `_split_records` never raises, and what it returns is the datagram
  cut into contiguous pieces from the start; an unmutated run of
  sealed records splits back into exactly those records.
- `_RecordSealer.open` returns (type, content, seq) or raises
  DtlsError or JobCryptoError; an unmutated record opens to what was
  sealed.
- `_parse_extensions` returns (dict, end) with end inside the data,
  or raises DtlsError; an unmutated block parses back to its pairs.

No `max_examples`: HP_PLATINUM_EXAMPLES sets how hard the rig pushes,
CI keeps the quick default. Written by 40000e00 alongside Muse's
queue P (docs/use/misc.md, 2026-10-26).
"""
import unittest

from hypothesis import given, settings, strategies as st

from runner.wire.dtlsproto import (
    DtlsError,
    _RecordSealer,
    _extensions_bytes,
    _parse_extensions,
    _plaintext_record,
    _split_records,
)
from runner.wire.jobcrypto import JobCryptoError

SECRET = bytes(range(48))
BOUNDARY = (0x00, 0x01, 0x04, 0x08, 0x10, 0x1F, 0x20, 0x2C, 0x3F, 0x7F,
            0x80, 0xE0, 0xFF)

_cid = st.one_of(st.none(), st.binary(min_size=0, max_size=8))
_seal_args = st.tuples(st.integers(0, 3), st.integers(20, 25),
                       st.binary(max_size=64), _cid)


def _seal_all(args):
    sealer = _RecordSealer(SECRET)
    return [sealer.seal(epoch, ct, body, cid)
            for epoch, ct, body, cid in args]


@st.composite
def _mutated(draw, data):
    """`data` mutated one to three of the ordinary ways."""
    data = bytearray(data)
    for _ in range(draw(st.integers(1, 3))):
        how = draw(st.sampled_from(
            ("truncate", "flip", "boundary", "length", "drop", "double",
             "repeat", "junk")))
        n = len(data)
        if how == "truncate":
            data = data[:draw(st.integers(0, n))]
        elif how == "repeat":
            data = data + data
        elif how == "junk":
            data += draw(st.binary(min_size=1, max_size=16))
        elif n == 0:
            continue
        elif how == "flip":
            i = draw(st.integers(0, n - 1))
            data[i] ^= 1 << draw(st.integers(0, 7))
        elif how == "boundary":
            data[draw(st.integers(0, n - 1))] = draw(st.sampled_from(BOUNDARY))
        elif how == "length" and n >= 2:
            # the two-octet length sits after the header; aim near it
            i = draw(st.integers(0, min(n - 2, 16)))
            v = draw(st.sampled_from((0, 1, 16, 17, n - 1, n, n + 1, 0xFFFF)))
            data[i:i + 2] = (v & 0xFFFF).to_bytes(2, "big")
        elif how == "drop":
            del data[draw(st.integers(0, n - 1))]
        elif how == "double":
            i = draw(st.integers(0, n - 1))
            data.insert(i, data[i])
    return bytes(data)


def _contiguous_prefix(test, pieces, data):
    joined = b"".join(pieces)
    test.assertEqual(joined, data[:len(joined)])
    for p in pieces:
        test.assertIsInstance(p, bytes)
        test.assertTrue(p)


def _open_or_refuse(test, sealer, epoch, record):
    try:
        out = sealer.open(epoch, record)
    except (DtlsError, JobCryptoError):
        return None
    test.assertIsInstance(out, tuple)
    test.assertEqual(len(out), 3)
    ct, content, seq = out
    test.assertIsInstance(ct, int)
    test.assertIsInstance(content, bytes)
    test.assertIsInstance(seq, int)
    test.assertGreaterEqual(seq, 0)
    return out


class SplitRecordsPlatinum(unittest.TestCase):
    @settings(deadline=None)
    @given(args=st.lists(_seal_args, min_size=1, max_size=4))
    def test_sealed_run_splits_back_exactly(self, args):
        records = _seal_all(args)
        self.assertEqual(_split_records(b"".join(records)), records)

    @settings(deadline=None)
    @given(data=st.data(), args=st.lists(_seal_args, min_size=1, max_size=3),
           plain=st.binary(max_size=40))
    def test_mutated_datagram_splits_into_a_prefix(self, data, args, plain):
        seed = b"".join(_seal_all(args))
        if data.draw(st.booleans()):
            seed = _plaintext_record(22, 0, 1, plain) + seed
        datagram = data.draw(_mutated(seed))
        _contiguous_prefix(self, _split_records(datagram), datagram)


class RecordOpenPlatinum(unittest.TestCase):
    @settings(deadline=None)
    @given(args=st.lists(_seal_args, min_size=1, max_size=4))
    def test_sealed_records_open_to_what_was_sealed(self, args):
        records = _seal_all(args)
        opener = _RecordSealer(SECRET)
        for seq, ((epoch, ct, body, _cid), rec) in enumerate(zip(args, records)):
            self.assertEqual(opener.open(epoch, rec), (ct, body, seq))

    @settings(deadline=None)
    @given(data=st.data(), arg=_seal_args)
    def test_mutated_record_opens_or_refuses(self, data, arg):
        record = _seal_all([arg])[0]
        mutated = data.draw(_mutated(record))
        if not mutated:
            return
        _open_or_refuse(self, _RecordSealer(SECRET), arg[0], mutated)

    @settings(deadline=None)
    @given(flags=st.sampled_from((0, 0x04, 0x08, 0x10, 0x0C, 0x14, 0x18, 0x1C)),
           epoch=st.integers(0, 3), tail=st.binary(max_size=4))
    def test_every_header_shape_short_or_empty_refuses(self, flags, epoch, tail):
        # one header octet of each C/S/L shape, then too little to hold
        # the fields it promises and a tag; the empty record too
        sealer = _RecordSealer(SECRET)
        with self.assertRaises(DtlsError):
            sealer.open(epoch, b"")
        with self.assertRaises((DtlsError, JobCryptoError)):
            sealer.open(epoch, bytes([0x20 | flags | epoch]) + tail)

    @settings(deadline=None)
    @given(start=st.integers(0xFFFF - 24, 0xFFFF + 8), count=st.integers(2, 32),
           stride=st.integers(1, 4), epoch=st.integers(0, 3),
           body=st.binary(max_size=16))
    def test_records_across_the_16_bit_wrap_keep_their_sequence(
            self, start, count, stride, epoch, body):
        # the wire carries the low 16 bits; across the wrap, with every
        # stride-th record arriving (the rest lost), then the first one
        # arriving late, each opens to its full sequence number
        sealer = _RecordSealer(SECRET)
        sealer.seq = start
        records = [sealer.seal(epoch, 23, body, None) for _ in range(count)]
        opener = _RecordSealer(SECRET)
        opener._next_expected = start
        for i in range(0, count, stride):
            self.assertEqual(opener.open(epoch, records[i]), (23, body, start + i))
        self.assertEqual(opener.open(epoch, records[0]), (23, body, start))

    @settings(deadline=None)
    @given(zeros=st.integers(0, 8), epoch=st.integers(0, 3))
    def test_all_zero_inner_plaintext_refuses(self, zeros, epoch):
        # content type 0 over zero padding: nothing left once the
        # padding is stripped (RFC 8446 5.2), so no content type
        record = _RecordSealer(SECRET).seal(epoch, 0, b"\x00" * zeros, None)
        with self.assertRaises(DtlsError):
            _RecordSealer(SECRET).open(epoch, record)


class ExtensionsPlatinum(unittest.TestCase):
    _pairs = st.dictionaries(st.integers(0, 0xFFFF), st.binary(max_size=24),
                             max_size=6)

    @settings(deadline=None)
    @given(pairs=_pairs, lead=st.binary(max_size=8))
    def test_block_parses_back_to_its_pairs(self, pairs, lead):
        block = _extensions_bytes(sorted(pairs.items()))
        out, end = _parse_extensions(lead + block, len(lead))
        self.assertEqual(out, pairs)
        self.assertEqual(end, len(lead) + len(block))

    @settings(deadline=None)
    @given(data=st.data(), pairs=_pairs)
    def test_mutated_block_parses_or_refuses(self, data, pairs):
        raw = _extensions_bytes(sorted(pairs.items()))
        if data.draw(st.booleans()) and pairs:
            # the duplicate-type refusal: one pair written twice
            t, v = sorted(pairs.items())[0]
            body = raw[2:] + t.to_bytes(2, "big") + len(v).to_bytes(2, "big") + v
            raw = len(body).to_bytes(2, "big") + body
        mutated = data.draw(_mutated(raw))
        offset = data.draw(st.integers(0, len(mutated) + 2))
        try:
            out, end = _parse_extensions(mutated, offset)
        except DtlsError:
            return
        self.assertIsInstance(out, dict)
        self.assertLessEqual(end, len(mutated))
        for k, v in out.items():
            self.assertTrue(0 <= k <= 0xFFFF)
            self.assertIsInstance(v, bytes)


if __name__ == "__main__":
    unittest.main()
