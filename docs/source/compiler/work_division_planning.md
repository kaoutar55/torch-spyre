# Work Division Planning

Work division is the compiler stage that decides how each tensor operation
runs across the Spyre cores. The planner picks the splits along each loop
dimension that determine how many cores work on the op and which slice each
core owns. This page describes the algorithm, the hardware constraints that
drive it, and how its output is consumed downstream.

## Mental model

A `torch.compile` graph reaches the planner as a sequence of Inductor
operations. For every eligible op, the planner walks an iteration space of
loop variables, adjusts those variables to stick granularity, and commits
per-dimension split counts. Three sequential passes do the work:

```text
IR op
  │
  ▼  iteration_space_from_op        loop variables and their ranges
  │
  ▼  adjust_it_space_for_sticks     element counts → stick counts
  │
  ▼  Pass 1  span_reduction         mandatory; commits splits to keep
  │                                 every tensor under the 256 MB
  │                                 per-core span limit
  │
  ▼  Pass 2  k_fast_division        optional, gated by
  │                                 SPYRE_CORE_ID_K_FAST_EMISSION;
  │                                 claims narrow-N small-M matmuls
  │
  ▼  Pass 3  work_distribution      default; spends remaining cores
  │                                 on every op Pass 2 did not claim
  │
  ▼  op.op_it_space_splits          consumed by SDSC emission in
                                    codegen/superdsc.py
```

Pass 1 is about correctness. Passes 2 and 3 are about parallelism. Every
eligible op is divided by exactly one of Pass 2 or Pass 3.

## Motivation

Spyre exposes multiple processing cores that can run operations in parallel.
The planner has to balance four goals:

1. Use as many cores as possible.
2. Keep the per-core workload balanced.
3. Stay within the per-core memory span limit (256 MB).
4. Preserve operation semantics.

