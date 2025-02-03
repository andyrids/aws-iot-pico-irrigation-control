"""Utility module containing helper functions.

Author: Andrew Ridyard.

License: GNU General Public License v3 or later.

Copyright (C): 2024.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

Functions:
    debug_message: Print debug messages if verbose flag is True.
    debug_network_status: Print specific WLAN status debug message.
    dynamic_get_secret: Read secret from /env/secrets.py.
    dynamic_set_secret: Write secret to /env/secrets.py.
"""

import network
import os
import sys


def debug_message(message: str, verbose: bool) -> None:
    """Print verbose debug message if verbose flag is True
    
    Args:
        message (str): Message to print.
        verbose (bool): Message print flag.
    """
    # "{:^30}".format("CENTERED STRING")
    if not verbose:
        return
    print("\n".join([i.strip() for i in message.split("\n")]))


def debug_network_status(
        WLAN: network.WLAN,
        mode: str,
        verbose: bool
    ) -> None:
    """Print verbose WLAN status debug message if verbose flag is True.

    Args:
        WLAN (network.WLAN): WLAN instance.
        mode (str): WLAN instance mode.
        verbose (bool): Message print flag.
    """
    WLAN_MODE_STR = ("STA", "AP")[mode]
    debug_message(
        f"""
        WLAN INFO
        ---------
        MODE: {WLAN_MODE_STR}
        STATUS: {WLAN.status()}
        ACTIVE: {WLAN.active()}
        CONNECTED: {WLAN.isconnected()}
        """,
        verbose
    )


def create_secrets() -> str:
    """Create an env/secrets file if missing.
    
    Returns:
        env/secrets filename.
    """

    SECRETS_PY = "secrets.py"
    SECRETS_MPY = "secrets.mpy"

    env_directory = os.listdir("env")
    if not (SECRETS_PY in env_directory or SECRETS_MPY in env_directory):
        with open(f"env/{SECRETS_PY}", "w") as secrets:
            secret_lines = (
                "AP_SSID = None\n"
                "AP_PASSWORD = None\n"
                "WLAN_SSID = None\n"
                "WLAN_PASSWORD = None\n"
                "MQTT_ENDPOINT = None\n"
                "MQTT_CLIENT_ID = None\n"
            )
            secrets.write("".join(secret_lines))

    return (SECRETS_MPY, SECRETS_PY)[SECRETS_PY in os.listdir("env")]


def dynamic_get_secret(name: str) -> str:
    """Dynamically import 'env.secrets' and 
    return the secret specified by name.

    Dynamic import allows for changes to secrets.py 
    and updated values being returned on subsequent 
    function calls.

    Args:
        name (str): Name of secret enumeration

    Returns:
        str: Specified secret value
    """
    exec("import env.secrets", {})
    # use getattr rather than sys.modules["env.secrets"].AP_PASSWORD etc.
    secret = getattr(sys.modules["env.secrets"], name, None)
    del sys.modules["env.secrets"]

    secret = None if isinstance(secret, str) and secret == "" else secret
    return secret


def dynamic_set_secret(name: str, value: str) -> bool:
    """Dynamically set secret variable value in the secrets file.

    Args:
        name (str): Secret name
        value (str): Secret value

    Returns:
        True if secret value not set to None, else False.
    """
    value = None if isinstance(value, str) and value == "" else value

    secrets_path = f"env/{create_secrets()}"

    name_found = False
    with open(secrets_path, "r") as secrets:
        secret_lines = secrets.readlines()
        for i in range(len(secret_lines)):
            if name not in secret_lines[i]:
                continue
            secret_line = "{} = {}\n" if value is None else "{} = '{}'\n"
            secret_lines[i] = secret_line.format(name, value)
            name_found = True

    if not name_found:
        secret_lines.append("{} = '{}'\n".format(name, value))

    with open(secrets_path, "w") as secrets:
        secrets.write("".join(secret_lines))

    return value is not None
