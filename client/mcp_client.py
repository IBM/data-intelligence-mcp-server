from fastmcp import Client
from fastmcp.client.elicitation import ElicitResult


config = {
    "mcpServers": {
        "wxdi-mcp-server": {
            "url": "http://127.0.0.1:3001/mcp",
            "transport": "http"
        }
    }
}

async def elicitation_handler(message: str, response_type: type, params, context):
    # Present the message to the user and collect input
    print(message)
    name = input("Enter name: ")
    email = input("Enter email: ")

    if name == "" or email == "":
        return ElicitResult(action="decline")

    response_data = response_type(name=name, age=email)

    return response_data


async def call_mcp():
    async with Client(config) as client:
        await client.ping()

        # List available operations
        tools = await client.list_tools()
        print("\n===============================Tools===============================\n")
        print("\n".join([tool.name for tool in tools]))

        # Call advanced server tools with elicitation
        print("\n===============================Advanced Server Tool with elicitation Result===============================\n")
        result = await client.call_tool("dummy:elicitation", {"input": {"name": "test_user"}})
        print(result.content[0].text)


if __name__ == "__main__":
    import asyncio
    asyncio.run(call_mcp())



