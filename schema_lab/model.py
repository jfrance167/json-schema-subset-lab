"""Bounded definition grammar, support assessment and conjunctive evaluation."""
import json
from .contract import LIMITS, SCHEMA, DIALECT, LabError, Unsupported, admit, bound, _walk

TYPES = {"object": dict, "array": list, "string": str, "number": int,
         "integer": int, "boolean": bool, "null": type(None)}
KEYWORDS = {"type", "enum", "required", "properties", "additionalProperties"}


def _bad():
    raise LabError("invalid definition")


def _pointer(parent, name):
    return parent + "/" + name.replace("~", "~0").replace("/", "~1")


def _clone(value):
    if type(value) is dict:
        return {key: _clone(child) for key, child in value.items()}
    if type(value) is list:
        return [_clone(child) for child in value]
    return value


def _equal(left, right):
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(_equal(value, right[key]) for key, value in left.items())
    if type(left) is list:
        return len(left) == len(right) and all(_equal(a, b) for a, b in zip(left, right))
    return left == right


def _distinct_strings(value, maximum, allowed=None):
    if type(value) is not list:
        _bad()
    bound(len(value), maximum)
    if any(type(item) is not str for item in value) or len(set(value)) != len(value):
        _bad()
    if allowed is not None and (not value or any(item not in allowed for item in value)):
        _bad()


def _enum_bounds(definition):
    # Generic admission has bounded the whole tree. Check every recognizable
    # enum member before grammar errors can short-circuit required resource work.
    if type(definition) is not dict:
        return
    choices = definition.get("enum")
    if type(choices) is list:
        bound(len(choices), LIMITS["enum"])
        for choice in choices:
            _walk(choice, "enum_value")
    children = definition.get("properties")
    if type(children) is dict:
        for name in sorted(children):
            _enum_bounds(children[name])
    additional = definition.get("additionalProperties")
    if type(additional) is dict:
        _enum_bounds(additional)


def _scan(definition, pointer, depth, count, features):
    # Scan every actual schema position before evaluation. Literal enum objects
    # and unknown payloads are generic data, never executable schema positions.
    count[0] += 1
    bound(count[0], LIMITS["schema_nodes"])
    bound(depth, LIMITS["schema_depth"])
    if type(definition) is bool:
        return
    if type(definition) is not dict:
        _bad()
    if "type" in definition:
        selected = definition["type"]
        if type(selected) is str:
            if selected not in TYPES:
                _bad()
        else:
            _distinct_strings(selected, LIMITS["type_options"], TYPES)
    if "enum" in definition:
        choices = definition["enum"]
        if type(choices) is not list:
            _bad()
        bound(len(choices), LIMITS["enum"])
    if "required" in definition:
        _distinct_strings(definition["required"], LIMITS["required"])
    if "properties" in definition:
        children = definition["properties"]
        if type(children) is not dict:
            _bad()
        bound(len(children), LIMITS["properties"])
        for name in sorted(children):
            _scan(children[name], _pointer(_pointer(pointer, "properties"), name), depth + 1, count, features)
    if "additionalProperties" in definition:
        extra = definition["additionalProperties"]
        if type(extra) is dict:
            _scan(extra, _pointer(pointer, "additionalProperties"), depth + 1, count, features)
        elif type(extra) is not bool:
            _bad()
    # Collect only after each position's supported shapes have been checked.
    # A feature cap may abort work, but no unsupported or valid verdict is emitted.
    for name in sorted(definition):
        if name not in KEYWORDS:
            _feature(features, _pointer(pointer, name), name, "unknown-keyword")
        elif name == "additionalProperties" and type(definition[name]) is dict:
            _feature(features, _pointer(pointer, name), name, "nonboolean-additional-schema")


def _feature(features, pointer, keyword, reason):
    bound(len(features) + 1, LIMITS["unsupported"])
    features.append(dict(definition_pointer=pointer, keyword=keyword, reason=reason))


def _issue(issues, instance_pointer, definition_pointer, keyword, reason):
    bound(len(issues) + 1, LIMITS["issues"])
    issues.append(dict(instance_pointer=instance_pointer, definition_pointer=definition_pointer,
                       keyword=keyword, reason=reason))


def _evaluate(definition, instance, dp, ip, issues):
    if type(definition) is bool:
        if not definition:
            _issue(issues, ip, dp, "boolean", "false-schema")
        return
    if "type" in definition:
        selected = definition["type"]
        names = [selected] if type(selected) is str else selected
        if not any(type(instance) is TYPES[name] for name in names):
            _issue(issues, ip, _pointer(dp, "type"), "type", "type-mismatch")
    if "enum" in definition and not any(_equal(instance, choice) for choice in definition["enum"]):
        _issue(issues, ip, _pointer(dp, "enum"), "enum", "enum-mismatch")
    if type(instance) is dict:
        missing = [(name, index) for index, name in enumerate(definition.get("required", [])) if name not in instance]
        for _name, index in sorted(missing):
            _issue(issues, ip, _pointer(_pointer(dp, "required"), str(index)), "required", "required-missing")
        declared = definition.get("properties", {})
        for name in sorted(declared):
            if name in instance:
                _evaluate(declared[name], instance[name], _pointer(_pointer(dp, "properties"), name), _pointer(ip, name), issues)
        if definition.get("additionalProperties", True) is False:
            for name in sorted(instance.keys() - declared.keys()):
                _issue(issues, _pointer(ip, name), _pointer(dp, "additionalProperties"), "additionalProperties", "additional-property")


def analyze(envelope):
    """Return complete detached report/status or a fixed LabError diagnostic.

    Exact builtin synthetic JSON values only; no caller mutation, concurrent
    mutation support, reference resolution or complete dialect conformance.
    """
    admit(envelope)
    _enum_bounds(envelope["definition"])
    features = []
    _scan(envelope["definition"], "", 1, [0], features)
    if envelope["schema"] != SCHEMA:
        raise Unsupported("unsupported schema")
    if envelope["dialect"] != DIALECT:
        raise Unsupported("unsupported dialect")
    features.sort(key=lambda row: (row["definition_pointer"], row["keyword"], row["reason"]))
    issues = []
    if not features:
        _evaluate(envelope["definition"], envelope["instance"], "", "", issues)
    report = dict(profile=SCHEMA, basis="2020-12-keyword-subset",
        assumption="synthetic supplied schema and instance; no authorization or safety verdict",
        limits=dict(LIMITS), definition=_clone(envelope["definition"]), instance=_clone(envelope["instance"]),
        support="unsupported" if features else "supported", valid=None if features else not issues,
        issues=issues, unsupported=features)
    return report, 3 if features else 1 if issues else 0


def render(report):
    """Encode a complete report, checking physical ASCII bytes before delivery."""
    text = json.dumps(report, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False) + "\n"
    bound(len(text.encode("ascii")), LIMITS["output_bytes"])
    return text
