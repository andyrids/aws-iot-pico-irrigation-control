"""Main script for MicroPython application.

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
    async_main: Main coroutine for application.
    catch_async_interrupt: Trap async coroutine exceptions.
    event_timer: Get a Timer instance set to a specified interval.
    garbage_collector: Coroutine for periodic garbage collection.
    handle_async_exception: Async exception handler.
    microdot_server: Serve a HTML form through a Microdot server.
    synchronise_time: Coroutine to set Network Time Protocol (NTP).

Types:
    FunctionType: Custom replacement type for typing.Callable.

Constants:
    _VERBOSE (bool): Verbose debug message flag.

Raises:
    KeyboardInterrupt

NOTE: Set _VERBOSE to True for verbose debug messages.
"""

import array
import asyncio
import binascii
import gc
import json
import network
import ntptime
import os
import rp2
import ssl
import sys

from machine import Timer, reset, soft_reset
from micropython import const
from time import localtime

from lib.microdot import Microdot, send_file
from lib.project.connection import (
    MQTTSecretsError,
    access_point_reset,
    connection_issue,
    deactivate_interface,
    get_client_interface,
    get_network_interface,
)
from lib.project.utility import (
    debug_message,
    debug_network_status,
    dynamic_set_secret,
)
from lib.umqtt.robust import MQTTClient

# verbose debug messages flag
_VERBOSE = const(True)


def fn() -> None:
    """FunctionType placeholder"""
    pass


FunctionType = type(fn)


async def synchronise_time(verbose: bool = False) -> bool:
    """Coroutine to set Network Time Protocol (NTP) and synchronize the time
    on successful WLAN connection/re-connection.

    NOTE: NTP must be set correctly to avoid AWS 'Thing' certificate validation
    issues, when using MQTT with SSL context.

    Args:
        verbose (bool, optional): Enable verbose debug messages.

    Returns:
        True if NTP was set successfully else False
    """

    debug_message("ASYNC TASK - SYNCHRONISE NETWORK TIME", verbose)
    try:  # 30 attempts
        attempt = iter(range(30))
        while next(attempt) >= 0:
            try:
                ntptime.settime()
                y, m, d, H, M, S, *_ = localtime()
                debug_message(
                    f"SET NTPTIME SUCCESS - {y}-{m}-{d} {H}:{M}:{S}", verbose
                )
                break
            except OSError as e:
                debug_message(f"NTPTIME EXCEPTION - {e}", verbose)
                debug_message("RETRY SET NTPTIME", verbose)
                continue
        return True
    except StopIteration:
        debug_message("SET NTPTIME FAILED", verbose)
    return False


async def garbage_collector(verbose: bool = False) -> None:
    """Coroutine to carry out garbage collection every 10 seconds.

    Args:
        verbose (bool, optional): Enable verbose debug messages.
    """
    gc.enable()
    while True:
        debug_message("ASYNC TASK - GARBAGE COLLECTION", verbose)
        gc.collect()
        gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
        await asyncio.sleep(10)


async def microdot_server(app: Microdot, verbose: bool = False) -> None:
    """Coroutine to serve a Microdot server, which handles requests from a
    user to update WLAN_SSID & WLAN_PASSWORD env/secrets. Once These secrets
    are updated, the server will shutdown. Static assets are served from
    server/assets.

    NOTE: The index page contains custom JavaScript, which intercepts all
    requests to the Microdot server and handles the server responses. This
    prevents endpoint changes on Form post and facilitates custom logic to
    turn off the server via a follow-up GET request, after a success response
    on new secret submission and change.

    NOTE: We are able to use Bootstrap offline, by utilising gz compression
    and the microdot.send_file function. We should probably be using custom
    CSS or a lightweight framework, but this shows the realms of the possible.

    Args:
        app (Microdot): Microdot app instance.
        verbose (bool, optional): Enable verbose debug messages.
    """

    @app.route("/", methods=["GET"])
    async def index(request):
        """Send index.html to client"""
        return send_file("server/index.html", compressed=False)

    @app.route("/system", methods=["GET"])
    async def system_information(request):
        """Send system information JSON to client."""
        system_details = os.uname()
        return {
            "device-description": system_details.machine,
            "micropython-version": system_details.release,
        }

    @app.route("/assets/<path:path>", methods=["GET"])
    async def fetch_assets(request, path):
        """Send gzip compressed assets to client"""
        return send_file(
            f"server/assets/{path}",
            max_age=86400,
            compressed=True,
            file_extension=".gz",
        )

    @app.route("/connection", methods=["POST"])
    async def set_connection(request):
        """Set secret names & values based on client Form data."""
        WLAN_SSID = request.form.get("input-ssid")
        WLAN_PASSWORD = request.form.get("input-password")

        dynamic_set_secret("WLAN_PASSWORD", WLAN_PASSWORD)
        if not dynamic_set_secret("WLAN_SSID", WLAN_SSID):
            return {"request": True, "valid": False}, 400
        # SSID was valid
        return {"request": True, "valid": True}, 205

    @app.route("/reset", methods=["GET"])
    async def reset(request):
        request.app.shutdown()
        return "SERVER SHUTDOWN"

    debug_message("ASYNC TASK - MICRODOT SERVER STARTUP", verbose)
    await app.start_server(port=80, debug=verbose, ssl=None)
    debug_message("ASYNC TASK - MICRODOT SERVER SHUTDOWN", verbose)


