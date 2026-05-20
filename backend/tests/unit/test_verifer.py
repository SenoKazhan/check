"""
Модульные тесты для DimensionVerifier.
"""
import pytest

from app.services.verifier import DimensionVerifier, VerifyResult


class TestDimensionVerifier:
    """Тесты верификатора габаритов."""

    def setup_method(self):
        """Инициализация перед каждым тестом."""
        self.verifier = DimensionVerifier(threshold_pct=10.0)

    def test_verify_with_perfect_match(self):
        """Измерения точно совпадают с эталоном."""
        measured = {
            "length_mm": 200.0,
            "width_mm": 150.0,
            "height_mm": 100.0
        }
        reference = {
            "ref_length_mm": 200.0,
            "ref_width_mm": 150.0,
            "ref_height_mm": 100.0
        }
        
        result = self.verifier.verify(measured, reference, confidence=0.95)
        
        assert result.ok is True
        assert result.delta_pct == 0.0
        assert result.details == {
            "length_mm": 0.0,
            "width_mm": 0.0,
            "height_mm": 0.0
        }

    def test_verify_within_threshold(self):
        """Отклонение в пределах порога (10%)."""
        measured = {
            "length_mm": 210.0,  # +5%
            "width_mm": 140.0,   # -6.7%
            "height_mm": 105.0   # +5%
        }
        reference = {
            "ref_length_mm": 200.0,
            "ref_width_mm": 150.0,
            "ref_height_mm": 100.0
        }
        
        result = self.verifier.verify(measured, reference, confidence=0.85)
        
        assert result.ok is True
        assert result.delta_pct <= 10.0

    def test_verify_exceeds_threshold(self):
        """Отклонение превышает порог."""
        measured = {
            "length_mm": 250.0,  # +25%
            "width_mm": 150.0,
            "height_mm": 100.0
        }
        reference = {
            "ref_length_mm": 200.0,
            "ref_width_mm": 150.0,
            "ref_height_mm": 100.0
        }
        
        result = self.verifier.verify(measured, reference, confidence=0.90)
        
        assert result.ok is False
        assert result.delta_pct == 25.0
        assert result.details["length_mm"] == 25.0

    def test_verify_no_reference(self):
        """Верификация при отсутствии эталона."""
        measured = {"length_mm": 200.0, "width_mm": 150.0, "height_mm": 100.0}
        reference = None
        
        result = self.verifier.verify(measured, reference)
        
        assert result.ok is None
        assert result.delta_pct is None
        assert result.details is None

    def test_verify_low_confidence(self):
        """Низкая уверенность модели не влияет на ok, но логируется."""
        measured = {"length_mm": 200.0, "width_mm": 150.0, "height_mm": 100.0}
        reference = {"ref_length_mm": 200.0, "ref_width_mm": 150.0, "ref_height_mm": 100.0}
        
        result = self.verifier.verify(measured, reference, confidence=0.25)
        
        # Верификация проходит (совпадение идеальное), но confidence низкий
        assert result.ok is True
        # В логах должно быть предупреждение (проверяется интеграционным тестом)

        # tests/unit/test_verifer.py
    @pytest.mark.parametrize("threshold,measured,expected_ok", [
        # 205 vs 200 = 2.5% отклонение, порог 5.0% -> должно быть OK (True)
        (5.0, {"length_mm": 205.0, "width_mm": 150.0, "height_mm": 100.0}, True),
        (10.0, {"length_mm": 205.0, "width_mm": 150.0, "height_mm": 100.0}, True),
        (15.0, {"length_mm": 205.0, "width_mm": 150.0, "height_mm": 100.0}, True),
    ])
    def test_verify_parametrized_threshold(self, threshold, measured, expected_ok):
        verifier = DimensionVerifier(threshold_pct=threshold)
        reference = {"ref_length_mm": 200.0, "ref_width_mm": 150.0, "ref_height_mm": 100.0}
        
        result = verifier.verify(measured, reference)
        assert result.ok is expected_ok