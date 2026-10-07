import unittest


class TestEpochMillisOverflow(unittest.TestCase):
    """Review C2: OverflowError must be caught, not crash the adapter."""

    def test_large_value_returns_none(self):
        from ai_adapter.runtime.normalizer import epoch_millis_to_datetime

        self.assertIsNone(epoch_millis_to_datetime(1e30))

    def test_infinity_returns_none(self):
        from ai_adapter.runtime.normalizer import epoch_millis_to_datetime

        self.assertIsNone(epoch_millis_to_datetime(float("inf")))

    def test_negative_returns_none_or_valid(self):
        from ai_adapter.runtime.normalizer import epoch_millis_to_datetime

        # Negative epoch is valid in Python; must not raise.
        result = epoch_millis_to_datetime(-1e12)
        self.assertTrue(result is None or hasattr(result, "isoformat"))
