import copy
import json
from pathlib import Path
import unittest
from schema_lab.contract import LabError, Unsupported, LIMITS, parse
from schema_lab.model import analyze, render

ROOT = Path(__file__).resolve().parents[1]
FROZEN = json.loads((ROOT / "fixtures/oracles.json").read_text())
RESOURCE = json.loads((ROOT / "fixtures/resources.json").read_text())


def env(definition, instance):
    return dict(schema="schema-subset-lab/1", dialect="2020-12", definition=definition, instance=instance)


def selected(name):
    return next(case for case in FROZEN["cases"] if case["name"] == name)


def wire(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


class ModelTests(unittest.TestCase):
    def test_full_frozen_reports(self):
        for case in FROZEN["cases"]:
            with self.subTest(name=case["name"]):
                original = copy.deepcopy(case["input"])
                report, code = analyze(case["input"])
                self.assertEqual(code, case["exit"])
                self.assertEqual(render(report), case["stdout"])
                self.assertEqual(case["input"], original)

    def test_full_frozen_diagnostics(self):
        for case in FROZEN["diagnostics"]:
            with self.subTest(name=case["name"]):
                with self.assertRaises(LabError) as raised:
                    render(analyze(case["input"])[0])
                code = 3 if type(raised.exception) is Unsupported else 2
                text = json.dumps(dict(status="unsupported" if code == 3 else "error", reason=str(raised.exception)), sort_keys=True, separators=(",", ":")) + "\n"
                self.assertEqual((code, text), (case["exit"], case["stderr"]))

    def test_boolean_integer(self):
        self.assertEqual(analyze(env({"type": "integer"}, False))[1], 1)

    def test_enum_kind(self):
        self.assertEqual(analyze(env({"enum": [0]}, False))[1], 1)

    def test_required_null(self):
        self.assertEqual(analyze(env({"required": ["x"]}, {"x": None}))[1], 0)

    def test_properties_absent(self):
        self.assertEqual(analyze(env({"properties": {"x": False}}, {}))[1], 0)

    def test_declared_failed_child(self):
        case = selected("declared-failing-covered")
        self.assertEqual(render(analyze(case["input"])[0]), case["stdout"])

    def test_unsupported_absent_child(self):
        self.assertEqual(analyze(env({"properties": {"x": {"$ref": "x"}}}, {}))[1], 3)

    def test_no_short_circuit(self):
        case = selected("mixed-no-short-circuit")
        self.assertEqual(render(analyze(case["input"])[0]), case["stdout"])

    def test_issue_cap(self):
        self.assertEqual(len(analyze(selected("issue-boundary-128")["input"])[0]["issues"]), 128)
        with self.assertRaisesRegex(LabError, "resource limit"):
            analyze(env({"additionalProperties": False}, {"k%03d" % i: 0 for i in range(129)}))

    def test_output_cap(self):
        report, code = analyze(RESOURCE["input"])
        self.assertEqual(code, 1)
        uncapped = json.dumps(report, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n"
        expected = json.dumps(RESOURCE["uncapped_report"], sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n"
        self.assertEqual(uncapped, expected)
        self.assertEqual(len(uncapped), 814207)
        self.assertEqual(len(wire(RESOURCE["input"])), 3185)
        with self.assertRaisesRegex(LabError, "resource limit"):
            render(report)

    def test_detached_aliases(self):
        shared = [1]
        value = env({"enum": [shared]}, shared)
        report = analyze(value)[0]
        report["instance"].append(2)
        self.assertEqual(shared, [1])
        self.assertEqual(report["definition"]["enum"], [[1]])
        report["definition"]["enum"][0].append(3)
        self.assertEqual(shared, [1])

    def test_hooks_rejected_before_call(self):
        touched = []
        class Trap(dict):
            def items(self): touched.append(1); raise RuntimeError()
            def __eq__(self, other): touched.append(2); raise RuntimeError()
        with self.assertRaises(LabError): analyze(env({}, Trap()))
        class Meta(type):
            def __eq__(self, other): touched.append(3); raise RuntimeError()
            def __hash__(self): touched.append(4); raise RuntimeError()
        class Foreign(metaclass=Meta): pass
        with self.assertRaises(LabError): analyze(env({}, Foreign()))
        self.assertEqual(touched, [])

    def test_cycles_and_alias_count(self):
        value = []; value.append(value)
        with self.assertRaises(LabError): analyze(env({}, value))
        shared = [0] * 16
        with self.assertRaisesRegex(LabError, "resource limit"):
            analyze(env({}, [shared] * 31))

    def test_encoded_integer_and_duplicates(self):
        for bad in (b'-0', b'1.0', b'1e0', b'NaN', b'Infinity', b'9007199254740992', b'0' * 33):
            with self.subTest(value=bad), self.assertRaises(LabError):
                parse(b'{"schema":"schema-subset-lab/1","dialect":"2020-12","definition":{},"instance":' + bad + b'}')
        for raw in (b'{"x":0,"x":1}', b'{"x":0,"\\u0078":1}'):
            with self.assertRaises(LabError):
                parse(b'{"schema":"schema-subset-lab/1","dialect":"2020-12","definition":{},"instance":' + raw + b'}')
        self.assertEqual(analyze(parse(wire(env({}, LIMITS["integer_abs"]))))[1], 0)

    def test_bytes_and_unicode(self):
        for raw in (bytearray(b'{}'), b'\xef\xbb\xbf{}', b'\xff', b'{} trailing', b'[[[[[[[[[[[[0'):
            with self.assertRaises(LabError): parse(raw)
        for bad in ("\ud800", "\ufdd0", "\U0001ffff"):
            with self.assertRaises(LabError): analyze(env({}, bad))
        self.assertEqual(analyze(env({}, "\x00\u200b\ue000"))[1], 0)

    def test_generic_boundaries(self):
        for value in ("x" * 129, [0] * 512, {"x": [0] * 511}):
            with self.assertRaisesRegex(LabError, "resource limit"): analyze(env({}, value))
        self.assertEqual(analyze(env({}, "x" * 128))[1], 0)
        value = 0
        for _ in range(8): value = [value]
        with self.assertRaisesRegex(LabError, "resource limit"): analyze(env({}, value))
        with self.assertRaisesRegex(LabError, "resource limit"): parse(b' ' * 32769)

    def test_grammar_bounds_and_late_invalid(self):
        for definition in ({"enum": [0] * 33}, {"required": [str(i) for i in range(17)]}, {"properties": {str(i): True for i in range(17)}}):
            with self.assertRaisesRegex(LabError, "resource limit"): analyze(env(definition, 0))
        nested = False
        for _ in range(4): nested = {"properties": {"x": nested}}
        with self.assertRaisesRegex(LabError, "resource limit"): analyze(env(nested, {}))
        for definition in ({"zzz": 0, "properties": {"absent": {"enum": False}}}, {"additionalProperties": {"required": False}}):
            with self.assertRaisesRegex(LabError, "invalid definition"): analyze(env(definition, 0))

    def test_schema_node_cap(self):
        children = {str(i): {"properties": {str(j): True for j in range(3)}} for i in range(16)}
        del children["0"]["properties"]["0"]
        self.assertEqual(analyze(env({"properties": children}, None))[1], 0)
        children["0"]["properties"]["0"] = True
        with self.assertRaisesRegex(LabError, "resource limit"): analyze(env({"properties": children}, None))

    def test_unsupported_cap(self):
        self.assertEqual(len(analyze(env({"k%03d" % i: 0 for i in range(128)}, 0))[0]["unsupported"]), 128)
        with self.assertRaisesRegex(LabError, "resource limit"):
            analyze(env({"k%03d" % i: 0 for i in range(129)}, 0))

    def test_enum_member_limits(self):
        self.assertEqual(analyze(env({"enum": [[0] * 127]}, 0))[1], 1)
        with self.assertRaisesRegex(LabError, "resource limit"):
            analyze(env({"enum": [[0] * 128]}, 0))
        with self.assertRaisesRegex(LabError, "resource limit"):
            analyze(env({"enum": [["x" * 128] * 9]}, 0))

    def test_wrong_envelopes_and_raw_quota(self):
        for value in ({}, {**env({}, 0), "other": None}, env({}, 9007199254740992), env({}, 1.0)):
            with self.assertRaises(LabError): analyze(value)
        for value in (env({}, 0) | {"schema": ""}, env({}, 0) | {"dialect": "x/y"}):
            with self.assertRaises(LabError): analyze(value)
        exact = wire(env({}, 0)); exact += b' ' * (32768 - len(exact))
        self.assertEqual(analyze(parse(exact))[1], 0)
        with self.assertRaisesRegex(LabError, "resource limit"): parse(exact + b' ')

    def test_enum_budget_before_malformed_grammar(self):
        for definition in ({"type": "bad", "enum": [[0] * 128]}, {"required": False, "properties": {"absent": {"enum": [[0] * 128]}}}):
            with self.assertRaisesRegex(LabError, "resource limit"):
                analyze(env(definition, None))


if __name__ == "__main__": unittest.main()
