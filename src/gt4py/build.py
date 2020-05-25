"""
Build process management tools.

Data structures to pass information along and facilitate the entire build process.
Allows fine grained control of build stages.
"""
import abc
import copy
import typing
import logging
from collections import ChainMap

import gt4py


LOGGER = logging.Logger("GT4Py build logger")
LOGGER.setLevel("INFO")


class BuildContext:
    """
    Primary datastructure for the build process.

    Keeps references to the chosen frontend and backend, contains user chosen options
    as well as default choices and information about current and previous build stages.

    An augmented copy is passed from build stage to stage.
    """

    MODULE_LOGGER = LOGGER

    def __init__(self, definition, **kwargs):
        """BuildContext can be constructed from a function definition."""
        self._data = {k: v for k, v in kwargs.items() if v is not None}
        self._data["definition"] = definition
        self._set_no_replace("module", getattr(definition, "__module__", ""))
        self._set_no_replace("name", definition.__name__)
        self._set_no_replace("externals", {})
        self._set_no_replace("qualified_name", f"{self._data['module']}.{self._data['name']}")
        self._set_no_replace("build_info", {})
        self._set_no_replace(
            "options",
            gt4py.definitions.BuildOptions(
                name=self._data["name"],
                module=self._data["module"],
                build_info=self._data["build_info"],
            ),
        )

    def _set_no_replace(self, key, value):
        if not key in self._data:
            self._data[key] = value

    def get(self, key, default=None):
        return self._data.get(key, default)

    def pop(self, key, default=None):
        return self._data.pop(key, default)

    def __getitem__(self, key: str):
        return self._data[key]

    def __setitem__(self, key: str, value: typing.Any):
        self._data[key] = value

    def update(self, data: typing.Mapping):
        self._data.update(data)

    def frontend(self, frontend_name: str):
        self._data["frontend"] = gt4py.frontend.from_name(frontend_name)

    def backend(self, backend_name: str):
        self._data["backend"] = gt4py.backend.from_name(backend_name)


class BuildStage(abc.ABC):
    """Manage transition to the next build stage, adding information to the context."""

    def __init__(self, ctx):
        self.ctx = ctx

    @abc.abstractmethod
    def _make(self):
        pass

    def make(self):
        self._make()
        return self

    @abc.abstractmethod
    def next_stage(self):
        pass

    def make_next(self):
        if self.is_final():
            return None
        return self.next_stage()(self.ctx).make()

    def is_final(self):
        return False


class BeginStage(BuildStage):
    """This stage is at the beginning of every build process."""

    def _make(self):
        LOGGER.warning("Begin stage created.")
        pass

    def next_stage(self):
        return IRStage


class IRStage(BuildStage):
    """
    Internal Representation stage.

    Make context requirements
    -------------------------

    * `frontend`
    * `backend`
    * `options`

    Make context modifications
    --------------------------

    * `options_id` is generated using the `backend` from `options`
    * `id` is set to the stencil ID generated by the `frontend`
    * `ir` is set to the IR generated by `frontend`
    """

    def _make(self):
        frontend = self.ctx["frontend"]
        backend = self.ctx["backend"]
        self.ctx["options_id"] = backend.get_options_id(self.ctx["options"])
        self.ctx["id"] = frontend.get_stencil_id(
            qualified_name=self.ctx["qualified_name"],
            definition=self.ctx["definition"],
            externals=self.ctx["externals"],
            options_id=self.ctx["options_id"],
        )
        self.ctx["ir"] = frontend.generate(
            definition=self.ctx["definition"],
            externals=self.ctx["externals"],
            options=self.ctx["options"],
        )

    def next_stage(self):
        return IIRStage


class IIRStage(BuildStage):
    """
    Internal Implementation Representation stage.

    Make context requirements
    -------------------------

    * `ir`
    * `backend`
    * `options`

    Make context modifications
    --------------------------

    * `iir` is generated through gt4py.analysis.transform
    """

    def _make(self):
        backend = self.ctx["backend"]
        backend._check_options(self.ctx["options"])
        self.ctx["iir"] = gt4py.analysis.transform(
            definition_ir=self.ctx["ir"], options=self.ctx["options"]
        )

    def next_stage(self):
        return SourceStage


class SourceStage(BuildStage):
    """
    Implementation language source for the chosen backend.

    Make context requirements
    -------------------------

    * `iir`
    * `backend`
    * `options`
    * `bindings` if backend supports bindings and they should be generated

    Make context modifications
    --------------------------

    * `src` is generated via the backend and should be a mapping of filenames to source strings
    """

    def _make(self):
        backend = self.ctx["backend"]
        if not backend.BINDINGS_LANGUAGES:
            self._make_py_module()
        else:
            self._make_lang_src()

    def _make_lang_src(self):
        backend = self.ctx["backend"]
        generator = backend.PYEXT_GENERATOR_CLASS(
            backend.get_pyext_class_name(self.ctx["id"]),
            backend.get_pyext_module_name(self.ctx["id"]),
            backend._CPU_ARCHITECTURE,
            self.ctx["options"],
        )
        self.ctx["src"] = generator(self.ctx["iir"])
        if "computation.src" in self.ctx["src"]:
            self.ctx["src"][f"computation.{backend.SRC_EXTENSION}"] = self.ctx["src"].pop(
                "computation.src"
            )
        if "bindings.cpp" in self.ctx["src"]:
            self.ctx["bindings_src"] = self.ctx.get("bindings_src", {})
            self.ctx["bindings_src"]["bindings.cpp"] = self.ctx["src"].pop("bindings.cpp")

    def _make_py_module(self):
        backend = self.ctx["backend"]
        generator_options = self.ctx["options"].as_dict()
        generator = backend.GENERATOR_CLASS(backend, options=generator_options)
        self.ctx["generator_options"] = generator_options
        self.ctx["src"] = {f"{self.ctx['name']}.py": generator(self.ctx["id"], self.ctx["iir"])}

    def is_final(self):
        if self.ctx["backend"].BINDINGS_LANGUAGES and self.ctx.get("bindings", None):
            return False
        return True

    def next_stage(self):
        return BindingsStage


class BindingsStage(BuildStage):
    """
    Language bindings stage.

    Make context requirements
    -------------------------

    * `backend` must support language bindings
    * `bindings` must be a non-empty list of languages supported by `backend`
    * `options`
    * `pyext_module_name`, defaults to `_<name>`
    * `pyext_module_path`
    * `bindings_src`, optional, may contain a key `bindings.cpp`.

    Make context modifications
    --------------------------

    * `bindings_src` is generated via the backend and should be a mapping of filenames to source strings
    """

    def is_final(self):
        return True

    def _make(self):
        if "python" in self.ctx["bindings"]:
            backend = self.ctx["backend"]
            generator_options = self.ctx["options"].as_dict()
            generator_options["pyext_module_name"] = self.ctx.get(
                "pyext_module_name", f"_{self.ctx['name']}"
            )
            generator_options["pyext_file_path"] = self.ctx["pyext_file_path"]
            self.ctx["generator_options"] = generator_options
            generator = backend.GENERATOR_CLASS(backend, options=generator_options)
            bindings_src = {}
            print(bindings_src)
            bindings_src["python"] = {
                "bindings.cpp": self.ctx.get("bindings_src", {}).get("bindings.cpp", ""),
                f"{self.ctx['name']}.py": generator(self.ctx["id"], self.ctx["iir"]),
            }
            print(bindings_src)
            self.ctx["bindings_src"] = bindings_src

    def next_stage(self):
        return None
