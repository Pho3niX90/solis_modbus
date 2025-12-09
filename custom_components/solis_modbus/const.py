DOMAIN = "solis_modbus"
CONTROLLER = "modbus_controller"
SLAVE = "modbus_controller_slave"
MANUFACTURER = "Solis"

VALUES = 'values'
VALUE = 'value'
REGISTER = 'register'
SENSOR_ENTITIES = 'sensor_entities'
TIME_ENTITIES = 'time_entities'
SWITCH_ENTITIES = 'switch_entities'
NUMBER_ENTITIES = 'number_entities'
SENSOR_DERIVED_ENTITIES = 'sensor_derived_entities'
DRIFT_COUNTER = 'drift_counter'
ENTITIES = 'entities'

# Connection types
CONN_TYPE_TCP = "tcp"
CONN_TYPE_SERIAL = "serial"

# Serial connection parameters
CONF_SERIAL_PORT = "serial_port"
CONF_BAUDRATE = "baudrate"
CONF_BYTESIZE = "bytesize"
CONF_PARITY = "parity"
CONF_STOPBITS = "stopbits"
CONF_CONNECTION_TYPE = "connection_type"
CONF_INVERTER_SERIAL = "inverter_serial"
CONF_SLAVE = "slave"

# Default serial values (standard for Solis inverters)
DEFAULT_BAUDRATE = 9600
DEFAULT_BYTESIZE = 8
DEFAULT_PARITY = "N"
DEFAULT_STOPBITS = 1
