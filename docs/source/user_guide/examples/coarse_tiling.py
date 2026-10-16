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
"""Coarse tiling with for_each_tile.

This script expresses an explicit tiled loop with for_each_tile. It splits
dimension 0 of a 256x256 computation into tiles of 64 rows, runs the body once
per tile to compute (a + b) * c on that tile, and lays each result tile back
into the output. It compares the compiled Spyre result against a CPU reference.
It requires a Spyre device to run.
"""

import torch

from torch_spyre._inductor.wsr.for_each_tile import for_each_tile

DEVICE = torch.device("spyre")
torch.manual_seed(0xAFFE)

# Build inputs on CPU
a = torch.randn(256, 256, dtype=torch.float16)
b = torch.randn(256, 256, dtype=torch.float16)
c = torch.randn(256, 256, dtype=torch.float16)


def fn(a, b, c):
    def body(_, tiles):
        a_tile, b_tile, c_tile = tiles
        y_tile = a_tile + b_tile
        return None, y_tile * c_tile

    # Tile dimension 0 into 64-row steps; out_dim=0 lays each step's tile back
    # into the full-size output. init=None makes this a map with no carry.
    _, z = for_each_tile(body, (a, b, c), dims=(0, 0, 0), tile_size=64, out_dim=0)
    return z


# Compute the reference on CPU as the equivalent untiled expression
cpu_result = (a + b) * c

# Send inputs to device
a_device = a.to(DEVICE)
b_device = b.to(DEVICE)
c_device = c.to(DEVICE)

# Compute on the device in compiled mode and bring the result back to the host
compiled = torch.compile(fn)
compiled_result = compiled(a_device, b_device, c_device).cpu()

# Print the results and compare them
print(f"CPU result\n{cpu_result}")
print(f"Spyre Compiled result\n{compiled_result}")
torch.testing.assert_close(compiled_result, cpu_result, atol=0.1, rtol=0.1)
cpu_delta = torch.abs(compiled_result - cpu_result).max()
print(f"Max delta Compiled Spyre vs. CPU: {cpu_delta}")