def event_timer(
    event: asyncio.Event, period: int, verbose: bool = False
) -> Timer:
    """Creates a periodic Timer instance, which calls the internal set_event
    function after a duration set by the period parameter. The set_event
    callback will set the internal flag of the event parameter, causing any
    coroutines/tasks waiting on this Event to continue.

    Args:
        event (asyncio.Event): Event to be set by Timer callback.
        period (int): Timer duration in milliseconds.
        verbose (bool, optional): Enable verbose debug messages.

    Returns:
        Timer instance.
    """

    def set_event(t: Timer) -> None:
        """Set Event internal flag on timer end."""
        debug_message(f"EVENT TIMER ({period} ms) - SETTING EVENT", verbose)
        event.set()

    timer = Timer()
    timer.init(period=period, mode=machine.Timer.PERIODIC, callback=set_event)
    return timer


async def catch_async_interrupt(coroutine: FunctionType, **kwargs) -> None:
    """Coroutine to catch an async interrupt.

    Args:
        coroutine (FunctionType): Async function to catch interrupts.
        kwargs (dict): Keyword arguments for coroutine.
    """
    try:
        return await coroutine(**kwargs)
    except asyncio.CancelledError:
        debug_message(f"CATCH ASYNCIO TASK CancelledError", **kwargs)
    except KeyboardInterrupt:
        debug_message(f"CATCH ASYNCIO TASK KeyboardInterrupt", **kwargs)
    except Exception as e:
        debug_message(f"CATCH ASYNCIO TASK Exception", **kwargs)
        sys.print_exception(e)


async def handle_async_exception(
    loop: asyncio.Loop, context: dict, verbose: bool = True
) -> None:
    """Exception handler for coroutines run as a Task via the
    asyncio.create_task method.

    Args:
        loop (asyncio.Loop): Current Event loop.
        context (dict): Exception context details.
        verbose (bool, optional): Enable verbose debug messages.
    """
    debug_message(f"HANDLE ASYNC EXCEPTION", verbose)
    sys.print_exception(context["exception"])
    sys.exit()


