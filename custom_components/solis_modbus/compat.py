"""Compatibility shims for older Home Assistant versions."""

try:
    # Home Assistant 2025.8+: the options flow reloads the entry itself. The
    # integration must then not register an update listener: HA raises if an
    # OptionsFlowWithReload finishes while one exists, and logs a deprecation
    # when reconfigure (async_update_reload_and_abort) meets one (#565).
    from homeassistant.config_entries import OptionsFlowWithReload as OptionsFlowBase

    OPTIONS_FLOW_RELOADS = True
except ImportError:  # Home Assistant < 2025.8: __init__ keeps an update listener instead
    from homeassistant.config_entries import OptionsFlow as OptionsFlowBase

    OPTIONS_FLOW_RELOADS = False

__all__ = ["OPTIONS_FLOW_RELOADS", "OptionsFlowBase"]
