"""Issue #475: 33289 == 0xAA55 marks V2 time-of-use firmware."""

from unittest.mock import MagicMock, patch

import pytest

from custom_components.solis_modbus.helpers import tou_v2_active
from custom_components.solis_modbus.sensor_data.hybrid_sensors import hybrid_sensors


@pytest.mark.parametrize("value,expected", [(0xAA55, True), (0, False), (None, False)])
def test_tou_v2_active(value, expected):
    with patch("custom_components.solis_modbus.helpers.cache_get", return_value=value) as cache_get:
        assert tou_v2_active(MagicMock(), MagicMock()) is expected
    assert cache_get.call_args.args[2] == 33289


def test_tou_version_register_polled_in_own_group():
    group = next(g for g in hybrid_sensors if g["register_start"] == 33289)
    assert [e["register"] for e in group["entities"]] == [["33289"]]
    assert "feature_requirement" not in group