The planning phase analyses each op based on its type, tensor dimensions,
device layouts, and the available core budget. Co-optimisation across
adjacent ops, and integration with LX scratchpad placement, are open work
tracked in [Coordination with scratchpad planning](#coordination-with-scratchpad-planning).

## Hardware context

A few hardware constants drive every decision the planner makes.

:::{figure} ../_static/images/spyre-core-microarchitecture.png
:alt: Spyre core microarchitecture with two corelets, PT array, SFU, and shared LX scratchpad
:width: 50%
:align: center

A single Spyre core has two corelets sharing a 2 MB {term}`LX scratchpad`.
Each corelet has an 8 × 8 systolic {term}`PE array` driving the {term}`PT`
execution unit (so 8 PT rows per corelet) plus a 1D Special Function Unit.
A card has 32 cores connected by a bi-directional ring.
:::

| Constant | Value | Where it shows up |
|---|---|---|
| Cores per card | 32 (configurable down to 1 via `SENCORES`) | Total core budget Pass 3 distributes |
| PT rows per corelet | 8 | Pass 2's `rows_per_core` ceiling of `2 × 8 = 16` |
| Per-core memory span | 256 MB | Pass 1's correctness constraint |
| Stick size | 128 B (`BYTES_IN_STICK`); element count from `device_dtype.elems_per_stick()`: 64 at fp16, 32 at fp32, 128 at int8 | Stick-aligned splits across all passes |

For the full hardware overview see [Spyre Accelerator](../architecture/spyre_accelerator.md).
For the dataflow execution model see [Dataflow Architecture](../architecture/dataflow_architecture.md).

## Iteration Space

Every operation has an _iteration space_: the set of loop variables and
their ranges that together enumerate all output elements (for pointwise
ops) or all input elements (for reductions). A 2D pointwise op over an
output of shape `[M, N]` has iteration space `{c0: M, c1: N}`.

Stick variables are iteration variables whose range maps to the innermost
(stick) device dimension of some tensor. They are converted from element
counts to stick counts before planning, so core splits always land on
stick boundaries and each core receives a whole number of sticks. When
multiple tensors of different dtypes share a stick variable, the
conversion uses the largest `elems_per_stick` across those tensors. Fewer
sticks means a smaller adjusted size, which means fewer cores assigned to
that dimension.

## Hardware Memory Span Constraint

Each Spyre core has a 256 MB limit on the memory span it can address. The
_per-core span_ for a tensor is the contiguous range of device memory (in
bytes) that a single core must read or write under a particular split
assignment. The outermost device dimension a core touches sets the span:
`per_core_size * stride`, where `per_core_size` is the number of positions
along that dimension that each core covers.

Without splits a large tensor can violate this limit. The planner detects
violations and computes the minimum number of slices on the responsible
iteration variables that bring each tensor's span within range.

For stick variables, valid slice counts are restricted to divisors of the
stick count, so each core always receives a whole number of sticks. If the
same iteration variable is a stick variable for one tensor and a span
variable for another, and no slice count satisfies both constraints
simultaneously, the compiler raises an error at compile time.

:::{admonition} Common misconceptions
:class: warning

- **256 MB span is not 2 MB LX.** The span limit is a per-core *addressable
  device memory* range. The 2 MB LX scratchpad is a separate on-core SRAM
  whose placement is decided by [scratchpad planning](scratchpad_planning.md),
  not work division.
- **Stick size is dtype dependent.** A stick is always 128 bytes, but the
  element count comes from `device_dtype.elems_per_stick()`. Code that
  hard-codes "64 fp16 elements" is fp16-specific.
- **K-fast does not change correctness.** Pass 2's `(M=1, N, K>1)` split
  is correct on its own. The performance benefit comes from a paired
  codegen layer in `codegen/superdsc.py` that permutes physical core IDs
  so K-collaborators land on adjacent ring positions.
:::

## Planning Algorithm

The three passes live in
[work_division.py](https://github.com/torch-spyre/torch-spyre/blob/main/torch_spyre/_inductor/work_division.py)
and are dispatched from `CustomPreSchedulingPasses` in
[passes.py](https://github.com/torch-spyre/torch-spyre/blob/main/torch_spyre/_inductor/passes.py).

The passes only see *eligible* ops. `_iter_computed_buffers` filters to
`ComputedBuffer` instances and drops `FallbackKernel`, `ExternKernel`, and
the `SpyreConstantFallback` / `SpyreEmptyFallback` allocation kernels.
`span_reduction` and `work_distribution` then dispatch only on `Pointwise`
and `Reduction` IR data, and `divide_reduction_op` returns early for the
TopK reduction ops. Within that eligible set, every op is divided by
exactly one of Pass 2 or Pass 3.

### Pass 1 — Span Reduction (`span_reduction`)

This pass is mandatory and runs first over every eligible op.

For each operation, `span_reduction_pass` computes the minimum splits
required to keep every tensor's per-core memory span within 256 MB
(`must_split_vars`).

`must_split_vars` processes tensors one at a time. For each tensor whose
per-core span exceeds 256 MB, it iterates over device dimensions outer to
inner and searches for the best split combination (Cartesian product of
valid divisors for the variables contributing to that dimension) that
satisfies the hardware limit. The search applies a two-tier selection:
among combinations whose total core count does not exceed `max_cores`,
the planner prefers the one with the **largest span that still fits within
the limit** (fewest cores used). If no combination brings the span within
the limit, it falls back to the one with the **smallest span** (most
progress). Previously committed splits are carried forward as lower bounds
and narrow the search for subsequent tensors.

The resulting minimum splits are written to `op.op_it_space_splits` via
`apply_splits`. If no span violation exists, `op_it_space_splits` is left
unset.

The span is set by the outermost device dimension a single core touches.
Splitting that outermost dim halves each core's footprint:

```text
A: [8192, 32768] fp16, total 512 MB

Unsplit                          Split K by 2
┌───────────────────────────┐    ┌──────────────┬──────────────┐
│       512 MB per core     │    │ 256 MB / core│ 256 MB / core│
│   (violates 256 MB limit) │    │     core 0   │     core 1   │
└───────────────────────────┘    └──────────────┴──────────────┘
              ✗                                  ✓
```

The arithmetic generalises: `per_core_span = (dim_size / split) × outer_stride × dtype_bytes`.
Pass 1 picks the smallest `split` that brings the span under 256 MB on the
outermost dimension that violates it.

### Pass 2 — K-Fast Division (`k_fast_division`)

This pass is optional. It runs after Pass 1 and before Pass 3, and is
gated by the `core_id_k_fast_emission` config flag
(`SPYRE_CORE_ID_K_FAST_EMISSION`, default on).

Each Spyre corelet has 8 {term}`PT` rows. For matmuls with a small M, the
default Pass-3 strategy splits along M and gives each core only a handful
of rows to work on, so most PT rows sit idle. This pattern is common in
LLM inference, where the decode phase processes one token at a time (M is
typically 1 to 8) and a pure-M split leaves most of the chip unused.

K-fast targets this case. The goal is to keep all 32 cores active and
their PT arrays fed when M is small. The pass commits an
`(M=1, N, K>1)` split, so a wider tile lands on each core and the
reduction runs in parallel across cores. The trade-off is a cross-core
PSUM accumulation. The paired codegen layer covered later in this
section makes that accumulation cheap at runtime.

```text
Shape: A:[8, 1024] × W:[1024, 1024], 32 cores

Pure-M split (Pass 3 default)        K-fast split  (M=1, N=16, K=2)
─────────────────────────────        ──────────────────────────────
  M = 8 → 8 cores get 1 row each       Each core: full M=8 rows,
  Other 24 cores: nothing                          N=64 cols,
  Each PT (8 rows): 1 row used                     K=512 of K
  → most PT rows idle                  Each PT: 8 of 8 rows used,
                                       all 32 cores active
```

#### Decision tree

The pass walks a fixed sequence of gates. The first gate that fails sends
the op to Pass 3.

:::{figure} ../_static/images/work-division/k-fast-decision-tree.svg
:alt: K-fast decision tree showing seven yes/no gates, each routing to Pass 3 on failure, ending in Pass 2 committing the split
:width: 90%
:align: center

K-fast walks seven gates top to bottom. Any "no" exits to Pass 3
(default M-only). All seven "yes" answers commit `(M=1, n_split, k_split)`.
:::

The gates in detail:

- The op is `BATCH_MATMUL` (2D matmul or batched matmul).
- The op has exactly one reduction dim (the K dim) and exactly two output
  dims, so `(M, N, K)` is well-defined.
- `rows_per_core = M / max_cores` is between 1 and `2 × PT_ROWS` (16).
  Below 1, the M-only split cannot give every core a row. Above 16,
  pure-M already keeps the PT array busy.
- N and K are each exact multiples of `elems_per_stick`. For example at
  fp16 where `elems_per_stick = 64`, N = 99 fails this check (99 % 64 ≠ 0)
  and the op goes to Pass 3, because the K-fast split arithmetic works in
  whole sticks and a partial tail tile would leave per-core sizes uneven.
- K has at least `max_cores` sticks, so every core gets at least one
  K-stick after the split.
- For moderate M (`rows_per_core > PT_ROWS / 2`), N must be narrow enough
  that PT is starved (`n_sticks < max_cores`). Otherwise the default
  M-only split is fine.
- Pass 1 has not already committed a split on K or any M dim. K-fast's
  `(1, n, k>1)` shape cannot sit on top of a Pass-1 commit on those axes.

When the gates pass, the search runs over the *proper* divisors of
`max_cores`. The constraint `1 < n_split < max_cores` excludes both
endpoints, so neither extreme is picked. The search picks the largest
`n_split` that divides `n_sticks` cleanly such that
`k_split = max_cores // n_split` also divides `k_sticks`, and commits that
split. The op is added to a `k_fast_ops` list that Pass 3 consults to
skip already-divided ops.

K-fast has two layers. The planner picks the split here. The SDSC emitter
then permutes physical core IDs so K-collaborators land on adjacent ring
positions. The permutation lives in `_k_fast_core_to_slice_mapping` in
`codegen/superdsc.py`, gated by `_should_use_k_fast_mapping`. It drops
PSUM accumulation hops from `m × n` to 1, which is what makes the cross-core
reduction cheap. Without the permutation the planner's split is still
correct, but the runtime cost of the PSUM chain would erase the gain from
splitting along K in the first place.

### Pass 3 — Work Distribution (`work_distribution`)

This pass is the default for every op Pass 2 did not claim. It runs
after Pass 2 has finished across all operations.

For each remaining op, `work_distribution_pass` does three things:

1. It recovers the splits committed by Pass 1 by reading
   `op.op_it_space_splits` via `apply_splits_from_index_coeff`. The
   coeff-keyed encoding is the same one codegen uses, so it remains
   stable across compiler passes even as sympy symbols are renamed.
2. It ranks the remaining dimensions (those not already committed by
   Pass 1) for additional core assignment via `prioritize_dimensions`:
   output dimensions first by decreasing stick-adjusted size, reduction
   dimensions last. At most one reduction dimension is eligible for
   splitting, the one that maximises `core_split(size, remaining_cores)`
   after output dimensions have absorbed their share of cores. If Pass 1
   already committed a reduction split, no further reduction dimensions
   are eligible.
3. It distributes all `max_cores` across committed and priority dimensions
   with `multi_dim_iteration_space_split`. The function first applies the
   committed splits as minimum requirements, then greedily assigns the
   largest valid divisor of each remaining dimension to the leftover
   core budget.

The final splits overwrite `op.op_it_space_splits`.

:::{admonition} What gets written to `op.op_it_space_splits`
:class: note

The attribute is a `dict` keyed by the index coefficients of the buffer's
read and write index expressions (computed by `splits_by_index_coeff` in
[pass_utils.py](https://github.com/torch-spyre/torch-spyre/blob/main/torch_spyre/_inductor/pass_utils.py)),
with each coefficient mapping to its slice count. The coefficient encoding
is internal; downstream passes recover an iteration-variable view by
calling `apply_splits_from_index_coeff(splits, write_index, read_index, it_space)`.

For the worked example below, the user-facing view is `{M: 16, N: 1, K: 2}`
and codegen sees the equivalent coefficient-keyed encoding.
:::

## Worked example: large matmul on 32 cores

Take a single matmul with `A: [8192, 32768]`, `W: [32768, 4096]`,
`O: [8192, 4096]`, all fp16, on `SENCORES=32`. The iteration space is
`{M: 8192, K: 32768, N: 4096}`, with output dims `M`, `N` and reduction
dim `K`.

### Before/after the planner

| Tensor | Unsplit per-core span | Violating dim | Pass 1 commit | After Pass 3 | Cores reading it |
|---|---|---|---|---|---|
| A `[8192, 32768]` fp16 | 512 MB | K (outermost) | K split = 2 | M = 16, K = 2 | each core reads (512 rows) × (16384 K) = 16 MB |
| W `[32768, 4096]` fp16 | 256 MB | none (at limit) | — | M = 16, K = 2 | each core reads (16384 K) × (4096 N) = 128 MB |
| O `[8192, 4096]` fp16 | 64 MB | none | — | M = 16, K = 2 | each core writes (512 rows) × 4096 = 4 MB |

Pass 2 looks at the same op and computes `rows_per_core = 8192 / 32 = 256`,
far above the `2 × PT_ROWS = 16` ceiling. The very first row-count gate
fails, so k-fast skips the op.

Pass 3 inherits the 2-way K split from Pass 1. With 16 cores remaining
per K-slice, it ranks output dims by size (`M = 8192`, `N = 4096`) and
gives all 16 cores to `M`. Final split: `{M: 16, N: 1, K: 2}`.

| Dim | Size | Split | Per-core |
|---|---|---|---|
| M | 8192 | 16 | 512 rows |
| N | 4096 | 1 | 4096 cols |
| K (reduction) | 32768 | 2 | 16384 |

### Core grid

The 32 cores form a 16 × 2 grid: 16 along M, paired up across the K
split. Each row of the grid (cores `i` and `i+16`) accumulates one
M-slice's PSUM:

```text
M-slice:    0    1    2    3    4    5    6    7   ...   15
         ┌────┬────┬────┬────┬────┬────┬────┬────┬─────┬────┐
K = 0..  │ c0 │ c1 │ c2 │ c3 │ c4 │ c5 │ c6 │ c7 │ ... │c15 │
K = 1..  │c16 │c17 │c18 │c19 │c20 │c21 │c22 │c23 │ ... │c31 │
         └────┴────┴────┴────┴────┴────┴────┴────┴─────┴────┘
                                                          ↑
                                          PSUM(c_i, c_{i+16}) → row i
```

### A small-M, narrow-N counterexample

Switch to `A: [8, 1024]`, `W: [1024, 1024]` on 32 cores. Pass 1 commits
nothing (no span violation). Pass 2's gates all pass and it picks
`(M=1, N=16, K=2)`. Pass 3 skips the op.

## Coordination with scratchpad planning

Each pass plans one op at a time. When two adjacent ops share a tensor
but pick different per-core splits for it, the LX scratchpad planner
sees a core-division mismatch and disqualifies the shared tensor from
scratchpad reuse. The tensor falls back to a DDR round-trip even though
it could have stayed on-core.

```text
Aligned splits (LX reuse possible)        Mismatched splits (DDR round-trip)
──────────────────────────────────        ──────────────────────────────────
  Op A: split M=4, N=8                      Op A: split M=4, N=8
            │                                         │
            ▼                                         ▼
       ┌──────────┐                             ┌──────────┐
       │ tensor T │  stays on LX                │ tensor T │  spills to DDR
       └──────────┘                             └──────────┘
            │                                         │
            ▼                                         ▼
  Op B: split M=4, N=8                      Op B: split M=2, N=16
        ✓ reuse                                   ✗ DDR reload
```

A graph-aware co-optimisation pass is in development. It aligns splits
across adjacent ops to grow the LX planner's legal-reuse set. The work
is tracked in the [scratchpad planning](scratchpad_planning.md) doc.

## Operation-Specific Strategies

### Pointwise Operations

The iteration space is the output tensor's. All output dimensions are
candidates for splitting. There is no reduction dimension. Span-required
splits are computed jointly over all input and output tensors.

### Reduction Operations

Output dimensions are split first, by decreasing size. After output
dimensions have been assigned cores, at most one reduction dimension may
also be split: the one whose size has the most useful divisors for the
remaining core budget (it maximises `core_split(size, remaining_cores)`).
If Pass 1 already committed a reduction split to satisfy the span limit,
no further reduction dimension is split in Pass 3.

Span-required splits may include at most one reduction variable. If more
than one reduction variable must be split to satisfy the 256 MB limit,
the compiler raises an error.

For matrix multiplication the reduction dimension is K. Since all matrix
multiply variants (mm, bmm) have exactly one K dimension, K is treated
as any other reduction dimension by Pass 3: output dimensions (batch,
M, N) take priority by decreasing size, and K is only split when the
output dimensions cannot use all available cores. Pass 2 (k-fast) is
the exception. For the narrow-N small-M shape class, it intentionally
splits K to feed the PT array.

## Configuration

Work division is controlled by the `SENCORES` environment variable, which
specifies the maximum number of cores available for parallelisation.
Valid values range from 1 (no parallelisation) to 32 (maximum supported
cores).

## Limitations and Future Work

**Current limitations:**

- Dimensions must divide evenly by the slice count (no uneven splits).
- Only `Pointwise` and `Reduction` IR nodes are dispatched for work
  division. `ExternKernel` and `FallbackKernel` nodes are skipped.
- Each pass plans one op at a time. Adjacent ops can pick incompatible
  per-core splits for a shared tensor, which the LX scratchpad planner
  then treats as a core-division mismatch.
- K-fast is restricted to 2D `BATCH_MATMUL`. Batched matmul with a
  separate batch dim is not yet handled by k-fast (TODO at
  [`work_division.py:644`](https://github.com/torch-spyre/torch-spyre/blob/main/torch_spyre/_inductor/work_division.py#L644));
  those ops currently take Pass 3's default M-only split.
- Padding is approximated rather than retrieved from the layout (FIXME
  in `adjust_it_space_for_sticks`).

**Potential future enhancements:**

- Retrieve the correct padding from the layout instead of the current
  simplifying assumption.
- Add a graph-aware co-optimisation pass that aligns splits across
  adjacent ops to grow the LX legal-reuse set (see
  [Coordination with scratchpad planning](#coordination-with-scratchpad-planning)).
- Extend optimisation across operations to take data reuse and the wider
  memory hierarchy into account.
- Implement a bmm-aware k-fast policy that folds the batch dim into the
  M-side decision.

## See Also

- [Tensor Layouts](../user_guide/tensors_and_layouts.md) covers device
  layouts and the stick memory model.
- [Scratchpad Planning](scratchpad_planning.md) covers LX placement and
  the co-optimisation work.
- [Spyre Accelerator](../architecture/spyre_accelerator.md) gives the
  full hardware overview.
