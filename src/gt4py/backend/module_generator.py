import abc
import numbers
import os
from dataclasses import dataclass, field
from inspect import getdoc
from typing import TYPE_CHECKING, Any, Dict, Optional, Set

import jinja2

from gt4py import ir as gt_ir
from gt4py import utils as gt_utils
from gt4py.definitions import AccessKind, DomainInfo, FieldInfo, ParameterInfo


if TYPE_CHECKING:
    from gt4py.stencil_builder import StencilBuilder


@dataclass
class ModuleData:
    field_info: Dict[str, Optional[FieldInfo]] = field(default_factory=dict)
    parameter_info: Dict[str, Optional[ParameterInfo]] = field(default_factory=dict)
    unreferenced: Set[str] = field(default_factory=set)

    @property
    def field_names(self):
        return self.field_info.keys()

    @property
    def parameter_names(self):
        return self.parameter_info.keys()


def make_args_data_from_iir(implementation_ir: gt_ir.StencilImplementation) -> ModuleData:
    data = ModuleData()

    # Collect access type per field
    out_fields = set()
    for ms in implementation_ir.multi_stages:
        for sg in ms.groups:
            for st in sg.stages:
                for acc in st.accessors:
                    if (
                        isinstance(acc, gt_ir.FieldAccessor)
                        and acc.intent == gt_ir.AccessIntent.READ_WRITE
                    ):
                        out_fields.add(acc.symbol)

    for arg in implementation_ir.api_signature:
        if arg.name in implementation_ir.fields:
            access = AccessKind.READ_WRITE if arg.name in out_fields else AccessKind.READ_ONLY
            if arg.name not in implementation_ir.unreferenced:
                field_decl = implementation_ir.fields[arg.name]
                data.field_info[arg.name] = FieldInfo(
                    access=access,
                    boundary=implementation_ir.fields_extents[arg.name].to_boundary(),
                    axes=field_decl.axes,
                    dtype=field_decl.data_type.dtype,
                )
            else:
                data.field_info[arg.name] = None
        else:
            if arg.name not in implementation_ir.unreferenced:
                data.parameter_info[arg.name] = ParameterInfo(
                    dtype=implementation_ir.parameters[arg.name].data_type.dtype
                )
            else:
                data.parameter_info[arg.name] = None

    data.unreferenced = implementation_ir.unreferenced

    return data


class BaseModuleGenerator(abc.ABC):

    SOURCE_LINE_LENGTH = 120
    TEMPLATE_INDENT_SIZE = 4
    DOMAIN_ARG_NAME = "_domain_"
    ORIGIN_ARG_NAME = "_origin_"
    SPLITTERS_NAME = "_splitters_"

    TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "templates", "stencil_module.py.in")

    _builder: Optional["StencilBuilder"]
    args_data: ModuleData
    template: jinja2.Template

    def __init__(self, builder: Optional["StencilBuilder"] = None):
        self._builder = builder
        self.args_data = ModuleData()
        with open(self.TEMPLATE_PATH, "r") as f:
            self.template = jinja2.Template(f.read())

    def __call__(
        self,
        args_data: ModuleData,
        builder: Optional["StencilBuilder"] = None,
        **kwargs: Any,
    ) -> str:
        """Generate source code for a Python module containing a StencilObject."""
        if builder:
            self._builder = builder
        self.args_data = args_data

        module_source = self.template.render(
            imports=self.generate_imports(),
            module_members=self.generate_module_members(),
            class_name=self.generate_class_name(),
            class_members=self.generate_class_members(),
            docstring=self.generate_docstring(),
            gt_backend=self.generate_backend_name(),
            gt_source=self.generate_sources(),
            gt_domain_info=self.generate_domain_info(),
            gt_field_info=repr(self.args_data.field_info),
            gt_parameter_info=repr(self.args_data.parameter_info),
            gt_constants=self.generate_constants(),
            gt_options=self.generate_options(),
            stencil_signature=self.generate_signature(),
            field_names=self.args_data.field_names,
            param_names=self.args_data.parameter_names,
            pre_run=self.generate_pre_run(),
            post_run=self.generate_post_run(),
            implementation=self.generate_implementation(),
        )
        if self.builder.options.as_dict()["format_source"]:
            module_source = gt_utils.text.format_source(
                module_source, line_length=self.SOURCE_LINE_LENGTH
            )

        return module_source

    @property
    def builder(self) -> "StencilBuilder":
        """
        Expose the builder reference.

        Raises a runtime error if the builder reference is not initialized.
        This is necessary because other parts of the public API depend on it before it is
        guaranteed to be initialized.
        """
        if not self._builder:
            raise RuntimeError("Builder attribute not initialized!")
        return self._builder

    @property
    def backend_name(self) -> str:
        return self.builder.backend.name

    @abc.abstractmethod
    def generate_implementation(self) -> str:
        pass

    def generate_imports(self) -> str:
        source = ""
        return source

    def generate_class_name(self) -> str:
        return self.builder.class_name

    def generate_docstring(self) -> str:
        return getdoc(self.builder.definition) or ""

    def generate_backend_name(self) -> str:
        return self.backend_name

    def generate_sources(self) -> Dict[str, str]:
        if self.builder.definition_ir.sources is not None:
            return {
                key: gt_utils.text.format_source(value, line_length=self.SOURCE_LINE_LENGTH)
                for key, value in self.builder.definition_ir.sources
            }
        return {}

    def generate_constants(self) -> Dict[str, str]:
        if self.builder.definition_ir.externals:
            return {
                name: repr(value)
                for name, value in self.builder.definition_ir.externals.items()
                if isinstance(value, numbers.Number)
            }
        return {}

    def generate_options(self) -> Dict[str, Any]:
        return {
            key: value
            for key, value in self.builder.options.as_dict().items()
            if key not in ["build_info"]
        }

    def generate_domain_info(self) -> str:
        parallel_axes = self.builder.definition_ir.domain.parallel_axes or []
        sequential_axis = self.builder.definition_ir.domain.sequential_axis.name
        domain_info = repr(
            DomainInfo(
                parallel_axes=tuple(ax.name for ax in parallel_axes),
                sequential_axis=sequential_axis,
                ndims=len(parallel_axes) + (1 if sequential_axis else 0),
            )
        )
        return domain_info

    def generate_module_members(self) -> str:
        source = ""
        return source

    def generate_class_members(self) -> str:
        source = ""
        return source

    def generate_signature(self) -> str:
        args = []
        keyword_args = ["*"]
        for arg in self.builder.definition_ir.api_signature:
            if arg.is_keyword:
                if arg.default is not gt_ir.Empty:
                    keyword_args.append(
                        "{name}={default}".format(name=arg.name, default=arg.default)
                    )
                else:
                    keyword_args.append(arg.name)
            else:
                if arg.default is not gt_ir.Empty:
                    args.append("{name}={default}".format(name=arg.name, default=arg.default))
                else:
                    args.append(arg.name)

        if len(keyword_args) > 1:
            args.extend(keyword_args)
        signature = ", ".join(args)

        return signature

    def generate_pre_run(self) -> str:
        source = ""
        return source

    def generate_post_run(self) -> str:
        source = ""
        return source


