"""Telemetry module contains functions specific to internal Pico
readings such as vsys and internal temperature on ADC 3.

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
    read_internal_temperature: Read internal RP2040 temperature.
    read_vsys: Measure vsys voltage.
"""

from machine import ADC, Pin


def read_internal_temperature() -> float:
    """Read the internal RP2040 temperature sensor 
    ADC value and convert to degrees Celsius.
    
    Returns (float):
        Temperature in degrees Celsius
    """

    analog_sensor = ADC(Pin(4, Pin.IN))
    sleep_ms(250)
    reading = analog_sensor.read_u16()
    voltage = (3.3 / 65535) * reading
    temperature = 27 - (voltage - 0.706) / 0.001721
    return temperature


def read_vsys() -> float:
    """Measure vsys by setting GP29 to Pin.IN and using it to read ADC3

    Info: https://www.coderdojotc.org/micropython/advanced-labs/15-measuring-vsys/

    Returns:
        float: _description_
    """
    vsys = ADC(Pin(29, Pin.IN))
    conversion_factor = (3.3 / (65535)) * 3
    reading = vsys.read_u16() * conversion_factor

    return reading