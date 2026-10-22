import codecs
import contextlib
import io
import itertools
import json
from pathlib import Path
import tempfile
import unittest

from newline_audit import inspect_stream, main, violations


class AuditTests(unittest.TestCase):
    def inspect(self, data, chunk_size=65536):
        return inspect_stream(io.BytesIO(data), chunk_size)

    def test_all_short_sequences_at_chunk_boundaries(self):
        # Independent reference: consume CRLF as one token, then count lone CR/LF.
        for length in range(6):
            for sequence in itertools.product((b"x", b"\r", b"\n"), repeat=length):
                data = b"".join(sequence)
                pairs = data.count(b"\r\n")
                remainder = data.replace(b"\r\n", b"")
                expected = (remainder.count(b"\n"), pairs, remainder.count(b"\r"))
                for chunk_size in (1, 2, 3, 7):
                    result = self.inspect(data, chunk_size)
                    self.assertEqual((result["lf"], result["crlf"], result["cr"]), expected,
                                     (data, chunk_size))

    def test_utf8_and_bom_split_across_chunks(self):
        data = codecs.BOM_UTF8 + "Caf\u00e9\r\n".encode("utf-8")
        result = self.inspect(data, 1)
        self.assertTrue(result["utf8_bom"])
        self.assertEqual(result["style"], "crlf")
        self.assertEqual(result["bytes"], len(data))

    def test_empty_bom_only_and_single_line(self):
        for data in (b"", codecs.BOM_UTF8):
            result = self.inspect(data, 1)
            self.assertIsNone(result["final_newline"])
            self.assertEqual(violations(result, "lf", True), [])
        self.assertFalse(self.inspect(b"hello")["final_newline"])
        self.assertEqual(len(violations(self.inspect(b"hello"), "lf", True)), 1)

    def test_policy(self):
        self.assertEqual(violations(self.inspect(b"a\n"), "lf", True), [])
        self.assertTrue(violations(self.inspect(b"a\r\n"), "lf"))
        self.assertTrue(violations(self.inspect(b"a\r\nb\n")))
        self.assertTrue(self.inspect(b"a\r")["final_newline"])

    def test_reject_binary_and_truncated_utf8(self):
        for data in (b"a\x00b", b"\xff", b"\xc3", codecs.BOM_UTF16_LE + b"a\x00"):
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.inspect(data, 1)

    def test_invalid_chunk_size(self):
        with self.assertRaises(ValueError):
            self.inspect(b"text", 0)

    def test_cli_json_and_error_priority_without_modification(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            good, bad = root / "good.txt", root / "bad.txt"
            good.write_bytes(b"a\r\nb\n")
            bad.write_bytes(b"private-example\xff")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main([str(bad), str(good), "--json"])
            rows = json.loads(output.getvalue())
            self.assertEqual(code, 2)
            self.assertEqual([row["status"] for row in rows], ["error", "fail"])
            self.assertNotIn("private-example", output.getvalue())
            self.assertEqual(good.read_bytes(), b"a\r\nb\n")

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sample.txt"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([str(path)]), 2)
                self.assertEqual(main([temp]), 2)
                path.write_bytes(b"a\n")
                self.assertEqual(main([str(path), "--expect", "lf"]), 0)
                self.assertEqual(main([str(path), "--expect", "crlf"]), 1)
                path.write_bytes(b"a")
                self.assertEqual(main([str(path)]), 0)
                self.assertEqual(main([str(path), "--require-final-newline"]), 1)


if __name__ == "__main__":
    unittest.main()
