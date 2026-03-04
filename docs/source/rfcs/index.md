# RFCs

This section lists the Request For Comments (RFCs) that describe the design
decisions behind Torch-Spyre. RFCs are written before implementation and serve
as a record of why things are built the way they are.

The full RFC sources live in the
[`RFCs/`](https://github.com/torch-spyre/torch-spyre/tree/main/RFCs)
directory of the repository. To propose a new RFC, open an issue first, then
copy the
[template](https://github.com/torch-spyre/torch-spyre/tree/main/RFCs/NNNN-template)
and submit a pull request.

## Index

| RFC | Title | Area |
|-----|-------|------|
| [0047](https://github.com/torch-spyre/torch-spyre/blob/main/RFCs/0047-TiledTensors/0047-TiledTensorsRFC.md) | Tensors with Device-Specific Layouts | Tensor layouts |
| [0171](https://github.com/torch-spyre/torch-spyre/blob/main/RFCs/0171-SpyreDevice/0171-SpyreDeviceRFC.md) | Spyre Device Construct in PyTorch | Device integration |
| [0264](https://github.com/torch-spyre/torch-spyre/blob/main/RFCs/0264-SpyreCICD/0264-SpyrePyTorchCICDRFC.md) | PyTorch CI/CD for IBM Spyre | CI/CD |
| [0682](https://github.com/torch-spyre/torch-spyre/blob/main/RFCs/0682-KtirSpec/0682-KtirSpecRFC.md) | Kernel Tile Intermediate Representation | Compiler IR |

## Summaries

### RFC 0047 — Tensors with Device-Specific Layouts

Defines the Spyre tiled tensor layout model: `device_size`, `dim_map`, and the
stick abstraction. Motivates why PyTorch's single-stride-per-dimension layout
cannot represent tiled tensors, and specifies the `SpyreTensorLayout` data
structure that maps between PyTorch coordinates and Spyre device memory.

See also: [Tensor Layouts](../user_guide/tensors_and_layouts.md)

### RFC 0171 — Spyre Device Construct in PyTorch

Describes how Spyre integrates as a first-class PyTorch device: registration
via `PrivateUse1`, dispatch keys, allocator, and the `torch.compile` Inductor
backend hook. Covers the design choices behind device naming and the extension
mechanism used to avoid upstream PyTorch changes.

See also: [Architecture Overview](../architecture/index.rst)

### RFC 0264 — PyTorch CI/CD for IBM Spyre

Specifies the continuous integration and continuous delivery pipeline for
Torch-Spyre, including test matrix, artifact publishing, and the GitHub Actions
workflow structure.

### RFC 0682 — Kernel Tile Intermediate Representation (KTIR)

Defines the Kernel Tile IR — an MLIR-based data-parallel intermediate
representation that replaces SuperDSC bundles as the target for the
Torch-Spyre compiler back-end. KTIR expresses tile-level operations,
scratchpad allocation, and DMA transfers in a hardware-independent form
that is then lowered to device-specific code by the DeepTools back-end.

See also: [Compiler Backend](../compiler/backend.md)
