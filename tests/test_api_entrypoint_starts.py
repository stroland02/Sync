"""Every global name `main` reaches is resolvable at module scope.

`B166` landed authentication and put its import inside `app_factory` while `main` called the same
two names, so `python -m sync.api` died on `NameError: configured_api_password` the moment anyone
ran it. Every test in `test_api_auth.py` passed throughout, because they build the app through
`create_app` and none executes `main`. Auth was tested and the process that serves it could not
start.

**The first version of this test did not work, and the reason is worth keeping.** It ran
`main()` in a subprocess and asserted `NameError` was absent from stderr. It passed with the import
removed -- because `main` reaches `graph_dsn()` and `require_schema()` first and dies there, never
arriving at the line that would raise. A test that passes for the wrong reason is the exact defect
this file exists to catch, one layer up.

So this reads the bytecode instead of running it. `main.__code__.co_names` holds every global the
function references; a name in that set and absent from the module's namespace is a `NameError`
waiting for the first person to run the entrypoint. That is decidable without a database, a port,
or a subprocess, and it cannot pass for the wrong reason.
"""

from __future__ import annotations

import builtins
import dis

import sync.api.__main__ as entrypoint


def _globals_referenced(func) -> set[str]:
    """Global names a function loads, via `LOAD_GLOBAL` only.

    `co_names` is the wrong set: it also holds every attribute accessed on anything, so `os.environ`
    contributes `environ` and `uvicorn.run` contributes `run`, neither of which the module defines
    nor should. `dis` separates a global load from an attribute load, which is exactly the
    distinction this test turns on.
    """
    names = {i.argval for i in dis.get_instructions(func) if i.opname == "LOAD_GLOBAL"}
    for constant in func.__code__.co_consts:
        if hasattr(constant, "co_names"):
            names |= {
                i.argval
                for i in dis.get_instructions(constant)
                if i.opname == "LOAD_GLOBAL"
            }
    return names


def test_every_global_main_references_exists_in_the_module():
    module_namespace = set(vars(entrypoint)) | set(dir(builtins))

    missing = sorted(
        name
        for name in _globals_referenced(entrypoint.main)
        if name not in module_namespace and not name.startswith("__")
    )

    assert not missing, (
        f"`main` references {missing}, which the module does not define. An import sitting inside "
        "another function satisfies `import sync.api.__main__` and still leaves `main` unable to "
        "see the name, so this fails only when the entrypoint is genuinely broken."
    )
