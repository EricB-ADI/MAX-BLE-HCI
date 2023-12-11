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
"""Module contains a host-controller interface for ADI BLE-compatible chips.

Module defines a host-controller interface for BLE operation on any Analog
Devices BLE compatible microchip. The HCI class provides basic testing
functionality, and is designed to be used with the `BLE5_ctrl` example
housed in the Analog Devices MSDK.

"""

from .hci_packets import CommandPacket, EventPacket, AsyncPacket, ExtendedPacket
from ._hci_packet_utils import OGF, OCF, PacketTypes, ADI_PORT_BAUD_RATE

import datetime
import sys
import time
import logging
from typing import Dict, List, Optional, Tuple, Union

import serial


class BleHci:
    """Host-controller interface for ADI BLE-compatible microchips.

    The BleHci object defines a host-controller interface for
    BLE operations on any Analog Devices BLE-compatible microchip.
    Controller provides implementations for both connection mode
    and DTM testing. It is designed to be used in conjunction with
    the embedded firmware found in the `BLE5_ctr` example in the
    Analog Devices MSDK.

    Parameters
    ----------
    port_id : str
        Serial port ID string.
    id_tag : str
        String identification for class instance.
    log_level : str
        HCI logging level.

    Attributes
    ----------
        port : serial.Serial
            Test board serial port connection.
        id_tag : str
            Identification for class instance.
        opcodes : Dict[str, int]
            Command name to opcode map.

    """
    def __init__(
        self,
        port_id: str,
        mon_port_id: Optional[str] = None,
        baud = ADI_PORT_BAUD_RATE,
        id_tag: str = 'DUT',
        log_level: Union[str, int] = 'INFO',
        logger_name: str = 'BLE-HCI'
    ) -> None:
        self.port = None
        self.mon_port = None
        self.id_tag = id_tag
        self.logger =  logging.Logger(logger_name)

        self._init_ports(port_id=port_id, mon_port_id=mon_port_id, baud=baud)
        self.set_log_level(log_level)

    def get_log_level(self) -> str:
        level = self.logger.level
        if level == logging.DEBUG:
            return "DEBUG"
        if level == logging.INFO:
            return "INFO"
        if level == logging.WARNING:
            return "WARNING"
        if level == logging.ERROR:
            return "ERROR"
        if level == logging.CRITICAL:
            return "CRITICAL"
        return "NOTSET"

    def set_log_level(self, level: Union[str, int]) -> None:
        """Sets log level.
        
        Provides intermediary control over the logging level
        of the host-controller interface module logger. If
        necessary, desired log level is automatically converted
        from a string to an integer. As such, both strings and
        integers are valid inputs to the `level` parameter.

        Parameters
        ----------
        level : Union[int, str]
            Desired log level.
        
        """
        if isinstance(level, int):
            self.logger.setLevel(level)
            return
        
        ll_str = level.upper()
        if ll_str == "DEBUG":
            self.logger.setLevel(logging.DEBUG)
        elif ll_str == "INFO":
            self.logger.setLevel(logging.INFO)
        elif ll_str == "WARNING":
            self.logger.setLevel(logging.WARNING)
        elif ll_str == "ERROR":
            self.logger.setLevel(logging.ERROR)
        elif ll_str == "CRITICAL":
            self.logger.setLevel(logging.CRITICAL)
        else:
            self.logger.setLevel(logging.NOTSET)
            self.logger.warning(
                f"Invalid log level string: {ll_str}, level set to 'logging.NOTSET'")

    def set_address(self, addr: Union[List[int], bytearray]) -> EventPacket:
        """Sets the BD address.

        Function sets the chip BD address. Address can be given
        as either a bytearray or as a list of integer values.

        Parameters
        ----------
        addr : Union[List[int], bytearray]
            Desired BD address.

        Returns
        -------
        EventPacket
            Object containing board return data.

        """
        if isinstance(addr, list):
            try:
                addr = bytearray(addr)
            except ValueError as err:
                self.logger.error("%s: %s", type(err).__name__, err)
                sys.exit(1)
            except TypeError as err:
                self.logger.error("%s: %s", type(err).__name__, err)
        cmd = CommandPacket(self.ogf.VENDOR_SPEC, self.ocf.VENDOR_SPEC.SET_BD_ADDR, params=addr)
        return self._send_command(cmd.to_bytes())

    def start_advertising(
        self,
        interval: int = 0x60,
        connect: bool = True,
        listen: Union[bool, int] = False
    ) -> EventPacket:
        """Command board to start advertising.

        Sends a command to the board, telling it to start advertising
        with the given interval. Advertising type can be either
        scannable/connectable or non-connectable in accordance with
        the `connect` argument. HCI can be directed to listen for
        events for either a finite number or seconds or indefinitely
        in accordance with the `listen` argument. Indefinite listening
        can only be ended with `CTRL-C`. A test end function must be
        called to end this process on the board.

        Parameters
        ----------
        interval : int
            The advertising interval.
        connect : bool
            Use scannable/connectable advertising type?
        listen : Union[bool, int]
            Listen (indefinitely or finite) for incoming events?

        Returns
        -------
        EventPacket
            Object containing board return data.

        """
        peer_addr = bytearray([0x0, 0x0, 0x0, 0x0, 0x0, 0x0])
        self._setup_event_masks()

        cmd = CommandPacket(self.ogf.LE_CONTROLLER, self.ocf.LE_CONTROLLER.SET_DEF_PHY)

    def _init_ports(
        self,
        port_id: Optional[str] = None,
        mon_port_id: Optional[str] = None,
        baud: int = ADI_PORT_BAUD_RATE
    ) -> None:
        """Initializes serial ports.
        
        PRIVATE
        
        """
        if self.port is not None:
            if self.port.is_open:
                self.port.flush()
                self.port.close()

        if self.mon_port is not None:
            if self.mon_port.is_open and mon_port_id:
                self.mon_port.flush()
                self.mon_port.close()

        try:
            self.port = serial.Serial(
                port=port_id,
                baudrate=baud,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                rtscts=False,
                dsrdtr=False,
                timeout=2.0
            )
            if mon_port_id:
                self.mon_port = serial.Serial(
                    port=mon_port_id,
                    baudrate=baud,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    bytesize=serial.EIGHTBITS,
                    rtscts=False,
                    dsrdtr=False,
                    timeout=2.0
                )
        except serial.SerialException as err:
            self.logger.error("%s: %s", type(err).__name__, err)
            sys.exit(1)
        except OverflowError as err:
            self.logger.error("Baud rate exception, %i is too large", baud)
            self.logger.error("%s: %s", type(err).__name__, err)
            sys.exit(1)

    def _wait_single(self, timeout: float = 6.0) -> Union[EventPacket, AsyncPacket]:
        """Wait for a single event"""
        self.port.timeout = timeout
        evt_type = self.port.read(size=1)

        if len(evt_type) == 0:
            self.port.flush()
            return None

        ##TODO: get full event
        evt = self.port.read()
        self.logger.info("%s  %s<%s", datetime.datetime.now(), self.id_tag, evt.hex())

        if evt_type == PacketTypes.ASYNC:
            return AsyncPacket.from_bytes(evt)
        if evt_type == PacketTypes.EVENT:
            return EventPacket.from_bytes(evt)
        
    def _wait_multiple(self, seconds: int = 2) -> None:
        """Wait for events from the test board for a few seconds.
        
        PRIVATE
        
        """
        start_time = datetime.datetime.now()
        delta = datetime.datetime.now() - start_time

        while True:
            if seconds != 0:
                if delta.seconds > seconds:
                    break
            
            self._wait_single(timeout=0.1)
            delta = datetime.datetime.now() - start_time
            if (delta.seconds > 30) and (delta.seconds % 30 == 0):
                self.logger.info("%s |", datetime.datetime.now())

    def _send_command(
        self,
        pkt: bytearray,
        delay: float = 0x1,
        timeout: int = 6
    ) -> Union[EventPacket, AsyncPacket]:
        """Sends a command to the test board and retrieves the response.
        
        PRIVATE
        
        """
        self.logger.info("%s  %s>%s", datetime.datetime.now(), self.id_tag, pkt.hex())

        self.port.write(pkt)
        time.sleep(delay)

        return self._wait_single(timeout=timeout)


    def write_command(self, command : CommandPacket) -> EventPacket:
        self.port.flush()
        self.port.write(command.to_bytes())
        evt_code = self.port.read(1)
        param_len = self.port.read(1)    
        
        data = [evt_code, param_len]
        

        for i in range(param_len):
            data.append(self.port.read())

        return EventPacket(data)
    def reset(self) ->EventPacket:
        return self._write_command(CommandPacket(ocf=3, ogf=3, params=[0]))
        
        
        