class PyExtModuleGenerator(BaseModuleGenerator):

    pyext_module_name: str
    pyext_file_path: str

    def __init__(self):
        super().__init__()
        self.pyext_module_name = ""
        self.pyext_file_path = ""

    def __call__(
        self,
        args_data: ModuleData,
        builder: Optional["StencilBuilder"] = None,
        **kwargs: Any,
    ) -> str:
        self.pyext_module_name = kwargs["pyext_module_name"]
        self.pyext_file_path = kwargs["pyext_file_path"]
        return super().__call__(args_data, builder, **kwargs)

    def generate_imports(self) -> str:
        source = """
from gt4py import utils as gt_utils
        """
        if self.builder.implementation_ir.multi_stages:
            source += """
pyext_module = gt_utils.make_module_from_file(
        "{pyext_module_name}", "{pyext_file_path}", public_import=True
    )
        """.format(
                pyext_module_name=self.pyext_module_name, pyext_file_path=self.pyext_file_path
            )
        return source

    def generate_implementation(self) -> str:
        definition_ir = self.builder.definition_ir
        sources = gt_utils.text.TextBlock(indent_size=BaseModuleGenerator.TEMPLATE_INDENT_SIZE)

        args = []
        api_fields = set(field.name for field in definition_ir.api_fields)
        for arg in definition_ir.api_signature:
            if arg.name not in self.args_data.unreferenced:
                args.append(arg.name)
                if arg.name in api_fields:
                    args.append("list(_origin_['{}'])".format(arg.name))

        # only generate implementation if any multi_stages are present. e.g. if no statement in the
        # stencil has any effect on the API fields, this may not be the case since they could be
        # pruned.
        if self.builder.implementation_ir.has_effect:
            source = """
# Load or generate a GTComputation object for the current domain size
pyext_module.run_computation(list(_domain_), {run_args}, exec_info)
""".format(
                run_args=", ".join(args)
            )
            sources.extend(source.splitlines())
        else:
            sources.extend("\n")

        return sources.text


class CUDAPyExtModuleGenerator(PyExtModuleGenerator):
    def generate_implementation(self) -> str:
        source = (
            super().generate_implementation()
            + """
cupy.cuda.Device(0).synchronize()
    """
        )
        return source

    def generate_imports(self) -> str:
        source = (
            """
import cupy
"""
            + super().generate_imports()
        )
        return source