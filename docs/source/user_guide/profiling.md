# Profiling

Torch-Spyre provides tooling to measure and diagnose the performance of
PyTorch workloads running on the Spyre accelerator.

For the full design of the planned profiling toolkit, see
[RFC 0601 — Spyre Profiling Toolkit](https://github.com/torch-spyre/rfcs/blob/main/0601-SpyreProfilingToolkit/0601-SpyreProfilingToolkitRFC.md).

## What Can Be Profiled Today

The following profiling capabilities are available in the current release:

- **Compilation time** — time spent in the front-end and back-end compilers
- **Kernel execution time** — wall-clock time per kernel on device
- **Memory usage** — peak DDR allocation during a forward pass
- **Work division efficiency** — core utilization for each operation

### Inductor Logging

Spyre-specific logging environment variables provide visibility into
the compilation pipeline:

| Variable | Effect |
|----------|--------|
| `SPYRE_INDUCTOR_LOG=1` | Enable Spyre Inductor logging |
| `SPYRE_INDUCTOR_LOG_LEVEL=DEBUG` | Set log verbosity (DEBUG, INFO, WARNING, ERROR) |
| `SPYRE_LOG_FILE=path/to/file.log` | Redirect Spyre log output to a file |
| `TORCH_LOGS="+inductor"` | Enable verbose PyTorch Inductor logging |

### Integration with PyTorch Profiler

Torch-Spyre emits events compatible with `torch.profiler.profile`, so
standard PyTorch profiling tools (TensorBoard, Chrome trace viewer) can
be used to visualize CPU-side results.

```python
import torch
from torch.profiler import profile, ProfilerActivity

with profile(activities=[ProfilerActivity.CPU]) as prof:
    output = compiled_model(x)

print(prof.key_averages().table(sort_by="cpu_time_total"))
```

## Planned: Spyre Profiling Toolkit

:::{admonition} Work in Progress
:class: warning

The Spyre Profiling Toolkit described below is under active development
as part of [RFC 0601](https://github.com/torch-spyre/rfcs/blob/main/0601-SpyreProfilingToolkit/0601-SpyreProfilingToolkitRFC.md).
The APIs and tools listed here reflect the **planned design** and are
not yet available. This section is provided so users and contributors
can understand the direction and provide early feedback.
:::

The toolkit will span the full stack, providing profiling at multiple
levels and granularities:

| Layer | Tool | Granularity | Status |
|-------|------|-------------|--------|
| Application / PyTorch | Spyre Extension for PyTorch Profiler | Kernel-level | In progress |
| Compiler Frontend | Enhanced Inductor Provenance Tracking | Pass-level | Planned |
| Compiler Backend | IR Instrumentation-based Fine-Grained Profiler | Intra-kernel | Planned |
| Runtime | Profiling Tools Interface (libaiupti) | Kernel + memory | In progress |
| Device Driver / HW | AIU SMI | Device-level | Available |
| Post-processing | aiu-trace-analyzer | Derived metrics | Available |

### Planned: Device-Side Profiling via PyTorch Profiler

The toolkit will integrate with the PyTorch Profiler through the
`REGISTER_PRIVATEUSE1_PROFILER` mechanism, allowing Spyre workloads to
be profiled with `ProfilerActivity.PrivateUse1`:

```python
import torch
import torch_spyre
from torch.profiler import profile, ProfilerActivity

model = torch.compile(MyModel().to("spyre"))
inputs = torch.randn(1, 3, 224, 224, device="spyre", dtype=torch.float16)

with profile(
    activities=[ProfilerActivity.CPU, ProfilerActivity.PrivateUse1],
    record_shapes=True,
    profile_memory=True,
) as prof:
    output = model(inputs)

# Print a summary table of kernel execution times
print(prof.key_averages().table(sort_by="self_device_time_total"))

# Export a Chrome/Perfetto trace for visualization
prof.export_chrome_trace("spyre_trace.json")
```

This integration will provide:

- Input shapes for each operation
- Execution and memory timelines for CPU and Spyre operations
- Call stack and file/line numbers
- Spyre kernel name, execution time, and invocation count
- Reserved, allocated, and peak memory for the workload

### Planned: Memory Profiling

Spyre has a **dual-memory hierarchy** requiring separate tracking:

| Memory | Managed by | Observable at |
|--------|-----------|---------------|
| DDR (device memory) | Runtime allocator | Runtime |
| Scratchpad (on-chip) | Compiler + LX planner | Compile-time + runtime |

**DDR memory APIs** (planned):

- `torch.spyre.memory_allocated()` — current DDR usage
- `torch.spyre.max_memory_allocated()` — peak DDR usage
- `torch.spyre.memory_reserved()` — reserved DDR pool size

**Scratchpad metrics** (planned):

- Peak and average scratchpad utilization
- Fragmentation and reuse rate

### AIU SMI

AIU SMI is a command-line monitoring tool for Spyre devices, similar to
`nvidia-smi`. It currently reports:

- Power consumption and temperature
- PT array utilization %
- Bandwidth (device memory read/write, PCIe rx/tx)
- Reserved and active memory
- Process-to-VF mapping

Memory statistics and multi-card metrics are being expanded.

### Planned: Dataflow-Specific Metrics

These metrics are unique to Spyre's dataflow architecture and have no
direct analog in GPU profiling:

| Metric | Description |
|--------|-------------|
| Pipeline utilization | Fraction of functional units active per cycle |
| DMA overhead | Transfer time between DDR and scratchpad |
| Reconfiguration latency | Time to load new dataflow configurations between kernels |
| Inter-core communication | Work division efficiency across up to 32 cores |
| Stick alignment overhead | Padding/reformatting cost for 128-byte stick misalignment |

### Planned: Compile-Time vs Runtime Profiling Boundary

| Metric category | Compile-time | Runtime | Both |
|-----------------|:---:|:---:|:---:|
| Scratchpad allocation decisions | X | | |
| Work division planning | X | | |
| Op selection / fusion decisions | X | | |
| Kernel execution time | | X | |
| DDR bandwidth | | X | |
| Memory allocation/deallocation | | X | |
| IR instrumentation profiling | | | X |
| Provenance tracking | | | X |
| Power and temperature | | X | |

## Trace Analysis with aiu-trace-analyzer

The [**aiu-trace-analyzer**](https://github.com/IBM/aiu-trace-analyzer)
is an open-source post-processing tool for traces generated by the
PyTorch Profiler. It provides:

- Process memory consumption breakdown
- Execution time breakdown (computation, communication, memory, idle)
- Overlap analysis between communication and computation
- Kernel launch analysis and idle time analysis

Visualization targets [Perfetto](https://ui.perfetto.dev/) as the
primary trace viewer.

Planned improvements include removing the dependency on compiler logs
for utilization data, multi-Spyre support for cross-card trace
correlation, and a device-agnostic abstraction layer for upstream
contribution to HTA.

## See Also

- [Debugging Guide](debugging.md) — systematic debugging workflow
- [Running Models](running_models.md) — `torch.compile` usage
- [Compiler Architecture](../compiler/architecture.md) — compilation
  pipeline overview
- [RFC 0601](https://github.com/torch-spyre/rfcs/blob/main/0601-SpyreProfilingToolkit/0601-SpyreProfilingToolkitRFC.md) — full profiling toolkit design
