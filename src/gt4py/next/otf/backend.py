import dataclasses
from typing import Any, Generic

from gt4py._core import definitions as core_defs
from gt4py.next import allocators as next_allocators
from gt4py.next.iterator import ir as itir
from gt4py.next.program_processors import processor_interface as ppi


@dataclasses.dataclass(frozen=True)
class Backend(ppi.ProgramExecutor, Generic[core_defs.DeviceTypeT]):
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

    @property
    def __gt_allocator__(
        self,
    ) -> next_allocators.FieldBufferAllocatorProtocol[core_defs.DeviceTypeT]:
        return self.allocator
