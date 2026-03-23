# Supported Operations

This page lists the PyTorch operations that Torch-Spyre supports via
`torch.compile`. Operations are grouped by category.

For details on how operations are implemented and how to add new ones,
see [Adding Operations](../compiler/adding_operations.md).

## Operations Table

| Operation | Execution | Notes |
|-----------|-----------|-------|
| **Matrix Operations** | | |
| `torch.mm` | Spyre | |
| `torch.matmul` | Spyre | |
| `torch.addmm` | Spyre | Decomposed to `mm` + `add` |
| `torch.bmm` | Spyre | |
| `torch.nn.functional.linear` | Spyre | Decomposed to `matmul` + `add` |
| **Activation Functions** | | |
| `torch.nn.functional.softmax` | Spyre | |
| `torch.nn.functional.layer_norm` | Spyre | Custom decomposition |
| `torch.nn.functional.rms_norm` | Spyre | Custom decomposition |
| `torch.nn.functional.gelu` | Spyre | Custom op + lowering |
| `torch.nn.functional.silu` | Spyre | |
| `torch.nn.functional.relu` | Spyre | |
| `torch.nn.functional.sigmoid` | Spyre | |
| `torch.nn.functional.softplus` | Spyre | Custom op + lowering |
| `torch.nn.functional.dropout` | Spyre | |
| **Pointwise Unary** | | |
| `torch.abs` | Spyre | |
| `torch.neg` | Spyre | |
| `torch.exp` | Spyre | |
| `torch.log` | Spyre | |
| `torch.sqrt` | Spyre | |
| `torch.rsqrt` | Spyre | |
| `torch.reciprocal` | Spyre | |
| `torch.tanh` | Spyre | |
| `torch.logical_not` | Spyre | Custom decomposition |
| `torch.clamp` | Spyre | Custom op + lowering |
| **Pointwise Binary** | | |
| `torch.add` | Spyre | |
| `torch.sub` | Spyre | |
| `torch.mul` | Spyre | |
| `torch.div` | Spyre | |
| `torch.where` | Spyre | |
| **Comparison** | | |
| `torch.eq` | Spyre | |
| `torch.ne` | Spyre | |
| `torch.gt` | Spyre | Custom decomposition |
| `torch.lt` | Spyre | Custom decomposition |
| `torch.ge` | Spyre | |
| `torch.le` | Spyre | |
| **Reduction** | | |
| `torch.sum` | Spyre | |
| `torch.mean` | Spyre | |
| `torch.amax` | Spyre | |
| `torch.amin` | Spyre | |
| `torch.max` | Spyre | |
| **Tensor Shape** | | |
| `torch.reshape` / `torch.view` | Spyre | |
| `torch.transpose` | Spyre | |
| `torch.permute` | Spyre | |
| `torch.clone` | Spyre | |
| `torch.squeeze` | Spyre | |
| `torch.unsqueeze` | Spyre | |
| `torch.cat` | Spyre | |
| **Tensor Creation** | | |
| `torch.ones` | Spyre | Custom decomposition |
| `torch.full` | Spyre | Custom decomposition |
| **CPU Fallback** | | |
| `torch.embedding` | CPU fallback | Runs on CPU, result transferred back |
| `torch.arange` | CPU fallback | Runs on CPU, result transferred back |
| `torch.sin` | CPU fallback | Runs on CPU, result transferred back |
| `torch.cos` | CPU fallback | Runs on CPU, result transferred back |
| `torch.tril` | CPU fallback | Runs on CPU, result transferred back |
| `torch.triu` | CPU fallback | Runs on CPU, result transferred back |

> **Note:** The **Execution** column indicates whether an operation runs
> natively on the Spyre accelerator or falls back to CPU execution.
> CPU fallback ops are automatically handled by the compiler — a warning
> is emitted when fallback occurs.
>
> This table reflects the operations validated in the torch-spyre test
> suite at the time of writing. Coverage grows continuously — check the
> [test suite](https://github.com/torch-spyre/torch-spyre/tree/main/tests)
> for the latest state.

## Unsupported Operations

Operations not listed above will either:
- **Fall back to CPU** — if Inductor cannot lower the op to a Spyre
  kernel, it falls back to CPU execution. A warning is emitted.
- **Raise a compile-time error** — if the op produces a tensor layout
  that is incompatible with downstream Spyre ops.

To request support for a new operation or to contribute one yourself,
see [Adding Operations](../compiler/adding_operations.md).
