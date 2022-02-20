#!/usr/bin/env python
"""Tests for `async_modbus` package."""
import pytest
import umodbus.functions
import umodbus.utils

import async_modbus


class ReadCoils:
    def __init__(self, slave_id, starting_address, values):
        self.slave_id = slave_id
        self.starting_address = starting_address
        self.quantity = len(values)
        self.response = values
        self.request_adu = b""
        self.reply_adu = None

    def get_header_pdu(self):
        return umodbus.utils.unpack_mbap(self.request_adu[:7]), self.request_adu[7:]

    def process(self):
        (tid, pid, length, uid), pdu = self.get_header_pdu()
        func_obj = umodbus.functions.create_function_from_request_pdu(pdu)
        assert self.slave_id == uid
        assert self.quantity == func_obj.quantity
        assert self.starting_address == func_obj.starting_address
        response_pdu = func_obj.create_response_pdu(self.response)
        response_header = umodbus.utils.pack_mbap(tid, pid, len(response_pdu) + 1, uid)
        return response_header + response_pdu

    async def write(self, data):
        self.request_adu += data

    async def readexactly(self, n):
        if self.reply_adu is None:
            self.reply_adu = self.process()
        reply = self.reply_adu[:n]
        self.reply_adu = self.reply_adu[n:]
        return reply

    def close(self):
        self.reply_adu = None


def test_modbus_for_url():

    with pytest.raises(TypeError):
        async_modbus.modbus_for_url()

    with pytest.raises(ValueError):
        async_modbus.modbus_for_url("something silly")

    modbus = async_modbus.modbus_for_url("tcp://localhost:1000")
    assert isinstance(modbus, async_modbus.AsyncTCPClient)

    modbus = async_modbus.modbus_for_url("serial:///dev/ttyS0")
    assert isinstance(modbus, async_modbus.AsyncRTUClient)


read_coils_data = [
    (0, 0, [0]),
    (0, 0, [1]),
    (6, 7, [1, 0, 1]),
    (1, 3, [1, 0, 1, 1]),
    (5, 10, 10 * [1] + 15 * [0] + 5 * [1]),
    (0, 0, 200 * [0] + 10 * [1]),
]


def idfn(v):
    if isinstance(v, (list, tuple)) and len(v) > 5:
        return f"SEQ#{len(v)}"
    return str(v)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "slave_id, starting_address, expected_reply", read_coils_data, ids=idfn
)
async def test_read_coils(slave_id, starting_address, expected_reply):

    server = ReadCoils(slave_id, starting_address, expected_reply)

    client = async_modbus.AsyncTCPClient(server)

    quantity = len(expected_reply)

    reply = await client.read_coils(slave_id, starting_address, quantity)

    assert (reply == expected_reply).all()
