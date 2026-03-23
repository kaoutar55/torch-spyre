---
name: check-docs
description: "Check documentation consistency against code changes. Audits supported ops table, RFC links, API docs, compiler docs, runtime docs, profiling, and user/developer guides for staleness or drift."
---

# Check Documentation Consistency

You are auditing the torch-spyre documentation for consistency with the current
state of the codebase. Run through each section below systematically. Report
every issue found with the file path, what is wrong, and a suggested fix.

## Audience

Documentation serves two personas:

- **Users** — data scientists and ML engineers running models on Spyre via
  `torch.compile`. They care about: installation, quickstart, supported ops,
  profiling, debugging, and examples.
- **Developers** — engineers contributing to torch-spyre. They care about:
  compiler architecture, Inductor integration, adding operations, tensor
  layouts, work division, runtime internals, and RFCs.

Check that content is appropriate for its target audience and does not leak
internal implementation details into user-facing pages.

## 1. Supported Operations Table

**File:** `docs/source/user_guide/supported_operations.md`

- Cross-reference the ops table against the actual op registrations in:
  - `torch_spyre/_inductor/customops.py` (custom ops)
  - `torch_spyre/_inductor/decompositions.py` (decompositions)
  - `torch_spyre/_inductor/lowering.py` (lowerings)
  - `torch_spyre/ops/eager.py` (eager ops)
  - `torch_spyre/ops/fallbacks.py` (fallback registrations)
- Check for ops that exist in code but are missing from the table.
- Check for ops listed in the table that no longer exist in code.
- Verify the model coverage columns (GPT-2, Llama, Hybrid, ResNet-50) match
  what the test suite actually exercises in `tests/inductor/test_inductor_ops.py`
  and `tests/inductor/test_building_blocks.py`.

## 2. RFC Links and References

**File:** `docs/source/rfcs/index.md`

- All RFC links must point to `https://github.com/torch-spyre/rfcs` (external
  repo), NOT to `torch-spyre/torch-spyre/RFCs/` (old location, now deleted).
- Grep the entire `docs/` tree for any remaining references to the old RFC
  paths: `RFCs/`, `torch-spyre/torch-spyre/blob/main/RFCs`.
- Check that every RFC listed in the index table actually exists at the linked
  URL (verify the path structure: `<number>-<Name>/<number>-<Name>RFC.md`).
- Check for new RFCs in `https://github.com/torch-spyre/rfcs` that are not yet
  listed in the index.

## 3. Compiler Documentation

**Files:** `docs/source/compiler/*.md`

- **architecture.md** — Verify the compilation pipeline stages match the actual
  code flow in `torch_spyre/_inductor/__init__.py` and `spyre_kernel.py`.
- **inductor_frontend.md** — Check that extension points (PrePass, PostPass,
  SchedulerPass) match what is registered in `torch_spyre/_inductor/passes.py`
  and `torch_spyre/_inductor/pass_utils.py`.
- **backend.md** — Verify DeepTools invocation paths match `torch_spyre/_inductor/dsc.py`.
- **adding_operations.md** — Confirm the three patterns (direct mapping,
  decomposition, custom op) still match the current code patterns. Check that
  example ops cited still exist.
- **work_division_planning.md** — Verify op_dim_splits representation and
  dimension labels match `torch_spyre/_inductor/core_division.py`.
- **work_division_codegen.md** — Check code generation patterns match
  `torch_spyre/_inductor/codegen/compute_ops.py` and `data_ops.py`.

## 4. Runtime Documentation

**File:** `docs/source/runtime/overview.md`

- Verify device registration flow matches `torch_spyre/__init__.py`.
- Check allocator description matches `torch_spyre/csrc/spyre_mem.cpp`.
- Verify tensor implementation details match `torch_spyre/csrc/spyre_tensor_impl.cpp`.
- Check for new runtime features (e.g., streams in `torch_spyre/streams.py`,
  `torch_spyre/csrc/spyre_stream.cpp`) that are not yet documented.

