# JSON Schema Subset Lab

An original standard-library Python learning tool that explains why a supplied synthetic value passes or fails a small schema. It supports boolean schemas and five keywords: `type`, `enum`, `required`, `properties`, and boolean `additionalProperties`. Unsupported definitions receive an explicit unassessed validity result. No installation or dependency download is needed.

The useful distinctions: required means presence, so null satisfies required; properties validates present members without requiring them; declared names remain covered by additionalProperties even when their child validation fails; boolean values differ from integers for type and enum equality. Empty and duplicate enums are allowed; an empty enum never matches. Object constraints are neutral on nonobject instances, while malformed or unsupported nested definitions are still checked.

## Run the synthetic demo

From this directory with Python (verified on Windows CPython3.13.7):

```powershell
python -m schema_lab samples/demo.json
python -m schema_lab samples/demo.json --output fresh-report.json
python -m schema_lab --help
```

The demo exits1 and reports three issues: `/port` has type and enum mismatches, and `/extra` is an additional property. There is no required-missing issue because port is present with null. The saved `samples/demo-report.json` is an actual checked CLI result. Output paths must be fresh; existing files and input aliases are refused.

| Exit | Meaning |
|---|---|
|0|Complete supported schema, valid instance|
|1|Complete supported schema, invalid instance|
|2|Malformed input/definition, resource cap, command or delivery failure|
|3|Unsupported feature report (`valid: null`) or unknown outer profile/dialect diagnostic|

Envelope keys are exactly `schema`, `dialect`, `definition`, `instance`; labels are `schema-subset-lab/1` and `2020-12`. The dialect is a label, never a URL to fetch. Full exact grammar, report pointers, precedence and inclusive limits are in PLAN.md and the frozen SCHEMA.md. No automatic dialect detection or $schema interpretation.

## Architecture and API

`schema_lab/contract.py` performs strict byte/native admission, duplicate/number/Unicode/depth/tree bounds and checked regular-file reads. `model.py` checks all recognizable enum budgets, then every actual schema-position shape and support before any instance evaluation. It collects complete deterministic issue rows, with definition and instance pointers, and detaches echoed trees. `__main__.py` enforces checked ASCII+LF delivery and exclusive files. No imports from prior labs or third-party candidates.

```python
from schema_lab import analyze, render, LabError

envelope = {"schema": "schema-subset-lab/1", "dialect": "2020-12",
            "definition": {"required": ["x"]}, "instance": {"x": None}}
report, exit_code = analyze(envelope)  # valid, exit0
text = render(report)
```

`analyze` accepts exact builtin synthetic JSON values and raises fixed LabError/Unsupported diagnostics for admission/definition/resource/outer-support failure. `parse` accepts exact UTF8 bytes; `render` is for reports produced by analyze and trusted fixed diagnostics, not arbitrary untrusted Python objects. The API can build a logically bounded report whose physical serialization exceeds the byte cap; render rejects it before delivery.

## Security model and limits

Original synthetic fixtures only. No actual/private schemas, reference resolution (local or remote), schema regex execution, array applicators, combinators, annotations, executable schemas, authentication or safety verdict. Unknown keywords, including metadata, are conservatively unsupported. Schema-valued additionalProperties is assessed but unsupported. This policy is narrower than general JSON Schema, which can treat unknown keywords as annotations.

Only exact bounded integers are admitted (±9007199254740991); encoded fractions, exponents, nonfinite and negative-zero spellings reject. Number/integer coincide within this subset. Duplicate decoded keys, subclasses/custom objects, cycles, surrogates and Unicode noncharacters reject. Aliases count each occurrence and become separate snapshots; controls/invisible/private-use characters remain admitted and are escaped in JSON. Concurrent input mutation is excluded.

Input cap32768 bytes, schema positions64/depth4, definition/instance512 logical nodes each, issues/unsupported128 each, output262144 ASCII bytes. Full text/container/enum budgets are fixed in PLAN and every report. Limits are logical work bounds, not a hard RSS/time maximum. Actual3185-byte input produces814207 uncapped ASCII report bytes and is refused before stdout/file creation. Physical I/O can leave partial bytes on failure; observed metadata checks/exclusive files are not filesystem transactions or hostile-race containment.

## Verified checks and reusable tools

33 tests pass normally and under `-O`; each run includes all56 independently frozen full reports and16 diagnostics through actual CLI children, physical closed pipes/help/error/both streams, dirty/short/flush/close sinks and hardlink aliases. Nine targeted assertion mutants caught, zero harness errors, original hashes unchanged. Bandit1.9.4 runtime scan: zero findings/errors. See VALIDATION.md and REVIEW.md for exact scope, correction evidence and limits. Self-review is not independent assurance; hosted CI/CodeQL, other OS/runtimes, complete dialect conformance and comprehensive supply-chain audit are unverified/outside local scope.

```powershell
python -m unittest discover -v
python -O -m unittest discover -v
python -m compileall -q schema_lab tests scripts
python -m scripts.mutation_check .private/fresh-mutation-run
python -m bandit -r schema_lab -f json -o .private/fresh-bandit.json
```

Mutation helper input is trusted local runtime/tests/fixtures; output is fresh isolated copies, raw logs and summary.json. Its nine fixed transformations must each cause one assertion failure rather than setup/import errors. It never edits original source or deletes anything. `scripts/freeze_oracles.py` is the pre-core original authoring record, not a validator: it refuses to replace existing fixtures. Preserve frozen evidence; do not regenerate answers from the engine. App permission may be needed for synthetic hardlink tests.

## Sources, licensing and learning

RESEARCH.md records connected GitHub candidate/source/license/dependency/CI/issues inspection and [2020-12 core](https://json-schema.org/draft/2020-12/json-schema-core)/[validation](https://json-schema.org/draft/2020-12/json-schema-validation) evidence. Original MIT product for Jake, owned admission/CLI/mutation patterns adapted from prior accepted labs; third-party inert research retains its separate notices. Codex assisted implementation and ECC self-review; local draft results and rejection are disclosed in NOTICE.md. DECISIONS.md and LEARNING.md explain choices and mistakes. No new repository or publication performed.

Optional exercise: change the demo port from null to443 and remove extra, then predict the exit before running it.

## Publication

See [publication review](PUBLICATION.md). Private evidence and original histories remain local. CI runs normal/optimized tests, Bandit and CodeQL.
