from __future__ import annotations

import logging
from operator import attrgetter


_CONFIG_RELOAD_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_CONFIG_FLAG_READ_EXCEPTIONS = (OSError, RuntimeError, TypeError, ValueError)


def reload_power_management_config(config: object, *, context: str, logger: logging.Logger) -> bool:
    try:
        config.reload()  # type: ignore[attr-defined]
        return True
    except _CONFIG_RELOAD_EXCEPTIONS:
        logger.exception("Failed to reload power management config during %s", context)
        return False


def _config_dict_or_none(config: object) -> dict[str, object] | None:
    try:
        config_dict = vars(config)
    except TypeError:
        return None
    return config_dict if isinstance(config_dict, dict) else None


def _read_config_attr(config: object, name: str) -> object:
    return attrgetter(name)(config)


def read_power_management_config_bool(config: object, *names: str, default: bool, logger: logging.Logger) -> bool:
    config_dict = _config_dict_or_none(config)
    if isinstance(config_dict, dict):
        for name in names:
            if name in config_dict:
                return bool(config_dict[name])

    for name in names:
        try:
            return bool(_read_config_attr(config, name))
        except AttributeError:
            continue
        except _CONFIG_FLAG_READ_EXCEPTIONS:
            logger.exception("Failed to read power management config flag '%s'", name)

    return default
