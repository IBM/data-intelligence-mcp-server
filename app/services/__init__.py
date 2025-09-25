from importlib import import_module
from pathlib import Path


def auto_register_services(mcp, caps, security, base_pkg="app.services"):
    base = Path(__file__).parent
    for p in base.iterdir():
        if p.is_dir() and (p / "__init__.py").exists():
            pkg = f"{base_pkg}.{p.name}"
            mod = import_module(pkg)
            if hasattr(mod, "register"):
                mod.register(mcp, caps, security)
