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
from .packet_defs import OGF, OCF, PacketTypes, ADI_PORT_BAUD_RATE

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
    PHY_1M = 0
    PHY_2M = 1
    PHY_S8 = 2
    PHY_S2 = 3

    def __init__(
        self,
        port_id: str,
        mon_port_id: Optional[str] = None,
        baud=ADI_PORT_BAUD_RATE,
        id_tag: str = 'DUT',
        log_level: Union[str, int] = 'INFO',
        logger_name: str = 'BLE-HCI'
    ) -> None:
        self.port = None
        self.mon_port = None
        self.id_tag = id_tag
        self.logger = logging.Logger(logger_name)

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
        cmd = CommandPacket(OGF.VENDOR_SPEC, OCF.VENDOR_SPEC.SET_BD_ADDR, 6, params=addr)
        return self._send_command(cmd)

    def start_advertising(
        self,
        interval: int = 0x60,
        connect: bool = True,
        listen: Union[bool, int] = False
    ) -> EventPacket:
        #TODO: more options?
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
        self.set_event_mask()

        cmd = CommandPacket(OGF.VENDOR_SPEC, OCF.VENDOR_SPEC.RESET_CONN_STATS, 0)
        self._send_command(cmd)

        params = [
            0x0,                            # All PHYs Preference
            0x7,                            # TX PHYs Preference
            0x7                             # RX PHYs Preference
        ]
        cmd = CommandPacket(OGF.LE_CONTROLLER, OCF.LE_CONTROLLER.SET_DEF_PHY, 3, params=params)
        self._send_command(cmd)

        params = [
            interval,                       # Advertising Interval Min.
            interval,                       # Advertising Interval Max.
            0x3,                            # Advertisiing Type
            0x0,                            # Own Address Type
            0x0,                            # Peer Address Type
            0x0, 0x0, 0x0, 0x0, 0x0, 0x0,   # Peer Address
            0x7,                            # Advertising Channel Map
            0x0                             # Advertising Filter Policy
        ]

        if connect:
            params[2] = 0x0                 # If connecting, change Advertising Type

        cmd = CommandPacket(OGF.LE_CONTROLLER, OCF.LE_CONTROLLER.SET_ADV_PARAM, 15, params=params)
        self._send_command()

        cmd = CommandPacket(OGF.LE_CONTROLLER, OCF.LE_CONTROLLER.SET_ADV_ENABLE, 1, params=0x1)
        evt = self._send_command(cmd)

        if not listen:
            return evt
        
        if isinstance(listen, int):
            self._wait(seconds=listen)
            return evt
        
        while True:
            self._wait(seconds=10)
            self.get_connection_stats()

    def start_scan(self, interval: int = 0x100) -> None:
        """Command board to start scanning for connections.

        Sends a command to the board, telling it to start scanning with
        the given interval for potential connections. Function then
        listens for events indefinitely. The listening can only be
        stopped with `CTRL-C`. A test end function must be called to end
        this process on the board.

        Parameters
        ----------
        interval : int
            The scan interval.

        """
        self.set_event_mask()

        params = [
            0x1,                            # LE Scan Type
            interval,                       # LE Scan Interval
            interval,                       # LE Scan Window
            0x0,                            # Own Address Type
            0x0                             # Scanning Filer Policy
        ]
        cmd = CommandPacket(OGF.LE_CONTROLLER, OCF.LE_CONTROLLER.SET_SCAN_PARAM, 2, params=params)
        self._send_command(cmd)

        params = [
            0x1,                            # LE Scan Enable
            0x0                             # Filter Duplicates
        ]
        cmd = CommandPacket(OGF.LE_CONTROLLER, OCF.LE_CONTROLLER.SET_SCAN_ENABLE, 2, params=params)
        self._send_command(cmd)

        while True:
            self._wait()

    def init_connection(
        self,
        addr: Union[List[int], bytearray],
        interval: int = 0x6,
        timeout: int = 0x64,
        listen: Union[bool, int] = False,
    ) -> EventPacket:
        """Command board to initialize a connection.

        Sends a sequence of commands to the board, telling it to
        initialize a connection in accordance with the given address,
        interval, and timeout. The `address` argument must be a
        string representing six bytes of hex values, with each byte
        seperated by a ':'. HCI can be directed to listen for events
        for either a finite number or seconds or indefinitely in
        accordance with the `listen` argument. Indefinite listening
        can only be ended with `CTRL-C`. The `disconnect()` function
        must be called to end the connection if it is successfully made.

        Parameters
        ----------
        addr : str
            BD address to use for connection initialization. String
            containing six bytes of hex data, with each byte separated
            by a ':'.
        interval : int
            Connection interval.
        timeout : int
            Connection initialization timeout.
        listen : Union[bool, int]
            Listen (finite or indefinite) for further events?

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
                sys,exit(1)
        
        self.set_event_mask()

        cmd = CommandPacket(OGF.VENDOR_SPEC, OCF.VENDOR_SPEC.RESET_CONN_STATS, 0x0)
        self._send_command(cmd)

        params = [
            0x0,                            # All PHYs Preference
            0x7,                            # TX PHYs Preference
            0x7                             # RX PHYs Preference
        ]
        cmd = CommandPacket(OGF.LE_CONTROLLER, OCF.LE_CONTROLLER.SET_DEF_PHY, 3, params=params)
        self._send_command(cmd)

        params = [
            0xA000,                         # LE Scan Interval
            0xA000,                         # LE Scan Window
            0x0,                            # Initiator Filter Policy
            0x0,                            # Peer Address Type
            addr,                           # Peer Address
            0x0,                            # Own Address Type
            interval,                       # Connection Interval Min.
            interval,                       # Connection Interval Max.
            0x0000,                         # Max. Latency
            timeout,                        # Supervision Timeout
            0x0F10,                         # Min. CE Length
            0x0F10                          # Max. CE Length
        ]
        cmd = CommandPacket(OGF.LE_CONTROLLER, OGF.LE_CONTROLLER.CREATE_CONN, 25, params=params)
        evt = self._send_command(cmd)

        if not listen:
            return evt
        
        if isinstance(listen, int):
            self._wait(seconds=listen)
            return evt
        
        while True:
            self._wait(seconds=10)
            self.get_connection_stats()

    def set_data_len(self) -> EventPacket:
        """Command board to set data length to the max value.

        Sends a command to the board, telling it to set its internal
        data length parameter to the maximum value.

        Returns
        -------
        Event
            Object containing board return data.

        """
        params = [
            0x0000,                         # Connection Handle
            0xFB00,                         # TX Octets
            0x9042                          # TX Time
        ]
        cmd = CommandPacket(OGF.LE_CONTROLLER, OCF.LE_CONTROLLER.SET_DATA_LEN, 6, params=params)
        evt = self._send_command(cmd)

        return evt

    def send_acl(self, packet_len: int, num_packets: int) -> EventPacket:
        """Command board to send ACL data.

        Sends a command to the board telling it to send ACL data
        in accordance with the provided packet length and number
        of packets. A test end function must be called to end this
        process on the board.

        Parameters
        ----------
        packet_len : int
            Desired packet length.
        num_packets : int
            Desired number of packets to send.

        Returns
        -------
        Event
            Object containing board return data.

        """
        if packet_len > 0xFFFF:
            self.logger.error(f"Invalid packet length {packet_len}. Must be less than 65536.")
            sys.exit(1)

        if num_packets > 0xFF:
            self.logger.error(
                f"Invalid number of packets: {num_packets}. Must be less than 256.")
            sys.exit(1)

        if num_packets == 0:
            cmd = CommandPacket(
                OGF.VENDOR_SPEC, OCF.VENDOR_SPEC.ENA_AUTO_GEN_ACL, 2, params=packet_len)
            evt = self._send_command(cmd)
            return evt

        cmd = CommandPacket(
            OGF.VENDOR_SPEC,
            OCF.VENDOR_SPEC.GENERATE_ACL,
            5, 
            params=[0x0000, packet_len, num_packets]
        )
        evt = self._send_command(cmd)
        return evt

    def sink_acl(self) -> EventPacket:
        """Command board to sink ACL data.

        Sends a command to the board, telling it to sink
        incoming ACL data.

        Returns
        -------
        Event
            Object containing board return data.

        """
        cmd = CommandPacket(OGF.VENDOR_SPEC, OCF.VENDOR_SPEC.ENA_ACL_SINK, 1, params=0x1)
        evt = self._send_command(cmd)
        return evt

    def get_connection_stats(self, retries: int = 5) -> float:
        """Gets and parses connection stats.

        Sends a command to the board, telling it to return
        a connection statistics packet. Function then attempts
        to parse the packet and calculate the current connection
        PER%. Function will attempt this process for the given
        number of retries.

        Parameters
        ----------
        retries : int
            Amount of times to attempt to collect and parse the
            connection statistics.

        Returns
        -------
        float
            The current connection PER as a percentage.

        """
        per = None,
        clear = False
        cmd = CommandPacket(OGF.VENDOR_SPEC, OCF.VENDOR_SPEC.GET_CONN_STATS, 0)

        while per is None and retries > 0:
            evt = self._send_command(cmd)
            if clear:
                self._wait(seconds=1)
            else:
                clear = True

            per = self._parse_conn_stats_evt(evt)
            retries -= 1
        if retries == 0 and per is None:
            self.logger.warning("Failed to get connection stats.")

        return per

    def set_phy(self, phy: int = 1, timeout: int = 3) -> EventPacket:
        """Set the PHY.

        Sends a command to the board, telling it to set the
        PHY to the given selection. PHY must be one of the
        values 1, 2, 3 or 4. Alternatively, PHY selection
        values are declared in `utils/constants.py` as
        ADI_PHY_1M (1), ADI_PHY_2M (2), ADI_PHY_S8 (3), and
        ADI_PHY_S2 (4).

        Parameters
        ----------
        phy_sel : int
            Desired PHY.
        timeout : int
            Process timeout.

        Returns
        -------
        Event
            Object containing board return data.

        """
        params = [
            0x0000,                         # Connection Handle
            0x0,                            # All PHYs Preference
            0x0,                            # TX PHYs Preference
            0x0,                            # RX PHYs Preference
            0x0000                          # PHY Options
        ]
        if phy == self.PHY_2M:
            params[2] = 0x2
            params[3] = 0x2
        elif phy == self.PHY_S8:
            params[2] = 0x4                 
            params[3] = 0x4
            params[4] = 0x0002
        elif phy == self.PHY_S2:
            params[2] = 0x4
            params[3] = 0x4
            params[4] = 0x0001
        elif phy != self.PHY_1M:
            self.logger.warning("Invalid PHY selection = %i, using 1M.", phy)
        
        cmd = CommandPacket(OGF.LE_CONTROLLER, OCF.LE_CONTROLLER.SET_PHY, 7, params=params)
        evt = self._send_command(cmd)

        return evt
    
    def reset(self) -> EventPacket:
        """Reset test board.

        Sends a command to the board, telling it to reset the
        link layer internal control.

        Returns
        -------
        Event
            Object containing board return data.

        """
        cmd = CommandPacket(OGF.CONTROLLER, OCF.CONTROLLER.RESET, 0)
        evt = self._send_command(cmd)

        return evt

    def listen(self, time: int = 0) -> float:
        """Listen for events and monitor connection stats.

        Listens for events and monitors connection stats for
        the specified amount of time. To listen indefinitely,
        set `time` argument to 0. Indefinite listening can only
        be ended with `CTRL-C`.

        Parameters
        ----------
        time : int
            The amount of time to listen/monitor for. Set to `0`
            for indefinitely.

        Returns
        -------
        float
            The current connection PER as a percent.

        """
        per = 100.0
        start_time = datetime.datetime.now()
        while True:
            if time == 0:
                self._wait(10)
            else:
                self._wait(time)

            cmd = CommandPacket(OGF.VENDOR_SPEC, OCF.VENDOR_SPEC.GET_CONN_STATS, 0)
            evt = self._send_command(cmd)

            per = self._parse_conn_stats_evt(evt)
            time_now = datetime.datetime.now()

            if time != 0 and (time_now - start_time).total_seconds() > time:
                return per

    def tx_test(
        self, channel: int = 0, phy: int = 1, payload: int = 0, packet_len: int = 0
    ) -> EventPacket:
        """Command board to being transmitting.

        Sends a command to the board, telling it to begin transmitting
        packets of the given packet length, with the given payload, on
        the given channel, using the given PHY. The payload must be one
        of the values 0, 1, 2, 3, 4, 5, 6, or 7. Alternatively, payload
        selection values are declared in `utils/constants.py` as
        ADI_PAYLOAD_PRBS9 (0), ADI_PAYLOAD_11110000 (1), ADI_PAYLOAD_10101010 (2),
        ADI_PAYLOAD_PRBS15 (3), ADI_PAYLOAD_11111111 (4) ADI_PAYLOAD_00000000 (5),
        ADI_PAYLOAD_00001111 (6) and ADI_PAYLOAD_01010101 (7). The PHY must
        be one of the values 1, 2, 3 or 4. Alternatively, PHY selection
        values are declared in `utils/constants.py` as ADI_PHY_1M (1),
        ADI_PHY_2M (2), ADI_PHY_S8 (3), and ADI_PHY_S2 (4). A test end
        function must be called in order to end this process on the board.

        Parameters
        ----------
        channel : int
            The channel to transmit on.
        phy : int
            The PHY to use.
        payload : int
            The payload type to use.
        packet_len : int
            The TX packet length.

        Returns
        -------
        Event
            Object containing board return data.

        """
        params = [
            channel,
            packet_len,
            payload,
            phy
        ]
        cmd = CommandPacket(
            OGF.LE_CONTROLLER, OCF.LE_CONTROLLER.ENHANCED_TRANSMITTER_TEST, 4, params=params)
        evt = self._send_command(cmd)

        return evt

    def tx_test_vs(
        self,
        channel: int = 0,
        phy: int = 1,
        payload: int = 0,
        packet_len: int = 0,
        num_packets: int = 0,
    ) -> EventPacket:
        """Command board to being transmitting (vendor-specific).

        Sends a command to the board, telling it to begin transmitting
        the given number of packets of the given length, with the given payload,
        on the given channel, using the given PHY. The payload must be one
        of the values 0, 1, 2, 3, 4, 5, 6, or 7. Alternatively, payload
        selection values are declared in `utils/constants.py` as
        ADI_PAYLOAD_PRBS9 (0), ADI_PAYLOAD_11110000 (1), ADI_PAYLOAD_10101010 (2),
        ADI_PAYLOAD_PRBS15 (3), ADI_PAYLOAD_11111111 (4) ADI_PAYLOAD_00000000 (5),
        ADI_PAYLOAD_00001111 (6) and ADI_PAYLOAD_01010101 (7). The PHY must
        be one of the values 1, 2, 3 or 4. Alternatively, PHY selection
        values are declared in `utils/constants.py` as ADI_PHY_1M (1),
        ADI_PHY_2M (2), ADI_PHY_S8 (3), and ADI_PHY_S2 (4). A test end
        function must be called in order to end this process on the board.

        Parameters
        ----------
        channel : int
            The channel to transmit on.
        phy : int
            The PHY to use.
        payload : int
            The payload type to use.
        packet_len : int
            The TX packet length.
        num_packets : int
            The number of packets to transmit.

        Returns
        -------
        Event
            Object containing board return data.

        """
        params = [
            channel,
            packet_len,
            payload,
            phy,
            num_packets
        ]
        cmd = CommandPacket(OGF.VENDOR_SPEC, OCF.VENDOR_SPEC.TX_TEST, 6, params=params)
        evt = self._send_command(cmd)

        return evt

    def rx_test(self, channel: int = 0, phy: int = 1, modulation_idx: float = 0) -> EventPacket:
        """Command board to begin receiving.

        Sends a command to the board, telling it to begin receiving
        on the given channel using the given PHY. The PHY must
        be one of the values 1, 2, 3 or 4. Alternatively, PHY selection
        values are declared in `utils/constants.py` as ADI_PHY_1M (1),
        ADI_PHY_2M (2), ADI_PHY_S8 (3), and ADI_PHY_S2 (4). A test end
        function must be called in order to end this process on the board.

        Parameters
        ----------
        channel : int
            The channel to receive on.
        phy : int
            The PHY to use.

        Returns
        -------
        Event
            Object containing board return data.

        """
        if phy == self.PHY_S2:
            phy = self.PHY_S8

        params = [
            channel,
            phy,
            modulation_idx
        ]
        cmd = CommandPacket(
            OGF.LE_CONTROLLER, OCF.LE_CONTROLLER.ENHANCED_RECEIVER_TEST, 3, params=params)
        evt = self._send_command(cmd)

        return evt

    def rx_test_vs(
        self,
        channel: int = 0,
        phy: int = 1,
        num_packets: int = 0,
        modulation_idx: float = 0
    ) -> EventPacket:
        """Command board to begin receiving (vendor-specific).

        Sends a command to the board, telling it to begin receiving
        the given number of packets on the given channel using the given
        PHY. The PHY must be one of the values 1, 2, 3 or 4. Alternatively,
        PHY selection values are declared in `utils/constants.py` as
        ADI_PHY_1M (1), ADI_PHY_2M (2), ADI_PHY_S8 (3), and ADI_PHY_S2 (4).
        A test end function must be called in order to end this process on
        the board.

        Parameters
        ----------
        channel : int
            The channel to receive on.
        phy : int
            The PHY to use.
        num_packets : int
            The number of packets to expect to receive.

        Returns
        -------
        Event
            Object containing board return data.

        """
        if phy == self.PHY_S2:
            phy = self.PHY_S8

        params = [
            channel,
            phy,
            modulation_idx,
            num_packets
        ]

        cmd = CommandPacket(OGF.VENDOR_SPEC, OCF.VENDOR_SPEC.RX_TEST, 5, params=params)
        evt = self._send_command(cmd)

        return evt

    def end_test(self) -> EventPacket:
        """Command board to end the current test.

        Sends a command to the board, telling it to end whatever test
        it is currently running. Function then parses the test stats
        and returns the number of properly received packets.

        Returns
        -------
        Union[int, None]
            The amount of properly received packets, or `None` if
            the return data from the board is empty. In this case
            it is likely that a test error occured.

        """
        cmd = CommandPacket(OGF.LE_CONTROLLER, OCF.LE_CONTROLLER.TEST_END, 0)
        evt = self._send_command(cmd)

        return evt
    
    def end_test_vs(self) -> EventPacket:
        """Command board to end the current test (vendor-specific).

        Sends a command to the board, telling it to end whatever test
        it is currently running. Function then parses and returns the
        test statistics, which inclue the number of packets properly
        received, the number of crc errors, the number of RX timeout
        occurances, and the number of TX packets sent.

        Returns
        -------
        Union[Dict[str, int], None]
            The test statistics, or `None` if the return data from
            the board is empty. In this case, it is likely that a
            test error occured.

        """
        cmd = CommandPacket(OGF.VENDOR_SPEC, OCF.VENDOR_SPEC.END_TEST, 0)
        evt = self._send_command(cmd)

        return evt

    def set_adv_tx_power(self, tx_power: int) -> EventPacket:
        """Set the advertising TX power.

        Sends a command to the board, telling
        it to set the advertising TX power to the given value.

        Parameters
        ----------
        power : int
            The desired TX power value.

        Returns
        -------
        EventPacket
            Object containing board return data from setting the
            advertising power.

        """
        cmd = CommandPacket(OGF.VENDOR_SPEC, OCF.VENDOR_SPEC.SET_ADV_TX_PWR, 1, params=tx_power)
        evt = self._send_command(cmd)
        return evt
    
    def set_conn_tx_power(self, tx_power: int, handle: int) -> EventPacket:
        """Set the connection TX power.

        Sends a command to the board, telling
        it to set the connection TX power to the given value.

        Parameters
        ----------
        power : int
            The desired TX power value.
        handle : int
            Connection handle.

        Returns
        -------
        EventPacket
            Object containing board return data from setting the
            connection power.

        """
        params = [
            handle,
            tx_power
        ]
        cmd = CommandPacket(OGF.VENDOR_SPEC, OCF.VENDOR_SPEC.SET_CONN_TX_PWR, 3, params=params)
        evt = self._send_command(cmd)
        return evt

    def disconnect(self) -> EventPacket:
        """Command board to disconnect from an initialized connection.

        Sends a command to the board, telling it to break a currently
        initialized connection. Board gives Local Host Termination (0x16)
        as the reason for the disconnection. Function is used to exit
        Connection Mode Testing.

        Returns
        -------
        Event
            Object containing board return data.

        """
        params = [
            0x0000,                         # Connection Handle
            0x16                            # Disconnect Reason
        ]
        cmd = CommandPacket(OGF.LINK_CONTROL, OCF.LINK_CONTROL.DISCONNECT, 3, params=params)
        evt = self._send_command(cmd)

        return evt

    def set_channel_map(
        self,
        channels: Optional[Union[List[int], int]] = None,
        mask: Optional[int] = None,
        handle: int = 0,
    ) -> EventPacket:
        """Set the channel map.

        Creates a channel map/mask based on the given arguments
        and sends a command to the board, telling it to set its
        internal channel map to the new one.

        Parameters
        ----------
        channel : int, optional
            Channel to mask out.
        mask : int, optional
            Channel mask to use.
        handle : int
            Connection handle.

        Returns
        -------
        Event
            Object containing board return data.

        """
        if not isinstance(channels, list):
            channels = [channels]

        if mask is None:
            if channels is None:             # Use all channels
                channel_mask = 0xFFFFFFFFFF
            elif channels == 0:              # Use channels 0 and 1
                channel_mask = 0x0000000003
            else:                           # Mask the given channel(s)
                channel_mask = 0x0000000001
                for chan in channels:
                    channel_mask = channel_mask | (1 << chan)
        else:
            channel_mask = mask

        channel_mask = channel_mask & ~(0xE000000000)
        self.logger.info("Channel Mask: 0x%X", channel_mask)

        params = [
            handle,
            channel_mask
        ]
        cmd = CommandPacket(OGF.VENDOR_SPEC, OCF.VENDOR_SPEC.SET_CHAN_MAP, 10, params=params)
        evt = self._send_command(cmd)

        return evt

    def command(
        self,
        command: CommandPacket,
        listen: Union[bool, int] = False,
        timeout: int = 6,
    ) -> EventPacket:
        """Send a custom command to the board.

        Sends a custom HCI command to the board. Safeguarding is
        not implemented, and therefore it is best to ensure desired
        command is supported prior to sending, and no error will
        be thrown for unsupported commands. The `command` argument will
        accept either a string or an integer value, however, string values
        must be in hex format, and integers must have originated from hex
        numbers. HCI can be directed to listen for events for either a finite
        number or seconds or indefinitely in accordance with the `listen`
        argument. Indefinite listening can only be ended with `CTRL-C`.

        Parameters
        ----------
        command : Union[str, int]
            The command to give the board. Can be a string or an integer.
            String input must be formatted as hex values.
        listen : Union[bool, int]
            Listen (finite or indefinite) for further events?
        timeout : int
            Command timeout. Set to None for indefinite.

        Returns
        -------
        Event
            Object containing board return data.

        """
        evt = self._send_command(command)

        if not listen:
            return evt
        
        if isinstance(listen, int):
            self._wait(seconds=listen)
        else:
            while True:
                self._wait(seconds=0)

        return evt

    def read_register(self, addr: Union[List[int], bytearray], length: int) -> List[int]:
        """Read data from a specific register.

        Sends a command to the board, telling it to read data
        or a given length from a given register address. Address
        must begin with '0x' and must be a string representing
        four bytes of hex data. Function both prints and returns
        the read data.

        Parameters
        ----------
        addr : str
            The register address to read from. Must being with '0x'
            and contain four bytes of hex data.
        length : int
            The desired length of the register read in bytes.

        Returns
        -------
        List[int]
            The data as read from the register.

        """
        if isinstance(addr, list):
            try:
                addr = bytearray(addr)
            except ValueError as err:
                self.logger.error("%s: %s", type(err).__name__, err)
                sys.exit(1)
            except TypeError as err:
                self.logger.error("%s: %s", type(err).__name__, err)

        self.logger.info("Reading %i bytes from address %08X", length, addr)

        params = [
            length,
            addr
        ]
        cmd = CommandPacket(OGF.VENDOR_SPEC, OCF.VENDOR_SPEC.REG_READ, 5, params=params)
        evt = self._send_command(cmd)

        param_len = [4] * int(length/4)
        param_len.append(length % 4)
        read_data = evt.return_vals
        curr_addr = addr

        for idx, data in enumerate(read_data):
            if param_len[idx] == 1:
                self.logger.info("0x%08X: 0x______%02X", curr_addr, data)
            elif param_len[idx] == 2:
                self.logger.info("0x%08X: 0x____%04X", curr_addr, data)
            elif param_len[idx] == 3:
                self.logger.info("0x%08X: 0x__%06X", curr_addr, data)
            else:
                self.logger.info("0x%08X: 0x%08X", curr_addr, data)

            curr_addr += 4

        return read_data

    def write_register(self, addr: str, data: int) -> EventPacket:
        """Write data to a specific register.

        Sends a command to the board, telling it to write the
        given data to the given register address. Address
        must begin with '0x' and must be a string representing
        four bytes of hex data. This function is not safeguarded,
        therefore it is important to ensure the proper register
        is being written to.

        Parameters
        ----------
        addr : str
            The register address to write to. Must being with '0x'
            and contain four bytes of hex data.
        data : int
            The data to write.

        Returns
        -------
        Event
            Object containing board return data.

        """
        write_length = max((data.bit_length() + 7) // 8, 1)
        
        if write_length > 4:
            self.logger.error("Input value can be no greater than 32 bits (4 bytes).")
            sys.exit(1)

        if isinstance(addr, list):
            try:
                addr = bytearray(addr)
            except ValueError as err:
                self.logger.error("%s: %s", type(err).__name__, err)
                sys.exit(1)
            except TypeError as err:
                self.logger.error("%s: %s", type(err).__name__, err)

        params = [
            write_length,
            addr,
            data
        ]
        cmd = CommandPacket(
            OGF.VENDOR_SPEC, OCF.VENDOR_SPEC.REG_WRITE, write_length + 5, params=params)
        evt = self._send_command(cmd)

        return evt

    def set_event_mask(self) -> int:
        """Create/setup test board event masks.

        Returns
        -------
        int
            Process statuses, 0x0 if all done correctly. Else,
            counts the number of failed processes.

        """
        mask = 0xFFFFFFFFFFFFFFFF
        status = 0
        cmd = CommandPacket(OGF.CONTROLLER, OCF.CONTROLLER.SET_EVENT_MASK, 8, params=mask)
        evt = self._send_command(cmd)
        if evt.status:
            status += 1

        cmd = CommandPacket(OGF.CONTROLLER, OCF.CONTROLLER.SET_EVENT_MASK_PAGE2, 8, params=mask)
        evt = self._send_command(cmd)
        if evt.status:
            status += 1

        cmd = CommandPacket(OGF.CONTROLLER, OCF.CONTROLLER.SET_EVENT_MASK, 8, params=mask)
        evt = self._send_command(cmd)
        if evt.status:
            status += 1

        cmd = CommandPacket(OGF.LE_CONTROLLER, OCF.LE_CONTROLLER.SET_EVENT_MASK, 8, params=mask)
        evt = self._send_command(cmd)
        if evt.status:
            status += 1

        return status

    def exit(self) -> None:
        """Close the HCI connection.

        Used to safely close the connection between the HCI and
        the test board.

        """
        if self.port.is_open:
            self.port.flush()
            self.port.close()

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

    def _parse_conn_stats_evt(self, evt: EventPacket) -> float:
        """Parse connection statistics packet.

        PRIVATE

        """
        try:
            stats = evt.return_vals
            rx_data_ok = stats[0:4]
            rx_data_crc = stats[4:8]
            rx_data_to = stats[8:12]
            tx_data = stats[12:16]
            err_trans = stats[16:20]
        except ValueError as err:
            self.logger.error("%s: %s", type(err).__name__, err)
            return None

        self.logger.info("%s<", self.id_tag)
        self.logger.info("rxDataOK   : %i", rx_data_ok)
        self.logger.info("rxDataCRC  : %i", rx_data_crc)
        self.logger.info("rxDataTO   : %i", rx_data_to)
        self.logger.info("txData     : %i", tx_data)
        self.logger.info("errTrans   : %i", err_trans)

        per = 100.0
        if rx_data_crc + rx_data_to + rx_data_ok != 0:
            per = round(
                float(
                    (rx_data_crc + rx_data_to) / (rx_data_crc + rx_data_to + rx_data_ok)
                )
                * 100,
                2,
            )
            self.logger.info("PER         : %i%%", per)

        return per

    def _read_event(self, timeout: float = 6.0) -> EventPacket:
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
            return None
        if evt_type == PacketTypes.EVENT:
            return EventPacket.from_bytes(evt)
        
    def _wait(self, seconds: int = 2) -> None:
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
        pkt: CommandPacket,
        delay: float = 0.1,
        timeout: int = 6
    ) -> EventPacket:
        """Sends a command to the test board and retrieves the response.
        
        PRIVATE
        
        """
        self.logger.info("%s  %s>%s", datetime.datetime.now(), self.id_tag, pkt.to_bytes().hex())

        self.port.flush()
        self.port.write(pkt.to_bytes())

        return self._read_event(timeout=timeout)


    # def write_command(self, command : CommandPacket) -> EventPacket:
    #     self.port.flush()
    #     self.port.write(command.to_bytes())
    #     evt_code = self.port.read(1)
    #     param_len = self.port.read(1)    
        
    #     data = [evt_code, param_len]
        
    #     for _ in range(int(param_len)):    
    #         data.append(int.from_bytes(self.port.read(), 'little'))

    #     return EventPacket.from_bytes(data)
    
    # def write_command(self, command: CommandPacket) -> EventPacket:
    #     self.port.flush()
    #     self.port.write(command.to_bytes())
    #     return self.read_event()
    # def write_command_raw(self, data):
    #     self.port.flush()
    #     self.port.write(data)
    #     return self.read_event()

    # def reset(self) -> EventPacket:
    #     """Sets log level.
    #     Resets the controller

    #     Returns
    #     ----------
    #     Event: EventPacket

    #     """
    #     return self.write_command(CommandPacket(ocf=OCF.CONTROLLER.RESET,
    #                                              ogf=OGF.CONTROLLER, params=[0]))
