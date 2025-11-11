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