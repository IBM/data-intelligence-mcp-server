# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

def trigger_interrupt_with_ui(*args, **kwargs):
    """
    No ui and interrupts in mcp - this does nothing
    """
    pass

class FakeCallerContext():
    """
    Fake CallerContext for code portabiility
    """

    def get(self):
        return "mcp"

caller_context = FakeCallerContext()