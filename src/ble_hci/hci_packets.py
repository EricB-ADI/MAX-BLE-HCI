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

from enum import Enum
from typing import List, Optional, Union

from .packet_codes import EventCode, StatusCode, EventSubcode
from .packet_defs import OCF, OGF, PacketType

def _byte_length(num: int):
    return max((num.bit_length() + 7) // 8, 1)

class Endian(Enum):
    LITTLE = "little"
    BIG = "big"


class CommandPacket:
    """
    Command Packet Class
    """

    def __init__(self, ogf, ocf, params=None) -> None:
        self.ogf = self._enum_to_int(ogf)
        self.ocf = self._enum_to_int(ocf)
        self.length = self._get_length(params)
        self.opcode = CommandPacket.make_hci_opcode(self.ogf, self.ocf)
        if params is not None:
            self.params = params if isinstance(params, list) else [params]
        else:
            self.params = None

    def __repr__(self):
        return str(self.__dict__)

    def _enum_to_int(self, num):
        if isinstance(num, Enum):
            return num.value
        else:
            return num

    def _get_length(self, params):
        if params is None:
            return 0
        if isinstance(params, int):
            return _byte_length(params)

        return sum([_byte_length(x) for x in params])

    @staticmethod
    def make_hci_opcode(ogf: OGF, ocf: OCF):
        """Makes an HCI opcode.

        Function creates an HCI opcode from the given
        Opcode Group Field (OGF) and Opcode Command Field (OCF).

        Parameters
        ----------
        ogf : Union[OGF, int]
            Opcode group field.
        ocf : Union[Enum, int]
            Opcode command field.

        Returns
        -------
        int
            The generated HCI opcode.

        """
        if not isinstance(ogf, int):
            if isinstance(ogf, Enum):
                ogf = ogf.value
            else:
                raise TypeError(
                    "Parameter 'ogf' must be an integer or an OGF enumeration."
                )

        if not isinstance(ocf, int):
            if isinstance(ocf, Enum):
                ocf = ocf.value
            else:
                raise TypeError(
                    "Parameter 'ogf' must be an integer or an OCF enumeration."
                )

        return (ogf << 10) | ocf

    def to_bytes(self, endianness: Endian = Endian.LITTLE) -> bytearray:
        """Serializes a command packet to a byte array.

        Parameters
        ----------
        endianness : int
            `Endian.LITTLE` for little endian serialization,
            `Endian.BIG` for big endian serialization.

        Returns
        -------
        bytearray
            The serialized command.

        """
        serialized_cmd = bytearray()
        serialized_cmd.append(PacketType.COMMAND.value)
        serialized_cmd.append(self.opcode & 0xFF)
        serialized_cmd.append((self.opcode & 0xFF00) >> 8)

        serialized_cmd.append(self.length)

        if self.params is not None:
            for param in self.params:
                num_bytes = _byte_length(param)
                try:
                    serialized_cmd.extend(param.to_bytes(num_bytes, endianness.value))
                except OverflowError:
                    serialized_cmd.extend(
                        param.to_bytes(num_bytes, endianness.value, signed=True)
                    )

        return serialized_cmd


class AsyncPacket:
    def __init__(self, handle, pb_flag, bc_flag, length, data) -> None:
        self.handle = handle
        self.pb_flag = pb_flag
        self.bc_flag = bc_flag
        self.length = length
        self.data = data

    def __repr__(self):
        return str(self.__dict__)

    @staticmethod
    def from_bytes(pkt):
        return AsyncPacket(
            handle=(pkt[0] & 0xF0) + (pkt[1] << 8),
            pb_flag=(pkt[0] & 0xC) >> 2,
            bc_flag=pkt[0] & 0x3,
            length=pkt[2] + (pkt[3] << 8),
            data=pkt[4:] if pkt[4:] else None,
        )


class EventPacket:
    def __init__(self, evt_code, length, status, evt_params, evt_subcode=None) -> None:
        self.evt_code = EventCode(evt_code)
        self.length = length
        self.status = StatusCode(status) if status else None
        self.evt_subcode = EventSubcode(evt_subcode) if evt_subcode else None
        self.evt_params = evt_params

    def __repr__(self):
        return str(self.__dict__)

    @staticmethod
    def from_bytes(serialized_event, endianness=Endian.LITTLE):
        if serialized_event[0] == EventCode.COMMAND_COMPLETE.value:
            return EventPacket(
                evt_code=serialized_event[0],
                length=serialized_event[1],
                status=serialized_event[5],
                evt_params=serialized_event[2:]
            )
        if serialized_event[0] == EventCode.HARDWARE_ERROR.value:
            return EventPacket(
                evt=serialized_event[0],
                length=serialized_event[1],
                status=StatusCode.LL_ERROR_CODE_HW_FAILURE.value,
                evt_params=serialized_event[2:]
            )
        if serialized_event[0] == EventCode.NUM_COMPLETED_PACKETS.value:
            return EventPacket(
                evt_code=serialized_event[0],
                length=serialized_event[1],
                status=StatusCode.LL_SUCCESS.value,
                evt_params=serialized_event[2:]
            )
        if serialized_event[0] == EventCode.DATA_BUFF_OVERFLOW.value:
            return EventPacket(
                evt_code=serialized_event[0],
                length=serialized_event[1],
                status=None,
                evt_params=serialized_event[2:]
            )
        if serialized_event[0] == EventCode.LE_META.value:
            return EventPacket(
                evt_code=serialized_event[0],
                length=serialized_event[1],
                status=None,
                evt_params=serialized_event[3:],
                evt_subcode=serialized_event[2]
            )
        if serialized_event[0] == EventCode.AUTH_PAYLOAD_TIMEOUT_EXPIRED.value:
            return EventPacket(
                evt_code=serialized_event[0],
                length=serialized_event[1],
                status=None,
                evt_params=serialized_event[2:]
            )
        
        return EventPacket(
            evt_code=serialized_event[0],
            length=serialized_event[1],
            status=serialized_event[2],
            evt_params=serialized_event[3:]
        )

    def get_return_params(
        self,
        param_lens: Optional[List[int]] = None,
        endianness: Endian = Endian.LITTLE,
        use_raw: bool = False,
        signed: bool = False,
    ) -> Union[List[int], int]:
        if use_raw:
            param_bytes = self.evt_params
        else:
            param_bytes = self.evt_params[4:]

        if not param_lens:
            return int.from_bytes(param_bytes, endianness.value, signed=signed)

        if sum(param_lens) > len(param_bytes):
            raise ValueError(
                "Expected and actual number of return bytes do not match. "
                f"Expected={sum(param_lens)}, Actual={len(param_bytes)}"
            )

        return_params = []
        p_idx = 0
        for p_len in param_lens:
            return_params.append(
                int.from_bytes(param_bytes[p_idx : p_idx + p_len], endianness.value)
            )
            p_idx += p_len

        return return_params


class ExtendedPacket:
    def __init__(self, data):
        self.opcode = data[0] + (data[1] << 8)
        self.length = data[2] + (data[3] << 8)
        self.payload = data[4:] if data[4:] else None

    def __repr__(self):
        return str(self.__dict__)

    @staticmethod
    def from_bytes(serialized_event):
        return ExtendedPacket(serialized_event)