## 5. API Reference

**Files:** `docs/source/api/torch_spyre.rst`, `torch_spyre/__init__.py`

- Verify that the public API surface exported by `torch_spyre/__init__.py`
  matches what autodoc will generate.
- Check that new public modules (e.g., `torch_spyre/ops/`, `torch_spyre/device/`,
  `torch_spyre/execution/`, `torch_spyre/memory/`, `torch_spyre/streams.py`)
  are included in the API docs or intentionally excluded.
- Verify type stubs (`torch_spyre/_C.pyi`, `torch_spyre/_hooks.pyi`) are
  consistent with the C++ bindings.

## 6. User Guide

**Files:** `docs/source/user_guide/*.md`

- **running_models.md** — Verify `torch.compile` usage examples are correct.
  Check that environment variables (SENCORES, etc.) match `torch_spyre/constants`
  and actual behavior.
- **tensors_and_layouts.md** — Verify SpyreTensorLayout fields match
  `torch_spyre/csrc/spyre_tensor_impl.h`. Check RFC links point to external repo.
- **profiling.md** — Check that profiling instructions match any new profiling
  infrastructure (e.g., logging utilities in `torch_spyre/_inductor/logging_utils.py`).
- **debugging.md** — Verify environment variables and compiler artifact paths
  are still accurate.
- **examples.md** — Check that referenced example scripts exist in `examples/`.

## 7. Getting Started

**Files:** `docs/source/getting_started/*.md`

- **installation.md** — Verify Python and PyTorch version requirements match
  `pyproject.toml` and `requirements/run.txt`.
- **quickstart.md** — Verify code examples actually work with current API.

## 8. Contributing Guide

**File:** `docs/source/contributing/guidelines.md`

- Verify development workflow instructions are current.
- Check that linting tools listed match `.pre-commit-config.yaml`.
- Verify test commands match `pytest.ini` configuration.

## 9. Inductor Integration Changes

Check for drift between docs and code in these areas:

- New passes added to `torch_spyre/_inductor/passes.py` or `temp_passes.py`
  that are not documented.
- New codegen patterns in `torch_spyre/_inductor/codegen/superdsc.py`.
- Changes to `torch_spyre/_inductor/wrapper.py` (host code generation).
- New modules like `torch_spyre/_inductor/views.py`,
  `torch_spyre/_inductor/multi_dim_reduction_pass.py`,
  `torch_spyre/_inductor/op_spec.py` that may need documentation.

## 10. Sensitive Content Audit

Scan all documentation files for:

- Internal Slack channel names (e.g., `#aiu-inductor`, `#torch-spyre`).
- Internal URLs (e.g., `*.ibm.com`, internal wikis, Jira links).
- Employee names or emails that should not be public.
- Proprietary tool names or internal codenames not meant for public docs.
- References to internal build systems or infrastructure.

Flag any findings and suggest replacements.

## 11. Cross-Reference and Link Integrity

- Check all relative links between docs pages resolve correctly.
- Check all external links (GitHub, PyTorch docs, Python docs) are valid.
- Verify image references in `_static/images/` — every referenced image exists,
  every image file is referenced somewhere.
- Check `intersphinx_mapping` in `conf.py` points to valid inventory URLs.

## 12. Build Verification

- Run `python -m sphinx docs/source docs/build/html -W --keep-going` and
  report any warnings or errors.
- Verify `suppress_warnings` in `conf.py` only suppresses intentional warnings
  (e.g., mocked autodoc), not real issues.

## Output Format

For each issue found, report:

```
### [SECTION] File: path/to/file.md

**Issue:** Description of the problem.
**Evidence:** What the docs say vs what the code shows.
**Fix:** Suggested correction.
**Severity:** critical | warning | info
```

At the end, provide a summary table:

| Section | Issues | Critical | Warnings | Info |
|---------|--------|----------|----------|------|
| ...     | ...    | ...      | ...      | ...  |
