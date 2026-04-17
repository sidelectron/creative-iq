from services.ab_testing.designer import required_sample_size


def test_required_sample_size_is_positive() -> None:
    n = required_sample_size(0.02, mde_relative=0.10, alpha=0.05, power=0.80)
    assert n > 0
    assert isinstance(n, int)
