import argparse
import ast
from pathlib import Path


def to_camel_case(snake_str):
    """Converts a snake_case_string to CamelCase."""
    return "".join(word.capitalize() for word in snake_str.split('_'))

# --- File Content Templates ---
MANIFEST_TEMPLATE = """service:
  name: {service_name}
  description: "A description for the {service_name} service."
system_instructions: |
  High-level rules and instructions for the {service_name} service.
"""
INIT_PY_TEMPLATE = "" # Empty __init__.py is sufficient
TOOL_FILE_TEMPLATE = """from app.core.registry import service_registry
from app.services.{service_name}.models.{tool_name} import {tool_name_camel}Request, {tool_name_camel}Response

@service_registry.tool(
    name="{service_name}:{tool_name}",
    description="A sample tool for {service_name}.",
    tags={{"sample", "{service_name}"}},
    meta={{"version": "1.0", "service": "{service_name}"}}
)
async def {tool_name}(input: {tool_name_camel}Request) -> {tool_name_camel}Response:
    greeting = f"Hello from {tool_name}, {{input.name}}!"
    return {tool_name_camel}Response(message=greeting)
"""
MODEL_FILE_TEMPLATE = """from pydantic import BaseModel, Field

class {tool_name_camel}Request(BaseModel):
    name: str = Field(..., description="An example input parameter for {tool_name}.")

class {tool_name_camel}Response(BaseModel):
    message: str = Field(..., description="An example output message from {tool_name}.")
"""

# --- Command Functions ---
def create_service(args):
    """Scaffolds a new service directory."""
    service_name = args.service_name
    service_path = Path("app/services") / service_name

    if not service_name.islower() or ' ' in service_name:
        print(f"Error: Service name '{service_name}' must be in snake_case (lowercase, no spaces).")
        return

    if service_path.exists():
        print(f"Error: Service '{service_name}' already exists.")
        return

    print(f"Creating new service '{service_name}'...")
    (service_path / "tools").mkdir(parents=True)
    (service_path / "models").mkdir()

    (service_path / "__init__.py").touch()
    (service_path / "tools" / "__init__.py").touch()
    (service_path / "models" / "__init__.py").touch()
    (service_path / "manifest.yaml").write_text(MANIFEST_TEMPLATE.format(service_name=service_name).strip())

    print(f"✓ Service '{service_name}' created successfully at {service_path}")

def add_tool(args):
    """Adds a new tool and its model to a service."""
    service_name, tool_name = args.service_name, args.tool_name
    service_path = Path("app/services") / service_name

    if not service_path.exists():
        print(f"Error: Service '{service_name}' not found.")
        return

    new_tool_file = service_path / "tools" / f"{tool_name}.py"
    if new_tool_file.exists():
        print(f"Error: Tool '{tool_name}' already exists in '{service_name}'.")
        return

    print(f"Adding tool '{tool_name}' to service '{service_name}'...")
    tool_name_camel = to_camel_case(tool_name)

    new_tool_file.write_text(TOOL_FILE_TEMPLATE.format(service_name=service_name, tool_name=tool_name, tool_name_camel=tool_name_camel).strip())
    (service_path / "models" / f"{tool_name}.py").write_text(MODEL_FILE_TEMPLATE.format(tool_name=tool_name, tool_name_camel=tool_name_camel).strip())

    print(f"  ✓ Created tool file: {new_tool_file}")
    print(f"  ✓ Created model file: {service_path / 'models' / f'{tool_name}.py'}")
    print("✓ Tool added successfully.")

def list_services(args):
    """Lists all available services and their tools."""
    print("Available Services and Tools:")
    print("-" * 30)
    for service_dir in sorted(Path("app/services").iterdir()):
        if not (service_dir.is_dir() and (service_dir / "tools").is_dir()):
            continue
        print(f"  ● {service_dir.name}")
        for tool_file in sorted((service_dir / "tools").glob("*.py")):
            if tool_file.name == "__init__.py":
                continue
            try:
                module = ast.parse(tool_file.read_text())
                for node in ast.walk(module):
                    if isinstance(node, ast.Call) and getattr(getattr(node, 'func', None), 'attr', None) == 'tool':
                        for kw in node.keywords:
                            if kw.arg == 'name':
                                print(f"    - {kw.value.value}")
            except Exception as e:
                print(f"    - (Could not parse {tool_file.name}: {e})")
    print("-" * 30)


