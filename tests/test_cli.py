import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from schema_lab.__main__ import main, write_checked
from schema_lab.contract import read
from tests.test_model import ROOT, FROZEN, RESOURCE, env, wire

CHILD = [sys.executable] + (["-O"] if sys.flags.optimize else [])
RUN = CHILD + ["-m", "schema_lab"]


class DirtySink:
    def __init__(self, failure): self.failure, self.content = failure, ""
    def write(self, text):
        self.content += text
        if self.failure == "write": raise OSError("private detail")
        if self.failure == "short": return len(text) - 1
        if self.failure == "bool": return True
        return len(text)
    def flush(self):
        if self.failure == "flush": raise OSError("private detail")


class CLITests(unittest.TestCase):
    def setUp(self):
        folder = ROOT / ".private/tests"; folder.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=folder); self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name); self.input = self.folder / "input.json"
        self.input.write_bytes(wire(env({}, 0)))
    def invoke(self, *args):
        return subprocess.run(RUN + [str(arg) for arg in args], cwd=ROOT, capture_output=True, timeout=20)
    def test_actual_all_reports(self):
        for case in FROZEN["cases"]:
            with self.subTest(name=case["name"]):
                self.input.write_bytes(wire(case["input"]))
                result = self.invoke(self.input)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (case["exit"], case["stdout"].encode("ascii"), b""))
    def test_actual_all_diagnostics(self):
        for case in FROZEN["diagnostics"]:
            with self.subTest(name=case["name"]):
                self.input.write_bytes(wire(case["input"]))
                result = self.invoke(self.input)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (case["exit"], b"", case["stderr"].encode("ascii")))
    def test_fresh_existing_alias_hardlink(self):
        original = self.input.read_bytes(); output = self.folder / "out.json"
        result = self.invoke(self.input, "--output", output)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", b""))
        saved = output.read_bytes()
        link = self.folder / "link.json"; os.link(self.input, link)
        for target in (output, self.input, link):
            self.assertEqual(self.invoke(self.input, "--output", target).returncode, 2)
        self.assertEqual(output.read_bytes(), saved)
        self.assertEqual(self.input.read_bytes(), original)
        self.assertEqual(link.read_bytes(), original)
    def test_output_cap_before_file(self):
        self.input.write_bytes(wire(RESOURCE["input"]))
        output = self.folder / "out.json"
        result = self.invoke(self.input, "--output", output)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (2, b"", b'{"reason":"resource limit","status":"error"}\n'))
        self.assertFalse(output.exists())
    def test_help_arguments_empty_nul(self):
        help_result = self.invoke("--help")
        self.assertEqual((help_result.returncode, help_result.stderr), (0, b""))
        self.assertEqual(help_result.stdout, b'usage: schema-lab [-h] [--output OUTPUT] input\n\nBounded supplied synthetic JSON Schema subset values.\n\npositional arguments:\n  input\n\noptions:\n  -h, --help       show this help message and exit\n  --output OUTPUT  exclusive fresh ASCII JSON report\n')
        for args in ((), (self.input, "--bad")):
            result = self.invoke(*args)
            self.assertEqual((result.returncode, result.stdout, result.stderr), (2, b"", b'{"reason":"invalid command arguments","status":"error"}\n'))
        for args in (("",), (self.folder,), (self.input, "--output", "")):
            self.assertEqual(self.invoke(*args).returncode, 2)
        for args in (("a\x00b",), (str(self.input), "--output", "a\x00b")):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(list(args)), 2)
    def test_dirty_sinks_and_exact_count(self):
        for failure in ("write", "short", "flush"):
            sink, diagnostic = DirtySink(failure), io.StringIO()
            with patch("sys.stdout", sink), patch("sys.stderr", diagnostic):
                self.assertEqual(main([str(self.input)]), 2)
            self.assertEqual(diagnostic.getvalue(), '{"reason":"I/O or output delivery failed","status":"error"}\n')
        for failure in ("bool", "short", "write", "flush"):
            with self.assertRaises(OSError): write_checked(DirtySink(failure), "x")
        with patch("sys.stdout", DirtySink("write")), patch("sys.stderr", DirtySink("write")):
            self.assertEqual(main([str(self.input)]), 2)
    def test_closed_python_streams(self):
        for name in ("stdout", "stderr"):
            sink = io.StringIO(); sink.close()
            with patch("sys." + name, sink), patch("sys." + ("stderr" if name == "stdout" else "stdout"), io.StringIO()):
                self.assertEqual(main([str(self.input)] if name == "stdout" else []), 2)
    def test_physical_closed_pipes(self):
        records = []
        # A real anonymous pipe whose reader is already closed before main.
        wrapper = 'import os,sys; from schema_lab.__main__ import main; names=sys.argv[1].split(","); [(lambda pair: (os.close(pair[0]), os.dup2(pair[1], int(n)), os.close(pair[1])))(os.pipe()) for n in names]; raise SystemExit(main(sys.argv[2:]))'
        for names, args in (("1", [str(self.input)]), ("1", ["--help"]), ("2", []), ("1,2", [str(self.input)]), ("1,2", []), ("1,2", ["--help"])):
            result = subprocess.run(CHILD + ["-c", wrapper, names] + args, cwd=ROOT, capture_output=True, timeout=20)
            records.append(dict(pipes=names, args=args, exit=result.returncode, stdout_hex=result.stdout.hex(), stderr_hex=result.stderr.hex()))
            self.assertEqual(result.returncode, 2)
            self.assertNotIn(b"Exception ignored", result.stderr)
        (ROOT / ".private" / ("pipes-optimized.json" if sys.flags.optimize else "pipes-normal.json")).write_text(json.dumps(records, indent=2))
    def test_input_metadata_change(self):
        with patch("schema_lab.contract._identity", side_effect=[(0,), (1,)]):
            with self.assertRaises(OSError): read(self.input)
    def test_file_close_failure(self):
        output = self.folder / "fresh.json"
        class BrokenClose(io.StringIO):
            def __exit__(self, *args): raise OSError("private close")
        actual = Path.open
        def opening(path, *args, **kwargs):
            return BrokenClose() if path == output else actual(path, *args, **kwargs)
        with patch.object(Path, "open", opening), contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main([str(self.input), "--output", str(output)]), 2)


if __name__ == "__main__": unittest.main()
