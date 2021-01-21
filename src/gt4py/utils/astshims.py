# -*- coding: utf-8 -*-
import ast
import sys


__all__ = ["Slice", "Const"]


class _Py38SliceShims:
    @staticmethod
    def is_ellipsis(node):
        return hasattr(node, "value") and isinstance(node.value, ast.Ellipsis)

    @staticmethod
    def is_multi_dim(node):
        return (
            hasattr(node, "value")
            and isinstance(node.value, ast.Tuple)
            or isinstance(node, ast.ExtSlice)
        )

    @classmethod
    def get_dims(cls, node):
        if cls.is_multi_dim(node):
            if hasattr(node, "dims"):
                return node.dims
            return node.value.elts
        return None

    @classmethod
    def is_zero_point(cls, node):
        if cls.is_multi_dim(node) and not isinstance(node, ast.ExtSlice):
            return all(_Py38ConstShims.get_value(i) == 0 for i in cls.get_dims(node))
        elif hasattr(node, "value"):
            return _Py38ConstShims.get_value(node.value) == 0
        return False


class _Py39SliceShims:
    @staticmethod
    def subscript_is_ellipsis(node):
        return isinstance(node, ast.Ellipsis)

    @staticmethod
    def is_multi_dim(node):
        return isinstance(node, ast.Tuple)

    @classmethod
    def get_dims(cls, node):
        if cls.is_multi_dim(node):
            return node.elts
        return None

    @classmethod
    def is_zero_point(cls, node):
        if cls.is_multi_dim(node):
            return all(_Py39ConstShims.get_value(i) for i in cls.get_dims(node))
        else:
            return _Py39ConstShims.get_value(node) == 0


class _Py38ConstShims:
    @staticmethod
    def get_value(node):
        if hasattr(node, "n"):
            return node.n
        elif hasattr(node, "s"):
            return node.s
        elif hasattr(node, "value"):
            return node.value
        return None


class _Py39ConstShims:
    @staticmethod
    def get_value(node):
        return node.value


def get_version_shims():
    if sys.version_info.major == 3:
        if sys.version_info.minor < 9:
            return _Py38SliceShims, _Py38ConstShims
        else:
            return _Py39SliceShims, _Py39ConstShims


Slice, Const = get_version_shims()
