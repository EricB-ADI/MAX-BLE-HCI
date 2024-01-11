#! /usr/bin/env python3
###############################################################################
#
#
# Copyright (C) 2023 Maxim Integrated Products, Inc., All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL MAXIM INTEGRATED BE LIABLE FOR ANY CLAIM, DAMAGES
# OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# Except as contained in this notice, the name of Maxim Integrated
# Products, Inc. shall not be used except as stated in the Maxim Integrated
# Products, Inc. Branding Policy.
#
# The mere transfer of this software does not imply any licenses
# of trade secrets, proprietary technology, copyrights, patents,
# trademarks, maskwork rights, or any other form of intellectual
# property whatsoever. Maxim Integrated Products, Inc. retains all
# ownership rights.
#
##############################################################################
#
# Copyright 2023 Analog Devices, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
##############################################################################
"""
Contains utilities functions/classes for the HCI implementation.
"""
#pylint: disable=too-many-instance-attributes, too-many-arguments
from typing import Optional, List, Callable, Any
from enum import Enum
from multiprocessing import Process
from threading import Event, Lock, Thread
import sys
import datetime
import time
import weakref

import serial

from ._hci_logger import get_formatted_logger
from .packet_defs import ADI_PORT_BAUD_RATE, PacketType
from .hci_packets import (
    AsyncPacket,
    CommandPacket,
    EventPacket
)
from .packet_codes import EventCode

def to_le_nbyte_list(value: int, n_bytes: int) -> List[int]:
    """Create a list of little-endian bytes.

    Converts a multi-byte number into a list of single-byte
    values. The list is little endian.

    Parameters
    ----------
    value : int
        The multi-byte value that should be converted.
    n_bytes : int
        The expected byte length of the given value

    Returns
    -------
    List[int]
        The given value represented as a little endian
        list of single-byte values. The length is
        equivalent to the `n_bytes` parameter.

    """
    little_endian = []
    for i in range(n_bytes):
        num_masked = (value & (0xFF << 8 * i)) >> (8 * i)
        little_endian.append(num_masked)
    return little_endian


def le_list_to_int(nums: List[int]) -> int:
    """Create an integer from a little-endian list.

    Converts a little-endian list of single byte values
    to a single multi-byte integer.

    Parameters
    ----------
    nums : List[int]
        List containing single-byte values in little endian
        byte order.

    Returns
    -------
    int
        The multi-byte value created from the given list.

    """
    full_num = 0
    for i, num in enumerate(nums):
        full_num |= num << 8 * i
    return full_num

_MAX_U16 = 2**16 - 1
"""Maximum value for a 16-bit unsigned integer."""
_MAX_U32 = 2**32 - 1
"""Maximum value for a 32-bit unsigned integer."""
_MAX_U64 = 2**64 - 1
"""Maximum value for a 64-bit unsigned integer."""

class PhyOption(Enum):
    """BLE-defined PHY options."""

    PHY_1M = 0x1
    """1M PHY option."""

    PHY_2M = 0x2
    """2M PHY option."""

    PHY_CODED = 0x3
    """Generic coded PHY option."""

    PHY_CODED_S8 = 0x3
    """Coded S8 PHY option."""

    PHY_CODED_S2 = 0x4
    """Coded S2 PHY option."""

class PayloadOption(Enum):
    """BLE-definded payload options."""

    PLD_PRBS9 = 0
    """PRBS9 payload option."""

    PLD_11110000 = 1
    """11110000 payload option."""

    PLD_10101010 = 2
    """10101010 payload option."""

    PLD_PRBS15 = 3
    """PRBS15 payload option."""

    PLD_11111111 = 4
    """11111111 payload option."""

    PLD_00000000 = 5
    """00000000 payload option."""

    PLD_00001111 = 6
    """00001111 payload option."""

    PLD_01010101 = 7
    """01010101 payload option."""


