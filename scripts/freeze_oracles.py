"""Author original explicit outcomes before core; never import the validator.

Run once from the project root. Writes exclusive fixtures; refusing replacement
keeps later implementation from silently regenerating its own expected answers.
"""
import json
from pathlib import Path

LIMITS = dict(input_bytes=32768, numeric_lexeme=32, integer_abs=9007199254740991,
 global_depth=11, global_nodes=1030, global_containers=193, global_text_scalars=512,
 global_text_utf8_bytes=2048, global_scalars=8192, global_utf8_bytes=32768,
 definition_depth=10, definition_nodes=512, definition_containers=128,
 definition_text_scalars=128, definition_text_utf8_bytes=512,
 definition_scalars=4096, definition_utf8_bytes=16384,
 instance_depth=7, instance_nodes=512, instance_containers=64,
 instance_text_scalars=128, instance_text_utf8_bytes=512,
 instance_scalars=2048, instance_utf8_bytes=8192,
 enum_value_depth=7, enum_value_nodes=128, enum_value_containers=32,
 enum_value_text_scalars=128, enum_value_text_utf8_bytes=512,
 enum_value_scalars=1024, enum_value_utf8_bytes=4096,
 schema_depth=4, schema_nodes=64, properties=16, required=16, enum=32,
 type_options=7, issues=128, unsupported=128, output_bytes=262144)


def envelope(definition, instance):
    return dict(schema="schema-subset-lab/1", dialect="2020-12",
                definition=definition, instance=instance)


def issue(ip, dp, kw, reason):
    return dict(instance_pointer=ip, definition_pointer=dp, keyword=kw, reason=reason)


def feature(dp, kw, reason="unknown-keyword"):
    return dict(definition_pointer=dp, keyword=kw, reason=reason)


def report(definition, instance, issues=(), unsupported=()):
    # Only supplied hand-authored rows decide validity. No keyword evaluation.
    return dict(profile="schema-subset-lab/1", basis="2020-12-keyword-subset",
        assumption="synthetic supplied schema and instance; no authorization or safety verdict",
        limits=LIMITS, definition=definition, instance=instance,
        support="unsupported" if unsupported else "supported",
        valid=None if unsupported else not issues, issues=list(issues), unsupported=list(unsupported))


def pack(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False) + "\n"


def counts(value, parent=0):
    """Independent read-only logical counts, not an admission implementation."""
    containers = isinstance(value, (dict, list))
    depth = parent + 1 if containers else parent
    result = dict(nodes=1, containers=int(containers), depth=depth, scalars=0, utf8_bytes=0, text_scalars=0, text_utf8_bytes=0)
    texts = [value] if isinstance(value, str) else list(value) if isinstance(value, dict) else []
    for item in texts:
        size = len(item.encode("utf-8"))
        result["scalars"] += len(item)
        result["utf8_bytes"] += size
        result["text_scalars"] = max(result["text_scalars"], len(item))
        result["text_utf8_bytes"] = max(result["text_utf8_bytes"], size)
    children = value.values() if isinstance(value, dict) else value if isinstance(value, list) else []
    for child in children:
        selected = counts(child, depth)
        for name in ("nodes", "containers", "scalars", "utf8_bytes"):
            result[name] += selected[name]
        for name in ("depth", "text_scalars", "text_utf8_bytes"):
            result[name] = max(result[name], selected[name])
    return result


