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

from __future__ import annotations

import dataclasses
from typing import Any, Generic, Optional, TypeVar

import gt4py._core.definitions as core_defs
import gt4py.next.allocators as next_allocators
import gt4py.next.iterator.ir as itir
import gt4py.next.program_processors.processor_interface as ppi
from gt4py.next.otf import languages, stages, workflow


SrcL = TypeVar("SrcL", bound=languages.NanobindSrcL)
TgtL = TypeVar("TgtL", bound=languages.LanguageTag)
LS = TypeVar("LS", bound=languages.LanguageSettings)
HashT = TypeVar("HashT")


@dataclasses.dataclass(frozen=True)
class OTFBackend(ppi.ProgramExecutor, Generic[core_defs.DeviceTypeT]):
    allocator: next_allocators.FieldBufferAllocatorProtocol[core_defs.DeviceTypeT]
    otf_workflow: workflow.Workflow[stages.ProgramCall, stages.CompiledProgram]
    name: Optional[str] = None

    def __call__(self, program: itir.FencilDefinition, *args, **kwargs: Any) -> None:
        return self.otf_workflow(stages.ProgramCall(program, args, kwargs))(
            *args, offset_provider=kwargs["offset_provider"]
        )

    @property
    def __name__(self) -> str:
        return self.name or "Anonymous Backend"

    @property
    def __gt_allocator__(
        self,
    ) -> next_allocators.FieldBufferAllocatorProtocol[core_defs.DeviceTypeT]:
        return self.allocator
