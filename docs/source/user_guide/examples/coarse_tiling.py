# Copyright 2025 The Torch-Spyre Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Coarse tiling with a Spyre compiler hint.

This script tiles a simple elementwise add across named dimensions using
spyre_hint(num_tiles_per_dim=...), which splits dimension A of a 256x256 add
into four tiles. The named dimensions are declared and attached to the device
tensors before compilation. It requires a Spyre device to run.
"""
import torch

from torch_spyre._inductor import spyre_hint
from torch_spyre._inductor.wsr import propagate_named_dims as named_dims

DEVICE = torch.device("spyre")
torch.manual_seed(0xAFFE)

# Build inputs on CPU
x = torch.randn(256, 256, dtype=torch.float16)
y = torch.randn(256, 256, dtype=torch.float16)

# Compute the reference on CPU
cpu_result = x + y


def add_tiled(a, b):
    with spyre_hint(num_tiles_per_dim={"A": 4}):
        with spyre_hint(expected_named_dims=["A", "B"]):
            return a + b


# Declare the named dimensions and attach them to the device tensors
named_dims.reset()
named_dims.declare_tensor_dim("A", 256)
named_dims.declare_tensor_dim("B", 256)
x_device = x.to(DEVICE)
y_device = y.to(DEVICE)
named_dims.name_tensor_dims(x_device, ["A", "B"])
named_dims.name_tensor_dims(y_device, ["A", "B"])

# Compute on the device in compiled mode and bring the result back to the host
compiled = torch.compile(add_tiled)
compiled_result = compiled(x_device, y_device).cpu()

# Print the results and compare them
print(f"CPU result\n{cpu_result}")
print(f"Spyre Compiled result\n{compiled_result}")
cpu_delta = torch.abs(compiled_result - cpu_result).max()
print(f"Max delta Compiled Spyre vs. CPU: {cpu_delta}")