def main():
    cases = []
    def add(name, definition, instance, issues=(), unsupported=()):
        expected = report(definition, instance, issues, unsupported)
        cases.append(dict(name=name, input=envelope(definition, instance), report=expected,
                          exit=3 if unsupported else 1 if issues else 0, stdout=pack(expected)))
    add("true-null", True, None)
    add("true-object", True, {"x": 0})
    add("false-root", False, 0, [issue("", "", "boolean", "false-schema")])
    add("empty", {}, [])
    valid_values = [("object", {}), ("array", []), ("string", ""), ("number", 0), ("integer", -1), ("boolean", False), ("null", None)]
    for kind, value in valid_values:
        add("type-pass-" + kind, {"type": kind}, value)
        other = True if kind in ("integer", "number") else 0
        if kind == "integer": other = False
        add("type-fail-" + kind, {"type": kind}, other, [issue("", "/type", "type", "type-mismatch")])
    add("union-pass", {"type": ["null", "string"]}, None)
    add("union-fail", {"type": ["null", "string"]}, [], [issue("", "/type", "type", "type-mismatch")])
    add("enum-empty", {"enum": []}, None, [issue("", "/enum", "enum", "enum-mismatch")])
    add("enum-duplicates", {"enum": [0, 0]}, 0)
    add("enum-bool-distinct", {"enum": [0]}, False, [issue("", "/enum", "enum", "enum-mismatch")])
    add("enum-true-distinct", {"enum": [1]}, True, [issue("", "/enum", "enum", "enum-mismatch")])
    add("enum-object-order", {"enum": [{"a": 1, "b": 2}]}, {"b": 2, "a": 1})
    add("enum-array-order", {"enum": [[1, 2]]}, [2, 1], [issue("", "/enum", "enum", "enum-mismatch")])
    add("enum-nested-kind", {"enum": [{"a": [0]}]}, {"a": [False]}, [issue("", "/enum", "enum", "enum-mismatch")])
    add("enum-literal-ref", {"enum": [{"$ref": "x", "properties": {}}]}, {"$ref": "x", "properties": {}})
    add("required-null", {"required": ["x"]}, {"x": None})
    add("required-false", {"required": ["x"]}, {"x": False})
    add("required-zero", {"required": ["x"]}, {"x": 0})
    add("required-absent", {"required": ["x"]}, {}, [issue("", "/required/0", "required", "required-missing")])
    add("required-empty-name", {"required": [""]}, {"": None})
    add("required-empty-list", {"required": []}, {})
    add("required-nonobject", {"required": ["x"]}, None)
    add("properties-absent", {"properties": {"x": False}}, {})
    add("properties-nonobject", {"properties": {"x": False}}, 0)
    add("properties-null", {"properties": {"x": {"type": "null"}}}, {"x": None})
    add("properties-false", {"properties": {"x": False}}, {"x": 0}, [issue("/x", "/properties/x", "boolean", "false-schema")])
    add("extras-absent", {}, {"x": 0})
    add("extras-true", {"additionalProperties": True}, {"x": 0})
    add("extras-false", {"additionalProperties": False}, {"x": 0}, [issue("/x", "/additionalProperties", "additionalProperties", "additional-property")])
    add("extras-nonobject", {"additionalProperties": False}, [])
    add("declared-failing-covered", {"properties": {"x": False}, "additionalProperties": False}, {"x": 0}, [issue("/x", "/properties/x", "boolean", "false-schema")])
    add("mixed-no-short-circuit", {"type": "array", "enum": [], "required": ["b", "a"], "properties": {"z": False}, "additionalProperties": False}, {"z": 0, "c": 1}, [issue("", "/type", "type", "type-mismatch"), issue("", "/enum", "enum", "enum-mismatch"), issue("", "/required/1", "required", "required-missing"), issue("", "/required/0", "required", "required-missing"), issue("/z", "/properties/z", "boolean", "false-schema"), issue("/c", "/additionalProperties", "additionalProperties", "additional-property")])
    add("escaped-property", {"properties": {"~/": False}}, {"~/": 0}, [issue("/~0~1", "/properties/~0~1", "boolean", "false-schema")])
    add("empty-property-pointer", {"properties": {"": False}}, {"": 0}, [issue("/", "/properties/", "boolean", "false-schema")])
    add("unknown-root", {"title": "x"}, 0, unsupported=[feature("/title", "title")])
    add("unknown-absent-child", {"properties": {"x": {"$ref": "x"}}}, {}, unsupported=[feature("/properties/x/$ref", "$ref")])
    add("unknown-irrelevant-child", {"properties": {"x": {"format": "x"}}}, 0, unsupported=[feature("/properties/x/format", "format")])
    add("additional-schema-empty", {"additionalProperties": {}}, {}, unsupported=[feature("/additionalProperties", "additionalProperties", "nonboolean-additional-schema")])
    add("unsupported-all-sorted", {"zzz": 0, "properties": {"x": {"$ref": "x"}}, "additionalProperties": {"aaa": 0}}, None, unsupported=[feature("/additionalProperties", "additionalProperties", "nonboolean-additional-schema"), feature("/additionalProperties/aaa", "aaa"), feature("/properties/x/$ref", "$ref"), feature("/zzz", "zzz")])
    add("nested-evaluation", {"properties": {"o": {"required": ["x"]}}}, {"o": {}}, [issue("/o", "/properties/o/required/0", "required", "required-missing")])
    add("unicode-distinct", {"enum": ["é"]}, "e\u0301", [issue("", "/enum", "enum", "enum-mismatch")])
    add("sorted-children", {"properties": {"z": False, "a": False}}, {"z": 1, "a": 2}, [issue("/a", "/properties/a", "boolean", "false-schema"), issue("/z", "/properties/z", "boolean", "false-schema")])
    extra128 = {"k%03d" % index: 0 for index in range(128)}
    add("issue-boundary-128", {"additionalProperties": False}, extra128, [issue("/k%03d" % index, "/additionalProperties", "additionalProperties", "additional-property") for index in range(128)])
    diagnostics = []
    def diag(name, definition, instance, reason="invalid definition", code=2, **updates):
        inp = envelope(definition, instance); inp.update(updates)
        expected = dict(status="unsupported" if code == 3 else "error", reason=reason)
        diagnostics.append(dict(name=name, input=inp, exit=code, stderr=pack(expected)))
    for name, definition in [("root-null", None), ("type-unknown", {"type": "wat"}), ("type-empty", {"type": []}), ("type-duplicate", {"type": ["null", "null"]}), ("required-null", {"required": None}), ("required-duplicate", {"required": ["x", "x"]}), ("properties-list", {"properties": []}), ("child-null", {"properties": {"x": None}}), ("additional-null", {"additionalProperties": None}), ("enum-nonlist", {"enum": 0}), ("malformed-behind-unknown", {"$ref": "x", "properties": {"x": {"required": False}}})]:
        diag(name, definition, None)
    diag("future-shape-first", {"required": False}, 0, dialect="future")
    diag("future-profile", {}, 0, "unsupported schema", 3, schema="future")
    diag("future-dialect", {}, 0, "unsupported dialect", 3, dialect="future")
    diag("issue-overflow", {"additionalProperties": False}, {"k%03d" % i: 0 for i in range(129)}, "resource limit")
    first, second = "\U00010000" * 128, "\U00010001" * 128
    leaves = {"f%d" % i: {"required": ["m%02d" % j for j in range(16)]} for i in range(8)}
    definition = {"properties": {first: {"properties": {second: {"properties": leaves}}}}}
    instance = {first: {second: {"f%d" % i: {} for i in range(8)}}}
    rows = [issue("/" + first + "/" + second + "/f%d" % i, "/properties/" + first + "/properties/" + second + "/properties/f%d/required/%d" % (i, j), "required", "required-missing") for i in range(8) for j in range(16)]
    uncapped = report(definition, instance, rows)
    raw = json.dumps(envelope(definition, instance), ensure_ascii=False, separators=(",", ":")).encode()
    resource = dict(input=envelope(definition, instance), uncapped_report=uncapped, raw_bytes=len(raw), ascii_report_bytes=len(pack(uncapped).encode("ascii")), schema_nodes=11, schema_depth=4, issue_count=128, counts={"global": counts(envelope(definition, instance)), "definition": counts(definition), "instance": counts(instance)})
    if not resource["ascii_report_bytes"] > LIMITS["output_bytes"]: raise RuntimeError("Amplification prediction failed")
    for prefix, selected in resource["counts"].items():
        for key, number in selected.items():
            if number > LIMITS[prefix + "_" + key]: raise RuntimeError("Resource construction not admitted: " + prefix + key)
    diag("output-overflow", definition, instance, "resource limit")
    Path("fixtures").mkdir(exist_ok=True)
    for path, value in [("fixtures/oracles.json", dict(cases=cases, diagnostics=diagnostics)), ("fixtures/resources.json", resource)]:
        with open(path, "x", encoding="ascii", newline="\n") as handle: handle.write(pack(value))
    print(json.dumps(dict(full_reports=len(cases), diagnostics=len(diagnostics), raw_bytes=resource["raw_bytes"], report_bytes=resource["ascii_report_bytes"], counts=resource["counts"])))


if __name__ == "__main__":
    main()
