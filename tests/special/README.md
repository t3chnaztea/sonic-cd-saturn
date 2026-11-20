# Special-stage release gate cases

`gate-cases.json` maps each case in `tools/zone_release_evidence.py`
`SPECIAL_CASES` to the command that proves it:

```json
"SP3-win": {"lane": "ss-retail",
            "command": ["python3", "tools/<tool>.py", "--stage", "3", "--output", "{out}"],
            "report": "{out}/report.json"}
```

`{out}` is the case folder under the zone-gates run (the tool creates it).
The report must carry `passed: true` and `disc_sha256` of the tested BIN.
`report` defaults to `{out}/report.json`; a repo-relative path is allowed.
Optional `group` puts the case in an existing serial group (for example
`test_cc2_route.py:build/cc1/controller` when the tool writes that folder);
the default group is `special`. Optional `before` lists argv commands run
first in the same run (prerequisites such as `tools/test_save_progression.py`).
Optional `exclusive: true` runs the case alone after every other group (it
writes folders many gates share, such as every route window's controller).
A case whose `command` is null is reported `missing` with its lane.

Run: `python3 tools/zone-gates.py --zones sp --gates special`. From V0.078 the
release matrix includes these 35 cases.
