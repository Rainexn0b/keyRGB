from __future__ import annotations

import logging


_CONFIG_RELOAD_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_CONFIG_FLAG_READ_EXCEPTIONS = (OSError, RuntimeError, TypeError, ValueError)


def reload_power_management_config(config: object, *, context: str, logger: logging.Logger) -> bool:
    try:
        config.reload()  # type: ignore[attr-defined]
        return True
    except _CONFIG_RELOAD_EXCEPTIONS:
        logger.exception("Failed to reload power management config during %s", context)
        return False


def read_power_management_config_bool(config: object, *names: str, default: bool, logger: logging.Logger) -> bool:
    config_dict = getattr(config, "__dict__", None)
    if isinstance(config_dict, dict):
        for name in names:
            if name in config_dict:
                return bool(config_dict[name])

    for name in names:
        try:
            return bool(getattr(config, name))
        except AttributeError:
            continue
        except _CONFIG_FLAG_READ_EXCEPTIONS:
            logger.exception("Failed to read power management config flag '%s'", name)

    return default
