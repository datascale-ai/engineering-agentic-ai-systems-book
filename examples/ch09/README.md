# Ch09: task decomposition and planning

This is a chapter-local teaching proposal, **not a frozen public Plan API**.
No network, model, credentials or real approvals are used. All cases and code
are original and use the repository MIT license. Third-party papers are kept
outside this directory in ignored private storage.

From the repository root (Python 3.11+):

```powershell
python examples/ch09/make_cases.py
python examples/ch09/run_experiment.py
python examples/ch09/trace_plan.py
python -m pytest tests/ch09 -q
```

Expected: 20 synthetic cases and 60 case/arm records; all commands exit 0.
`results/exp09-01/summary.json` contains the actual environment, code/input
SHA-256, one-run timing and counts. Wall-clock timings can vary. For independent
reproduction, write to a new directory with `--output-dir <chapter-local-path>`
and compare semantic counts, excluding timing and machine metadata. Do not
claim independent reproduction for an author rerun.

Assets:

- `proposals/plan_schema.json`: the only Ch09 experimental schema; do not copy
  it to a public contracts directory. Replace with an authoritative reference
  after A/F and consumers approve migration.
- `plan_validator.py`: schema-subset shape checks, trusted model checks, all
  serial topological order validation and a separate bounded feasibility search.
- `make_cases.py`, `plan_cases.jsonl`: reproducible original data, stable IDs
  CH09-SYN-01..20, with 15 model-feasible goals and 5 model-infeasible goals.
- `run_experiment.py`: constrained text adapter, independent mock execution
  logic, evidence observation, failure injection, three-arm output.
- `trace_plan.py`, `results/worked_traces.json`: ten worked examples from the
  same twenty cases, separating candidate validation, goal feasibility and
  guarded direct mock execution. This does not add a fourth experiment arm.
- `results/exp09-01/`: actual deterministic mock results, not LLM measurements.

The data are twenty closely related instances over six tools, not twenty
independent domains. Case 06 omits approval, 07 eligibility, 08 has a cycle,
09 omits a causal edge, 10 understates resource cost. Cases 14/15 pass static
checks but fail on runtime tool drift / HTTP success without business effects.
Cases 16..20 are infeasible because approval is unavailable, submission is
unavailable, minimum cost 7 exceeds budget 6, goals conflict, or no action can
produce the goal. These labels can be checked without relying on the validator.

The text adapter only accepts exact `- 使用 tool。` lines; it supplies a serial
order and trusted fields, so comparisons are confounded. Arm 3 additionally
uses bounded state-space search for feasibility diagnosis; its benefits and
costs cannot be attributed to JSON formatting. All arms retain execution-time
approval/precondition/budget guards. No rejected plan receives completion
events or fabricated evidence.

Limits: trusted environments must be well-formed; state uses finite positive
propositions and delete effects; approval is a single-request mock fact.
Validation covers serializations, not overlapping concurrent actions. The
shape checker supports only this schema's keyword subset. UNKNOWN is a proof
budget limit, INVALID rejects a candidate, and UNSAT_MODEL is confined to the
finite trusted model. No guarantee of real-world execution or optimality is
made. Model experiments and D's independent review/reproduction remain pending.

Figure deliverables follow the user's 2026-11-02 instruction: prompts only in
`docs/images/ch09/Fig-09-01.prompt.txt` and `Fig-09-02.prompt.txt`; tables remain
editable CSV. Full Chinese exposition is in the Ch09 manuscript.
