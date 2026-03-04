# Installation

## Prerequisites

- Python >= 3.11
- PyTorch ~= 2.9.1
- IBM Spyre Software Stack (required for hardware execution)

## Build Instructions

Building Torch-Spyre requires a development build of the IBM Spyre Software
Stack. If you are within IBM, instructions can be found in the internal
`#aiu-inductor` Slack channel.

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
