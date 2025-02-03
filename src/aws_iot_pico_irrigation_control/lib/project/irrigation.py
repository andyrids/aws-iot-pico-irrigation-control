"""Irrigation module contains functions to facilitate communication
with sensors & components attached to the BC Robotics Pico Irrigation
board.

Author: Andrew Ridyard.

License: GNU General Public License v3 or later.

Functions:
    activate_solenoid
    min_max_scale_reading
    read_moisture_sensor
"""

import array
import asyncio
import time
from machine import ADC, Pin, RTC
from micropython import const
from .utility import debug_message


async def activate_solenoid(solenoid_num: int, time_s: int) -> None:
    """Activate solenoid Pin for a duration given in seconds.

    BC Robotics Pico Irrigation board solenoid controller pins 
    are; GPIO2, GPIO3, GPIO4, GPIO5 & GPIO6.

    https://bc-robotics.com/datasheets/raspberry-pi-pico-irrigation-board-schematic.pdf

    Args:
        solenoid_num (int): Solenoid number 1 - 5
        time_s (int): Duration in seconds

    Returns:
        None
    """
    # solenoid controllers are; GPIO2, GPIO3, GPIO4, GPIO5, GPIO6
    solenoid_gp = Pin(solenoid_num + 1, Pin.OUT)
    solenoid_gp.on()
    await asyncio.sleep(time_s)
    solenoid_gp.on()


async def read_moisture_sensor(sensor_num: int, thing_id: str) -> dict:
    """Power an Analog sensor and take a reading.

    BC Robotics Pico Irrigation board Analog sensors are powered 
    using; GP20, GP21 & GP22, which correspond to ADC0 (GP26), 
    ADC1 (GP27) & ADC2 (GP28) respectively.

    https://bc-robotics.com/datasheets/raspberry-pi-pico-irrigation-board-schematic.pdf

    Args:
        sensor_num (int): Analog sensor 0 - 2.

    Returns:
        A dict containing sensor data: 
        
        {
            "thing-id": thing_id,
            "sensor-id": sensor_num,
            "timestamp": timestamp,
            "reading-u16": Average of 8 u16 readings,
            "reading-vdc": Average of 8 u16 readings in volts,
        }
    """

    analog_gp = Pin(sensor_num + 20, Pin.OUT)
    analog_sensor = ADC(Pin(sensor_num + 26, Pin.IN))

    # power on sensor
    analog_gp.on()

    N_READINGS = const(2)

    debug_message("TAKING MOISTURE READINGS", True)

    # create array ready for N_READINGS
    readings = array.array('L', (0 for _ in range(N_READINGS)))
    for i in range(len(readings)):
        await asyncio.sleep_ms(250)
        readings[i] = analog_sensor.read_u16()

    # power off sensor
    analog_gp.off()
    conversion_factor = (3.3 / (65535)) * 3
    reading_avg = round(sum(readings) / N_READINGS)
   
    debug_message("RETURNING MOISTURE READINGS", True)

    return {
        "thing-id": thing_id,
        "sensor-id": sensor_num,
        "timestamp": time.mktime(time.gmtime()),
        "reading-u16": reading_avg,
        "reading-vcc": reading_avg * conversion_factor
    }


def min_max_scale_reading(value: float, min: int, max: int) -> float:
    """Scale a reading to lie between a given minimum and maximum value.
    If a moisture sensor reading, along with its calibration min and max 
    values are passed, the value will be scaled between 0 & 1.

    NOTE: The scaled value * 100 would give the percentage.

    Args:
        value (float): Reading value.
        min (int): Minimum reading value.
        max (int): Maximum reading value.

    Returns:
        float: Value scaled between 0 & 1
    """
    # value will now lie between min & max - i.e. 0 - 1
    value_scaled = (value - min) / (max - min) 
    return value_scaled
