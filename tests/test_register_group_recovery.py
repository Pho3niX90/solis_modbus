"""Tests for Modbus register block recovery, clustering, and group splitting."""

import unittest
from functools import partial
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.solis_modbus.const import DOMAIN, NUMBER_ENTITIES, SENSOR_ENTITIES, VALUES
from custom_components.solis_modbus.data.enums import PollSpeed
from custom_components.solis_modbus.data_retrieval import DataRetrieval
from custom_components.solis_modbus.modbus_controller import RECOVERABLE_REGISTER_READ_EXCEPTIONS, ModbusController
from custom_components.solis_modbus.sensors.solis_base_sensor import (
    SolisSensorGroup,
    cluster_sensors_by_contiguous_registers,
)


def _mock_sensor(registrars: list[int], name: str = "s", enabled: bool = True):
    m = MagicMock()
    m.registrars = registrars
    m.name = name
    m.enabled = enabled
    return m


class TestClusterSensors(unittest.TestCase):
    def test_cluster_splits_on_gap(self):
        a = _mock_sensor([100, 101])
        b = _mock_sensor([103])
        clusters = cluster_sensors_by_contiguous_registers([b, a])
        self.assertEqual(2, len(clusters))
        self.assertEqual(1, len(clusters[0]))
        self.assertEqual([100, 101], clusters[0][0].registrars)
        self.assertEqual(1, len(clusters[1]))
        self.assertEqual([103], clusters[1][0].registrars)

    def test_cluster_single_block(self):
        a = _mock_sensor([10])
        b = _mock_sensor([11])
        c = _mock_sensor([12])
        clusters = cluster_sensors_by_contiguous_registers([c, a, b])
        self.assertEqual(1, len(clusters))
        self.assertEqual(3, len(clusters[0]))

    def test_cluster_skips_disabled(self):
        a = _mock_sensor([1], enabled=False)
        b = _mock_sensor([2])
        clusters = cluster_sensors_by_contiguous_registers([a, b])
        self.assertEqual(1, len(clusters))
        self.assertEqual(1, len(clusters[0]))
        self.assertIs(b, clusters[0][0])


class TestIsolateBadRegister(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.hass = MagicMock()
        self.hass.is_running = False
        self.hass.data = {DOMAIN: {VALUES: {}, SENSOR_ENTITIES: [], NUMBER_ENTITIES: []}}
        self.controller = MagicMock()
        self.controller.host = "192.168.1.1"
        self.controller.slave = 1
        self.controller.device_id = 1
        self.controller.enabled = True
        self.controller.connected = MagicMock(return_value=True)
        self.dr = DataRetrieval(self.hass, self.controller)

    async def test_isolate_finds_middle_register(self):
        bad = 104

        async def detailed(start, count, quiet=False):
            regs = range(start, start + count)
            if bad in regs:
                if count == 1 and start == bad:
                    return None, 2
                return None, 2
            return [0] * count, None

        self.controller._async_read_input_register_raw_detailed = AsyncMock(side_effect=detailed)
        found = await self.dr._async_isolate_one_bad_register(100, 10, is_holding=False)
        self.assertEqual(bad, found)


class TestSolisSensorGroupFromSensors(unittest.TestCase):
    def test_from_sensors_builds_group(self):
        s1 = _mock_sensor([200])
        s2 = _mock_sensor([201])
        g = SolisSensorGroup.from_sensors([s1, s2], PollSpeed.NORMAL, identification="id1")
        self.assertEqual(PollSpeed.NORMAL, g.poll_speed)
        self.assertEqual("id1", g.identification)
        self.assertEqual(200, g.start_register)
        self.assertEqual(2, g.registrar_count)


class TestRecoverMultiRegisterDisable(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.hass = MagicMock()
        self.hass.is_running = False
        self.hass.data = {DOMAIN: {VALUES: {}, SENSOR_ENTITIES: [], NUMBER_ENTITIES: []}}
        self.controller = MagicMock()
        self.controller.host = "192.168.1.1"
        self.controller.slave = 1
        self.controller.device_id = 1
        self.controller.enabled = True
        self.controller.connected = MagicMock(return_value=True)
        self.controller._sensor_groups = []
        self.controller.replace_sensor_group = partial(ModbusController.replace_sensor_group, self.controller)
        self.dr = DataRetrieval(self.hass, self.controller)

    async def test_disables_sensor_spanning_bad_word(self):
        bad = 302
        s_wide = _mock_sensor([301, 302], name="wide")
        s_ok = _mock_sensor([303], name="ok")
        group = MagicMock(spec=SolisSensorGroup)
        group.sensors = [s_wide, s_ok]
        group.poll_speed = PollSpeed.FAST
        group.identification = "test"
        group.start_register = 301
        group.registrar_count = 3
        self.controller._sensor_groups = [group]

        async def detailed(start, count, quiet=False):
            regs = range(start, start + count)
            if bad in regs:
                if count == 1 and start == bad:
                    return None, 2
                return None, 2
            return [7] * count, None

        self.controller._async_read_input_register_raw_detailed = AsyncMock(side_effect=detailed)

        async def read_blk(start, count, is_holding):
            if start == 303 and count == 1:
                return ([42], None)
            return (None, 2)

        with patch.object(self.dr, "_read_register_block_with_exception", new=AsyncMock(side_effect=read_blk)):
            with patch("custom_components.solis_modbus.data_retrieval.mark_platform_entities_unavailable_for_base_sensors"):
                out = await self.dr._recover_sensor_group_after_modbus_failure(group, 301, 3, False, [])

        self.assertFalse(s_wide.enabled)
        self.assertTrue(s_ok.enabled)
        self.assertIsNotNone(out)
        self.assertEqual(1, len(out))
        new_g, values = out[0]
        self.assertEqual([303], new_g.sensors[0].registrars)
        self.assertEqual(1, len(values))


class TestModbusControllerReplaceGroup(unittest.TestCase):
    def test_replace_sensor_group_preserves_order(self):
        from custom_components.solis_modbus.modbus_controller import ModbusController

        g0 = MagicMock()
        g1 = MagicMock()
        g2 = MagicMock()
        n1 = MagicMock()
        n2 = MagicMock()
        controller = object.__new__(ModbusController)
        controller._sensor_groups = [g0, g1, g2]
        controller.host = "h"
        controller.device_id = 1
        ModbusController.replace_sensor_group(controller, g1, [n1, n2])
        self.assertEqual([g0, n1, n2, g2], controller._sensor_groups)


class TestRecoverableCodes(unittest.TestCase):
    def test_codes_include_address_and_value(self):
        self.assertIn(2, RECOVERABLE_REGISTER_READ_EXCEPTIONS)
        self.assertIn(3, RECOVERABLE_REGISTER_READ_EXCEPTIONS)
