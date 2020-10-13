from typing import Iterator, Tuple

import pytest

from gt4py.backend.gtc_backend.common import DataType, LevelMarker, LoopOrder
from gt4py.backend.gtc_backend.fields_metadata_pass import FieldsMetadataPass
from gt4py.backend.gtc_backend.gtir import (
    AssignStmt,
    AxisBound,
    CartesianOffset,
    Computation,
    FieldAccess,
    FieldBoundary,
    FieldDecl,
    HorizontalLoop,
    Stencil,
    VerticalInterval,
    VerticalLoop,
)


@pytest.fixture(
    params=[
        (CartesianOffset(i=-1, j=2, k=0), FieldBoundary(i=(1, 0), j=(0, 2), k=(0, 0))),
        (CartesianOffset(i=1, j=2, k=-3), FieldBoundary(i=(0, 1), j=(0, 2), k=(3, 0))),
        (CartesianOffset(i=0, j=0, k=0), FieldBoundary(i=(0, 0), j=(0, 0), k=(0, 0))),
    ]
)
def shift_offset(request) -> Iterator[Tuple[CartesianOffset, FieldBoundary]]:
    yield request.param


def test_copy_shift(shift_offset: Tuple[CartesianOffset, FieldBoundary]) -> None:
    offset, boundary = shift_offset
    copy_shift = Computation(
        name="copy_shift",
        params=[
            FieldDecl(name="a", dtype=DataType.FLOAT64),
            FieldDecl(name="b", dtype=DataType.FLOAT64),
        ],
        stencils=[
            Stencil(
                vertical_loops=[
                    VerticalLoop(
                        loop_order=LoopOrder.FORWARD,
                        vertical_intervals=[
                            VerticalInterval(
                                start=AxisBound(level=LevelMarker.START, offset=0),
                                end=AxisBound(level=LevelMarker.END, offset=0),
                                horizontal_loops=[
                                    HorizontalLoop(
                                        stmt=AssignStmt(
                                            left=FieldAccess.centered(name="a"),
                                            right=FieldAccess(name="b", offset=offset),
                                        )
                                    )
                                ],
                            )
                        ],
                    )
                ]
            )
        ],
    )
    new_copy_shift = FieldsMetadataPass().visit(copy_shift)
    assert new_copy_shift is not copy_shift
    a_meta = new_copy_shift.fields_metadata.metas["a"]
    b_meta = new_copy_shift.fields_metadata.metas["b"]
    assert a_meta.boundary.to_tuple() == FieldBoundary(i=(0, 0), j=(0, 0), k=(0, 0)).to_tuple()
    assert b_meta.boundary.to_tuple() == boundary.to_tuple()
