# GT4Py - GridTools Framework
#
# Copyright (c) 2014-2023, ETH Zurich
# All rights reserved.
#
# This file is part of the GT4Py project and the GridTools framework.
# GT4Py is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or any later
# version. See the LICENSE.txt file at the top-level directory of this
# distribution for a copy of the license or check <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import dataclasses
from typing import Any, Generic, Protocol, runtime_checkable

from gt4py._core import definitions as core_defs
from gt4py.next import allocators as next_allocators
from gt4py.next.iterator import ir as itir
from gt4py.next.program_processors import processor_interface as ppi


@runtime_checkable
class Backend(ppi.ProgramProcessor, Protocol[core_defs.DeviceTypeT]):
    executor: ppi.ProgramExecutor
    allocator: next_allocators.FieldBufferAllocatorProtocol[core_defs.DeviceTypeT]

    @property
    def __name__(self) -> str: ...

    @property
    def __gt_allocator__(
        self,
    ) -> next_allocators.FieldBufferAllocatorProtocol[core_defs.DeviceTypeT]:
        return self.allocator

    @property
    def kind(self) -> type[ppi.ProgramExecutor]:
        return ppi.ProgramExecutor


@dataclasses.dataclass(frozen=True)
class ExecutorWrapperBackend(Backend, Generic[core_defs.DeviceTypeT]):
    executor: ppi.ProgramExecutor
    allocator: next_allocators.FieldBufferAllocatorProtocol[core_defs.DeviceTypeT]

    def __call__(self, program: itir.FencilDefinition, *args, **kwargs: Any) -> None:
        self.executor(program, *args, **kwargs)

    @property
    def __name__(self) -> str:
        return getattr(self.executor, "__name__", None) or repr(self)

    @property
    def kind(self) -> type[ppi.ProgramExecutor]:
        return self.executor.kind
