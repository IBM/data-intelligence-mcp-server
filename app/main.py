#!/usr/bin/env python3

# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""WXDI MCP Server"""

import argparse
import importlib
import pkgutil
import sys
from pathlib import Path

from fastmcp import FastMCP
from pydantic import BaseModel

import app.services
from app.core.prompts_provider import get_prompts_provider
from app.core.registry import service_registry
from app.core.settings import settings

# Ensure the project root is in the Python path for module resolution
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def discover_and_import_services(package):
    """Dynamically imports all tool modules to trigger registration decorators."""
    for _, service_name, _ in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
        service_module = importlib.import_module(service_name)
        tools_path = Path(service_module.__file__).parent / "tools"
        if tools_path.is_dir():
            # First, import the tools package itself to trigger the __init__.py
            importlib.import_module(f"{service_name}.tools")
            # Then, iterate over any other tool modules that might not be in __init__.py
            for _, tool_name, _ in pkgutil.iter_modules([str(tools_path)], f"{service_name}.tools."):
                try:
                    importlib.import_module(tool_name)
                except ImportError as e:
                    print(f"Warning: Could not import tool module '{tool_name}': {e}")


def create_server() -> FastMCP:
    """Creates and configures the MCP server."""
    print("Discovering services...")
    discover_and_import_services(app.services)

    mcp = FastMCP("WXDI MCP Server", version="1.0.0")

    print(f"Registering {len(service_registry._tools)} discovered tools...")
    service_registry.register_all(mcp)
    print("✓ Tool registration complete.")

    prompts_provider = get_prompts_provider()

    class SystemPromptsResponse(BaseModel):
        system_prompt: str
        instructions: str
        services: list[str]

    @mcp.tool(name="system:get_prompts")
    async def get_system_prompts() -> SystemPromptsResponse:
        """Gets system prompts for all available tools."""
        return SystemPromptsResponse(
            system_prompt=prompts_provider.get_system_prompt(),
            instructions="Use these prompts to understand how to interact with each service's tools.",
            services=list(prompts_provider.service_instructions.keys())
        )

    return mcp


def main():
    """Main server entry point."""
    parser = argparse.ArgumentParser(description="IKC MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default=settings.server_transport, help="Transport protocol")
    parser.add_argument("--host", default=settings.server_host, help="Server host address")
    parser.add_argument("--port", type=int, default=settings.server_port, help="Server port number")
    parser.add_argument("--ssl-cert", help="Path to SSL certificate file")
    parser.add_argument("--ssl-key", help="Path to SSL private key file")
    parser.add_argument("--di-url", default=settings.di_service_url, help="Data Intelligence service URL")
    args = parser.parse_args()

    if args.transport != settings.server_transport:
        settings.server_transport = args.transport
        print(f"ℹ Transport overridden via CLI: {args.transport}")

    if args.di_url != settings.di_service_url:
        settings.di_service_url = args.di_url
        print(f"Data Intelligence service URL overridden via CLI: {args.di_url}")

    print(" Starting IKC MCP Server...")
    print(f"   Transport: {args.transport}")

    if args.transport == "http":
        protocol = "https" if args.ssl_cert and args.ssl_key else "http"
        print(f"   Address: {protocol}://{args.host}:{args.port}")

    try:
        mcp = create_server()
        # Note: The final tool count will be the number of discovered tools plus built-ins.
        print(f"✓ Server initialized with {len(service_registry._tools)} discovered tools.")

        if args.transport == "http":
            kwargs = {
                "transport": "streamable-http",
                "host": args.host,
                "port": args.port,
                "stateless_http": True
            }

            # Add SSL configuration if certificate and key are provided
            ssl_cert = args.ssl_cert or settings.ssl_cert_path
            ssl_key = args.ssl_key or settings.ssl_key_path

            if ssl_cert and ssl_key:
                ciphers = [
                    "ECDHE-ECDSA-AES256-GCM-SHA384",
                    "ECDHE-RSA-AES256-GCM-SHA384",
                    "ECDHE-ECDSA-AES128-GCM-SHA256",
                    "ECDHE-RSA-AES128-GCM-SHA256",
                    "DHE-RSA-AES128-GCM-SHA256",
                    "DHE-RSA-AES256-GCM-SHA384",
                ]
                kwargs["port"]=443
                kwargs["uvicorn_config"]= {"ssl_keyfile":ssl_key,"ssl_certfile":ssl_cert,"ssl_ciphers":":".join(ciphers),}

            mcp.run(**kwargs)
        else:
            mcp.run()  # Default stdio transport

    except Exception as e:
        print(f"✗ Failed to start server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