async def async_main(verbose: bool = False):
    """Main async application function.

    1. Establish & monitor WLAN connection
        A. Attempt WLAN STA connection using env/secrets
        B. Start Microdot server on WLAN connection fail
        C. Serve HTML form to update WLAN credentials
        D. Update env/secrets if correct
        E. Shutdown server & attempt WLAN connection
        F. Repeat A - E as necessary

    2. Facilitate AWS IoT Core communication over MQTT
        A. Publish telemetry data at set intervals
        B. Carry out tasks in command topic messages
            I. Read data from moisture sensor
            II. Activate solenoid valve

    TODO: Alexa skill creation for MQTT communication with device.

    Args:
        verbose (bool, optional): Enable verbose debug messages.
    """
    # set country
    rp2.country("GB")

    # get initial WLAN instance & attempt connection
    WLAN, WLAN_MODE = get_network_interface(verbose)
    debug_network_status(WLAN, WLAN_MODE, verbose)

    # event loop & exception handler setup
    event_loop = asyncio.get_event_loop()
    event_loop.set_exception_handler(handle_async_exception)

    # asyncio Event instances
    async_events = {}
    async_events["connection_issue"] = asyncio.Event()

    gc.collect()

    # asyncio Task instances
    async_tasks = {}
    async_tasks["garbage_collector"] = asyncio.create_task(
        garbage_collector(verbose)
    )

    await asyncio.sleep(5)

    # check if WLAN connected in STA mode
    if not connection_issue(WLAN, WLAN_MODE, verbose):
        # if 'synchronise_time' coroutine completes successfully...
        if await synchronise_time(verbose):
            # we indicate no connection issues
            async_events["connection_issue"].set()
        else:
            debug_message(f"SYNCHRONISE TIME FAILED", verbose)

    # Microdot HTTP server instance
    app = Microdot()
    try:
        debug_message(f"ENTERING MAIN LOOP", verbose)
        while True:
            # handle connection issues
            if connection_issue(WLAN, WLAN_MODE, verbose):
                # can reconnect if only intermittent connection issue
                await asyncio.sleep(15)
                # if connection issue resolved - continue
                if not connection_issue(WLAN, WLAN_MODE, verbose):
                    debug_message(f"CONNECTION ISSUE RESOLVED", verbose)
                    continue
                debug_message(
                    f"CONNECTION ISSUE - STATUS: {WLAN.status()}", verbose
                )
                async_events["connection_issue"].clear()
                # reset interface to AP if in STA mode
                if WLAN_MODE == network.STA_IF:
                    WLAN, WLAN_MODE = access_point_reset(WLAN, verbose)

                ip, subnet, gateway, dns = WLAN.ifconfig()

                debug_message(f"AFTER MICRODOT SERVER STARTUP:", verbose)
                debug_message(f"1. CONNECT TO PICO W WLAN", verbose)
                debug_message(f"2. NAVIGATE TO http://{gateway}:80", verbose)
                debug_message(f"3. ENTER YOUR WLAN SSID & PASSWORD", verbose)

                # WLAN AP mode & Microdot server hosting while connection issue
                while connection_issue(WLAN, WLAN_MODE, verbose):
                    # await server shutdown on user SSID & password input
                    await microdot_server(app, verbose)
                    debug_message(f"RESETTING WLAN INTERFACE", verbose)
                    # reset the interface and attempt connection
                    WLAN, WLAN_MODE = get_network_interface(verbose)
                    debug_network_status(WLAN, WLAN_MODE, verbose)

                debug_message(f"CONNECTION ISSUE RESOLVED", verbose)
                async_events["connection_issue"].set()
                await asyncio.sleep(1)
                # if NTP never synchronised
                if not (await synchronise_time(verbose)):
                    debug_message(f"SYNCHRONISE TIME FAILED", verbose)
            # hand over to other async tasks
            await asyncio.sleep(0)
    except (OSError, KeyboardInterrupt, MQTTSecretsError) as e:
        debug_message(f"{e}", verbose)
        sys.print_exception(e)
    except Exception as e:
        debug_message(f"Exception {e}", verbose)
        sys.print_exception(e)
    finally:
        debug_message(f"ASYNC_MAIN LOOP CLEANUP", verbose)
        try:
            app.shutdown()
        except AttributeError:
            pass
        debug_message(f"DISCONNECT & DEACTIVATE WLAN INTERFACE", verbose)
        WLAN.disconnect()
        deactivate_interface(WLAN, verbose)
        WLAN.deinit()
        debug_message(f"ASYNC_MAIN LOOP TERMINATE", verbose)


debug_message(f"ASYNCIO.RUN ASYNC_MAIN", _VERBOSE)
try:
    asyncio.run(async_main(_VERBOSE))
except KeyboardInterrupt:
    debug_message(f"ASYNCIO.RUN KeyboardInterrupt", _VERBOSE)
except Exception as e:
    debug_message(f"ASYNCIO.RUN UNHANDLED EXCEPTION: {e}", _VERBOSE)
    sys.print_exception(e)
finally:
    debug_message(f"ASYNCIO.RUN CLEANUP", _VERBOSE)
    asyncio.new_event_loop()
    debug_message(f"ASYNCIO.RUN TERMINATE", _VERBOSE)
