#!/usr/bin/env python3

# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

"""WXDI MCP Server"""

import argparse
import importlib
import pkgutil
import sys
import os
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

import app.services
from app.core.registry import prompt_registry, service_registry
from app.core.settings import settings

# Ensure the project root is in the Python path for module resolution
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def _import_modules_from_path(module_path: Path, package_prefix: str, module_type: str):
    """Helper function to import all modules from a given path.
    
    Args:
        module_path: Path to the directory containing modules
        package_prefix: Package prefix for module names (e.g., "app.services.search.tools")
        module_type: Type of module for error messages (e.g., "tool", "prompt")
    """
    if not module_path.is_dir():
        return
    
    # First, import the package itself to trigger the __init__.py
    importlib.import_module(package_prefix)
    
    # Then, iterate over any other modules that might not be in __init__.py
    for _, module_name, _ in pkgutil.iter_modules([str(module_path)], f"{package_prefix}."):
        try:
            importlib.import_module(module_name)
        except ImportError as e:
            print(f"Warning: Could not import {module_type} module '{module_name}': {e}", file=sys.stderr)


def discover_and_import_services(package):
    """Dynamically imports all tool and prompt modules to trigger registration decorators."""
    for _, service_name, _ in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
        service_module = importlib.import_module(service_name)
        service_path = Path(service_module.__file__).parent
        
        # Discover and import tools
        tools_path = service_path / "tools"
        _import_modules_from_path(tools_path, f"{service_name}.tools", "tool")
        
        # Discover and import prompts
        prompts_path = service_path / "prompts"
        _import_modules_from_path(prompts_path, f"{service_name}.prompts", "prompt")


def create_server() -> FastMCP:
    """Creates and configures the MCP server."""
    print("Discovering services...", file=sys.stderr)
    discover_and_import_services(app.services)

    mcp = FastMCP("WXDI MCP Server", version="1.0.0")

    # Register tools first to get the actual count
    service_registry.register_all(mcp)
    actual_registered_count = service_registry.get_registered_count()

    print(f"Registering {actual_registered_count} discovered tools...", file=sys.stderr)
    print("✅ Tool registration complete.", file=sys.stderr)

    # Register prompts
    prompt_registry.register_all(mcp)
    actual_prompt_count = prompt_registry.get_registered_count()
    
    if actual_prompt_count > 0:
        print(f"Registering {actual_prompt_count} discovered prompts...", file=sys.stderr)
        print("✅ Prompt registration complete.", file=sys.stderr)

    return mcp


def apply_cli_settings_overrides(args):
    """Apply command line argument overrides to settings and print notifications.

    Args:
        args: Parsed command line arguments
    """
    if args.transport != settings.server_transport:
        settings.server_transport = args.transport
        print(f"ℹ Transport overridden via CLI: {args.transport}", file=sys.stderr)

    if args.di_url != settings.di_service_url:
        settings.di_service_url = args.di_url
        print(f"Data Intelligence service URL overridden via CLI: {args.di_url}", file=sys.stderr)

    if args.wxo:
        settings.wxo = True
        print("✅ Watsonx orchestrator compatibility mode enabled", file=sys.stderr)
    else:
        settings.wxo = False


def main():
    """Main server entry point."""
    parser = argparse.ArgumentParser(description="IKC MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default=settings.server_transport, help="Transport protocol")
    parser.add_argument("--host", default=settings.server_host, help="Server host address")
    parser.add_argument("--port", type=int, default=settings.server_port, help="Server port number")
    parser.add_argument("--ssl-cert", help="Path to SSL certificate file")
    parser.add_argument("--ssl-key", help="Path to SSL private key file")
    parser.add_argument("--di-url", default=settings.di_service_url, help="Data Intelligence service URL")
    parser.add_argument("--wxo", action="store_true", help="Enable watsonx orchestrator compatibility mode")
    args = parser.parse_args()

    apply_cli_settings_overrides(args)

    print(" Starting IKC MCP Server...", file=sys.stderr)
    print(f"   Transport: {args.transport}", file=sys.stderr)

    try:
        mcp = create_server()
        # Get the actual registered count after registration
        actual_registered_count = service_registry.get_registered_count()
        print(f"✅ Server initialized with {actual_registered_count} registered tools.", file=sys.stderr)

        if args.transport == "http":
            # Initialize protocol and port for display
            protocol = "http"
            port = args.port
            
            kwargs = {
                "transport": "streamable-http",
                "host": args.host,
                "port": args.port,
                "stateless_http": True
            }
            
            # Configure uvicorn for high concurrency handling
            uvicorn_config: dict[str, Any] = {
                "limit_concurrency": settings.server_limit_concurrency,
                "timeout_keep_alive": settings.server_timeout_keep_alive,
                "backlog": settings.server_backlog,
            }
            kwargs["uvicorn_config"] = uvicorn_config
            
            print(
                f"   Server concurrency settings: "
                f"limit_concurrency={settings.server_limit_concurrency}, "
                f"timeout_keep_alive={settings.server_timeout_keep_alive}s, "
                f"backlog={settings.server_backlog}",
                file=sys.stderr
            )

            # Add SSL configuration if certificate and key are provided
            ssl_cert = args.ssl_cert or settings.ssl_cert_path
            ssl_key = args.ssl_key or settings.ssl_key_path

            if not settings.use_https:
                highlight = "\033[1;33m"  # Bold yellow
                reset = "\033[0m"  # Reset formatting
                print(f"⚠️ WARNING: Starting server in HTTP mode because {highlight}SERVER_HTTPS=False{reset}.", file=sys.stderr)
            
            # Check if we should use HTTPS based on settings
            if settings.use_https:
                # If certificates are available, configure HTTPS
                if ssl_cert and ssl_key:
                    ciphers = [
                        "ECDHE-ECDSA-AES256-GCM-SHA384",
                        "ECDHE-RSA-AES256-GCM-SHA384",
                        "ECDHE-ECDSA-AES128-GCM-SHA256",
                        "ECDHE-RSA-AES128-GCM-SHA256",
                        "DHE-RSA-AES128-GCM-SHA256",
                        "DHE-RSA-AES256-GCM-SHA384",
                    ]
                    kwargs["port"] = 443

                    port = 443  # Update port for display
                    protocol = "https"  # Ensure protocol is https

                    # Merge SSL configuration with existing uvicorn_config
                    uvicorn_config["ssl_keyfile"] = ssl_key
                    uvicorn_config["ssl_certfile"] = ssl_cert
                    uvicorn_config["ssl_ciphers"] = ":".join(ciphers)
                    kwargs["uvicorn_config"] = uvicorn_config
                else:
                    # No certificates found, but HTTPS is required
                    error_msg = (
                        "Server cert and key not found. MCP server is by default started in HTTPS mode. "
                        "Either set SSL_CERT_PATH and SSL_KEY_PATH environment variables or provide "
                        "the cert/keys via --ssl-cert and --ssl-key options OR set SERVER_HTTPS=False "
                        "to start the server without HTTPS (i.e., HTTP). For details on cert/key generation for HTTPS, "
                        "pls. refer to https://github.com/IBM/data-intelligence-mcp-server/blob/main/readme_guides/SERVER_HTTPS.md"
                    )
                    print(f"❌ Error: {error_msg}", file=sys.stderr)
                    sys.exit(1)
            
            # Print address with correct protocol and port
            print(f"   Address: {protocol}://{args.host}:{port}", file=sys.stderr)
            
            mcp.run(**kwargs)
        else:
            mcp.run()  # Default stdio transport

    except Exception as e:
        print(f"❌ Failed to start server: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