def generate_tests(args):
    """Generate basic test stub for a specific service and tool."""
    if not args.service or not args.tool:
        print("Error: Both 'service' and 'tool' arguments are required.")
        print("Usage: python3 scripts/manage.py test generate --service <service_name> --tool <tool_name>")
        return

    tests_path = Path("tests/services")
    service_tests_dir = tests_path / args.service

    print(f"Generating test stub for {args.service}:{args.tool}")
    print("-" * 40)

    try:
        # Create service test directory if it doesn't exist
        service_tests_dir.mkdir(parents=True, exist_ok=True)
        (service_tests_dir / "__init__.py").touch(exist_ok=True)

        # Generate basic test stub
        test_content = f'''"""Unit tests for {args.service} {args.tool} tool."""

import pytest
from unittest.mock import patch, AsyncMock

# TODO: Import your tool and models here
# from app.services.{args.service}.tools.{args.tool} import {args.tool}
# from app.services.{args.service}.models.{args.tool} import {to_camel_case(args.tool)}Request, {to_camel_case(args.tool)}Response


class Test{to_camel_case(args.tool)}RequestModel:
    """Test {to_camel_case(args.tool)}Request model validation."""

    def test_valid_request_creation(self):
        """Test creating a valid request."""
        # TODO: Implement test
        pass


class Test{to_camel_case(args.tool)}ResponseModel:
    """Test {to_camel_case(args.tool)}Response model."""

    def test_valid_response_creation(self):
        """Test creating a valid response."""
        # TODO: Implement test
        pass


class Test{to_camel_case(args.tool)}Tool:
    """Test {args.tool} tool function."""

    @pytest.mark.asyncio
    async def test_basic_functionality(self):
        """Test basic tool functionality."""
        # TODO: Implement test
        pass


class TestServiceRegistryIntegration:
    """Test service registry integration."""

    def test_tool_registered(self):
        """Test that the tool is registered."""
        # TODO: Implement test
        pass
'''

        test_file_path = service_tests_dir / f"test_{args.tool}.py"
        test_file_path.write_text(test_content)
        print(f"  ✓ Created: {test_file_path}")
        print("-" * 40)
        print("✓ Test stub generated successfully!")

    except Exception as e:
        print(f"  ✗ Error generating test for {args.service}:{args.tool}: {e}")
        print("-" * 40)
        print("✗ Test generation failed!")


def main():
    parser = argparse.ArgumentParser(description="A CLI tool to manage MCP services.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    service_parser = subparsers.add_parser("service", help="Manage services")
    service_subparsers = service_parser.add_subparsers(dest="service_command", required=True)

    p_create = service_subparsers.add_parser("create", help="Create a new service.")
    p_create.add_argument("service_name", help="Name (snake_case) of the new service.")
    p_create.set_defaults(func=create_service)

    p_add_tool = service_subparsers.add_parser("add-tool", help="Add a new tool to a service.")
    p_add_tool.add_argument("service_name", help="Name of the service to modify.")
    p_add_tool.add_argument("tool_name", help="Name (snake_case) of the new tool.")
    p_add_tool.set_defaults(func=add_tool)

    p_list = service_subparsers.add_parser("list", help="List all services and their tools.")
    p_list.set_defaults(func=list_services)

    # Test generation commands
    test_parser = subparsers.add_parser("test", help="Manage tests")
    test_subparsers = test_parser.add_subparsers(dest="test_command", required=True)

    p_generate_tests = test_subparsers.add_parser("generate", help="Generate basic test stub for a specific tool.")
    p_generate_tests.add_argument("--service", required=True, help="Service name (required).")
    p_generate_tests.add_argument("--tool", required=True, help="Tool name (required).")
    p_generate_tests.set_defaults(func=generate_tests)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