class SerialUartTransport:
    """HCI UART serial port transportation object.

    Class defines the implementation of a thread-based UART
    serial port transportation object. The object is used 
    by the HCI to retrieve and sort both event packet and
    asynchronous packets received from the DUT.

    Parameters
    ----------
    port_id : str
        ID string for the port on which a connection should be
        established.
    baud : int
        Port baud rate.
    id_tag : str
        Connection ID string to use when logging.
    logger_name : str
        Name used to reference the HCI logger.
    retries : int
        Number of times a port read should be retried before
        an error is thrown.
    timeout : float
        Port timeout.
    async_callback : Callable[[AsyncPacket], Any], optional
        Function pointer defining the process that should be taken
        when an async packet is received. If not defined, the async
        packet will be thrown out.
    evt_callback : Callable[[EventPacket], Any], optional
        Function pointer defining the process that should be taken
        when an unexpected event packet is received. If not defined,
        the event packet will be thrown out.

    Attributes
    ----------
    port_id : str
        ID string for the port on which a connection has been
        established.
    port : serial.Serial
        Port baud rate.
    id_tag : str
        Connection ID string used by the logger.
    logger : logging.Logger
        HCI logging object referenced by the `logger_name` argument.
    retries : int
        Number of times a port read should be retried before an error
        is thrown.
    timeout : float
        Port timeout.
    async_callback : Callable[[AsyncPacket], Any], optional
        Function pointer defining the process that should be taken
        when an async packet is received.
    evt_callback : Callable[[AsyncPacket], Any], optional
        Function pointer defining the process that should be taken
        when an unexpected event packet is received.
    
    """
    def __new__(cls, *args, **kwargs):
        if "instances" not in cls.__dict__:
            cls.instances = weakref.WeakValueDictionary()

        serial_port = kwargs.get("port_id", args[0])
        if serial_port in cls.instances:
            cls.instances[serial_port].stop()
            cls.instances[serial_port].port.flush()

        cls.instance = super(SerialUartTransport, cls).__new__(cls)
        cls.instances[serial_port] = cls.instance

        return cls.instance

    def __init__(
        self,
        port_id: str,
        baud: int = ADI_PORT_BAUD_RATE,
        id_tag: str = "DUT",
        logger_name: str = "BLE-HCI",
        retries: int = 0,
        timeout: float = 1.0,
        async_callback: Optional[Callable[[AsyncPacket], Any]] = None,
        evt_callback: Optional[Callable[[EventPacket], Any]] = None,
    ):
        self.port_id = port_id
        self.port = None
        self.id_tag = id_tag
        self.logger = get_formatted_logger(name=logger_name)
        self.retries = retries
        self.timeout = timeout
        self.async_callback = async_callback
        self.evt_callback = evt_callback

        self._event_packets = []
        self._read_thread = None
        self._kill_evt = None
        self._data_lock = None
        self._port_lock = None

        self._init_port(port_id, baud)
        self._init_read_thread()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        with self._port_lock:
            self.stop()
            self.port.close()

    def __del__(self):
        if self._read_thread.is_alive():
            self.stop()

    def start(self):
        """Start the port read thread.

        Starts the thread that is used to read from the serial
        port and store the received events.
        
        """
        self._read_thread.start()

    def stop(self):
        """Stop the port read thread.

        Safely stops the execution of the thread used to
        read from the serial port.

        """
        self._kill_evt.set()
        self._read_thread.join()

    def close(self):
        """Close the serial connection.

        Safely stops the execution of any active threads and
        closes the serial connection.

        """
        if self._read_thread.is_alive():
            self.stop()

        if self.port.is_open:
            self.port.flush()
            self.port.close()

    def send_command(
        self, pkt: CommandPacket, timeout: Optional[float] = None
    ) -> EventPacket:
        """Send a command over the serial connection.

        Sends the given command to the DUT over the serial
        connection and retrieves the response.

        Parameters
        ----------
        pkt : CommandPacket
            Command that should be transported.
        timeout : Optional[float], optional
            Timeout for response retrieval. Can be used
            to temporarily override this object's `timeout`
            attribute.

        Returns
        -------
        EventPacket
            The retrieved packet.

        """
        return self._write(pkt.to_bytes(), timeout)

    def retrieve_packet(self, timeout: Optional[float] = None) -> EventPacket:
        """Retrieve a packet from the serial line.

        Retrieves a single packet from the front of the
        serial port queue.

        Parameters
        ----------
        timeout : Optional[float], optional
            Timeout for read operation. Can be used to
            temporarily override this object's `timeout`
            attribute.

        Returns
        -------
        EventPacket
            The retrieved packet.

        """
        return self._retrieve(timeout)

    def _init_read_thread(self) -> None:
        """Initializes the port read thread and data locks.
        
        PRIVATE
        
        """
        self._kill_evt = Event()
        self._read_thread = Thread(
            target=self._read,
            args=(self._kill_evt,),
            daemon=True,
            name=f"Thread-{self.id_tag}",
        )
        self._data_lock = Lock()
        self._port_lock = Lock()
        self.start()

    def _init_port(self, port_id: str, baud: int) -> None:
        """Initializes serial port.

        PRIVATE

        """
        try:
            self.port = serial.Serial(
                port=port_id,
                baudrate=baud,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                rtscts=False,
                dsrdtr=False,
                timeout=2.0,
            )
        except serial.SerialException as err:
            self.logger.error("%s: %s", type(err).__name__, err)
            sys.exit(1)
        except OverflowError as err:
            self.logger.error("Baud rate exception, %i is too large", baud)
            self.logger.error("%s: %s", type(err).__name__, err)
            sys.exit(1)

    def _read(self, kill_evt: Event) -> None:
        """Process executed by the port read thread.
        
        PRIVATE
        
        """
        while not kill_evt.is_set():
            # pylint: disable=consider-using-with
            if self.port.in_waiting and self._port_lock.acquire(blocking=False):
                pkt_type = self.port.read(1)
                if pkt_type[0] == PacketType.ASYNC.value:
                    read_data = self.port.read(4)
                    data_len = read_data[2] | (read_data[3] << 8)
                else:
                    read_data = self.port.read(2)
                    data_len = read_data[1]

                read_data += self.port.read(data_len)
                self._port_lock.release()
                self.logger.info(
                    "%s  %s<%02X%s",
                    datetime.datetime.now(),
                    self.id_tag,
                    pkt_type[0],
                    read_data.hex(),
                )

                with self._data_lock:
                    if pkt_type[0] == PacketType.ASYNC.value and self.async_callback:
                        self.async_callback(AsyncPacket.from_bytes(read_data))
                    else:
                        pkt = EventPacket.from_bytes(read_data)
                        if pkt.evt_code == EventCode.COMMAND_COMPLETE:
                            self._event_packets.append(pkt)
                        elif self.evt_callback:
                            self.evt_callback(pkt)

    def _retrieve(
        self,
        timeout: Optional[float],
    ) -> EventPacket:
        """Reads an event from serial port.

        PRIVATE

        """
        if timeout is None:
            timeout = self.timeout

        def _wait_timeout():
            time.sleep(timeout)
            return 0

        timeout_process = Process(target=_wait_timeout)
        timeout_process.start()

        while self._read_thread.is_alive():
            if self._event_packets:
                timeout_process.terminate()
                timeout_process.join()
                timeout_process.close()
                break
            if timeout_process.exitcode is None:
                continue
            raise TimeoutError(
                "Timeout occured before DUT could respond. Check connection and retry."
            )

        with self._data_lock:
            evt = self._event_packets.pop(0)

        return evt

    def _write(self, pkt: bytearray, timeout: Optional[float]) -> EventPacket:
        """Sends a command to the test board and retrieves the response.

        PRIVATE

        """
        tries = self.retries
        self.logger.info("%s  %s>%s", datetime.datetime.now(), self.id_tag, pkt.hex())
        timeout_err = None

        self.port.flush()
        self.port.write(pkt)
        while tries >= 0 and self._read_thread.is_alive():
            try:
                return self._retrieve(timeout)
            except TimeoutError as err:
                tries -= 1
                timeout_err = err
                self.logger.warning(
                    "Timeout occured. Retrying. %d retries remaining.", tries + 1
                )

        raise TimeoutError("Timeout occured. No retries remaining.") from timeout_err
