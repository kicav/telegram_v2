from tms.runtime.resource_governor import ResourceGovernor


def test_performance_mode_is_reference_counted():
    governor = ResourceGovernor()
    governor.enable_performance_mode()
    governor.enable_performance_mode()
    assert governor.performance_mode
    governor.disable_performance_mode()
    assert governor.performance_mode
    governor.disable_performance_mode()
    assert not governor.performance_mode
    governor.disable_performance_mode()
    assert not governor.performance_mode
