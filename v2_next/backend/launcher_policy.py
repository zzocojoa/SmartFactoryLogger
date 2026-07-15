import os
from collections.abc import Mapping


EMBEDDED_ELECTRON_ENV = "SFL_EMBEDDED_ELECTRON"


def is_embedded_electron(environ: Mapping[str, str] | None = None) -> bool:
    """Return whether the backend is hosted by the packaged Electron app."""
    runtime_environ = os.environ if environ is None else environ
    return runtime_environ.get(EMBEDDED_ELECTRON_ENV) == "1"


def should_show_backend_splash(environ: Mapping[str, str] | None = None) -> bool:
    """Keep the legacy Tk splash only for standalone backend launches."""
    return not is_embedded_electron(environ)
