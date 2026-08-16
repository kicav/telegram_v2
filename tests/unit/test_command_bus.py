from tms.runtime.command_bus import CommandBus


def test_payload_can_contain_business_field_named_name():
    bus = CommandBus()
    received = {}

    def handler(name: str, value: int):
        received.update(name=name, value=value)
        return "ok"

    bus.register("dataset.combine", handler)
    result = bus.dispatch("dataset.combine", name="data1", value=7)
    assert result == "ok"
    assert received == {"name": "data1", "value": 7}
