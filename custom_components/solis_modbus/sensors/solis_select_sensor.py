from homeassistant.components.select import SelectEntity

from custom_components.solis_modbus.sensors.solis_base_sensor import SolisBaseSensor

class SolisSelectEntity(SelectEntity):
    def __init__(self, hass, sensor: SolisBaseSensor):
        self._attr_options = sensor.options
        self.base_sensor = sensor
        self.hass = hass