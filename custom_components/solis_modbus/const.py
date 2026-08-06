DOMAIN = "solis_modbus"
CONTROLLER = "modbus_controller"
SLAVE = "modbus_controller_slave"
MANUFACTURER = "Solis"

VALUES = "values"
VALUE = "value"
REGISTER = "register"
SENSOR_ENTITIES = "sensor_entities"
TIME_ENTITIES = "time_entities"
SWITCH_ENTITIES = "switch_entities"
NUMBER_ENTITIES = "number_entities"
SENSOR_DERIVED_ENTITIES = "sensor_derived_entities"
DRIFT_COUNTER = "drift_counter"
ENTITIES = "entities"

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

# Modbus exception code 2: the slave has no register at the requested address.
# Distinguishes "you asked for the wrong thing" from "the read failed".
MODBUS_ILLEGAL_DATA_ADDRESS = 2

# Poll profiles (issue #457): how much of the register map gets polled.
#
# FULL      — every group the inverter's features allow.
# ESSENTIAL — the core power-flow groups only (issue #412), no 43xxx settings
#             groups, so writable entities are not created.
# EXTREME   — live meter/CT + PV only, for tight control loops (issue #451).
#             Small enough that a 2s fast interval is realistic: each group is
#             one Modbus frame and the Solis spec requires >300ms between frames,
#             so a full ~11-group pass can never be that fast.
POLL_PROFILE_FULL = "full"
POLL_PROFILE_ESSENTIAL = "essential"
POLL_PROFILE_EXTREME = "extreme"

CONF_POLL_PROFILE = "poll_profile"
CONF_EXTREME_INCLUDE_BATTERY = "extreme_include_battery"

POLL_PROFILES = {
    POLL_PROFILE_FULL: "Full (all sensors)",
    POLL_PROFILE_ESSENTIAL: "Essential only (reduce datalogger load)",
    POLL_PROFILE_EXTREME: "Extreme (meter/CT + PV live only, for control loops)",
}

# Minimum fast-poll interval. The default floor protects the bus for everyone;
# extreme mode polls few enough frames that a tighter loop is safe.
POLL_INTERVAL_FAST_MIN = 10
POLL_INTERVAL_FAST_MIN_EXTREME = 2
