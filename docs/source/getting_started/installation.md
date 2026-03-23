# Installation

## Prerequisites

- Python >= 3.11
- PyTorch ~= 2.10.0
- IBM Spyre Software Stack (required for hardware execution)

## Build Instructions

Building Torch-Spyre requires a development build of the IBM Spyre Software
Stack. Internal build instructions are available to IBM employees through
internal documentation channels.

Torch-Spyre is an active research project. We are working on an access program
for external contributors and research collaborators. Watch this repository for
updates or open an issue to express interest.

## Verify the Installation

Once installed, verify your setup with:

```python
import torch

x = torch.tensor([1, 2], dtype=torch.float16, device="spyre")
print(x.device)  # device(type='spyre', index=0)
```

## Running the Test Suite

```bash
python -m pytest tests/
```

## Next Steps

- [Quickstart](quickstart.md) — run your first model on Spyre
- [Tensors and Layouts](../user_guide/tensors_and_layouts.md) — understand how tensors work on Spyre
