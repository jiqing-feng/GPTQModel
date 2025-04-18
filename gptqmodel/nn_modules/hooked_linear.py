# Copyright 2024-2025 ModelCloud.ai
# Copyright 2024-2025 qubitium@modelcloud.ai
# Contact: qubitium@modelcloud.ai, x.com/qubitium
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
from typing import List, Optional, Tuple, Union

import torch
import transformers
from torch import Tensor
from torch.nn.modules.conv import _ConvNd


class HookedConvND(_ConvNd):
    def __init__(self,
        weight: Tensor,
        in_channels: int,
        out_channels: int,
        kernel_size: Tuple[int, ...],
        stride: Tuple[int, ...],
        padding: Union[str, Tuple[int, ...]],
        dilation: Tuple[int, ...],
        transposed: bool,
        output_padding: Tuple[int, ...],
        groups: int,
        padding_mode: str,
        bias: Optional[Tensor],
        _reversed_padding_repeated_twice: List[int]):

        torch.nn.Module.__init__(self)
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.kernel_size = kernel_size
        self.stride = stride
        self.padding = padding
        self.dilation = dilation
        self.transposed = transposed
        self.output_padding = output_padding
        self.groups = groups
        self.padding_mode = padding_mode
        self.weight = weight
        self.bias = bias
        self._reversed_padding_repeated_twice = _reversed_padding_repeated_twice

        self.forward_hook = None

    @staticmethod
    def from_convNd(module: _ConvNd):
        # "stride",
        # "padding",
        # "dilation",
        # "groups",
        # "padding_mode",
        # "output_padding",
        # "in_channels",
        # "out_channels",
        # "kernel_size",
        #
        return HookedConvND(
            weight=module.weight,
            bias=module.bias,
            in_channels=module.in_channels,
            out_channels=module.out_channels,
            kernel_size=module.kernel_size,
            stride=module.stride,
            padding=module.padding,
            dilation=module.dilation,
            transposed=module.transposed,
            output_padding=module.output_padding,
            groups=module.groups,
            padding_mode=module.padding_mode,
            _reversed_padding_repeated_twice=module._reversed_padding_repeated_twice,
        )

    def forward(self, input: torch.Tensor) -> torch.Tensor:
        output = super().forward(input)
        if self.forward_hook:
            self.forward_hook(self, (input,), output)
        return output

# Models using conv1d: gpt2
class HookedConv1D(transformers.Conv1D):
    def __init__(self, nf: int, nx: int) -> None:
        torch.nn.Module.__init__(self)
        self.nf = nf
        self.nx = nx
        self.forward_hook = None

    @staticmethod
    def from_conv1d(conv1d: transformers.Conv1D):
        custom = HookedConv1D(conv1d.nf, conv1d.nx)
        custom.weight = conv1d.weight
        custom.bias = conv1d.bias
        return custom

    def forward(self, input: torch.Tensor) -> torch.Tensor:
        output = super().forward(input)
        if self.forward_hook:
            self.forward_hook(self, (input,), output)
        return output

# Models using conv2d: ovis
# class HookedConv2d(torch.nn.Conv2d):
#     def __init__(self, in_channels: int, out_channels: int, kernel_size: int, stride: int, padding: int) -> None:
#         # TODO: call super().__init__() is too slow, need to find a better way
#         super().__init__(in_channels, out_channels, kernel_size, stride, padding)
#         self.forward_hook = None
#
#     @staticmethod
#     def from_conv2d(conv2d: torch.nn.Conv2d):
#         custom_conv2d = HookedConv2d(conv2d.in_channels, conv2d.out_channels, conv2d.kernel_size, conv2d.stride, conv2d.padding)
#         custom_conv2d.weight = conv2d.weight
#         custom_conv2d.bias = conv2d.bias
#         return custom_conv2d
#
#     def forward(self, input: torch.Tensor) -> torch.Tensor:
#         output = super().forward(input)
#         if self.forward_hook:
#             self.forward_hook(self, (input,), output)
#         return output


class HookedLinear(torch.nn.Linear):
    def __init__(self, in_features: int, out_features: int) -> None:
        # avoid calling super().__init__() as it would allocate memory baased on in/out features
        torch.nn.Module.__init__(self)
        self.in_features = in_features
        self.out_features = out_features

        self.forward_hook = None

    @staticmethod
    def from_linear(linear: torch.nn.Linear):
        custom_linear = HookedLinear(linear.in_features, linear.out_features)
        custom_linear.weight = linear.weight
        custom_linear.bias = linear.bias
        return custom_linear

    def forward(self, input: torch.Tensor) -> torch.Tensor:
        output = super().forward(input)
        if self.forward_hook:
            self.forward_hook(self, (input,), output)
        return output


def replace_linear_with_hooked_linear(module):
    for name, child in module.named_children():
        if isinstance(child, torch.nn.Linear):
            setattr(module, name, HookedLinear.from_linear(child))
        elif isinstance(child, _ConvNd):
            setattr(module, name, HookedConvND.from_convNd(child))
        elif isinstance(child, transformers.Conv1D):
            setattr(module, name, HookedConv1D.from_conv1d(child))
        # elif isinstance(child, torch.nn.Conv2d):
        #     setattr(module, name, HookedConv2d.from_conv2d(child))
        else:
            replace_linear_with_hooked_linear(child)
