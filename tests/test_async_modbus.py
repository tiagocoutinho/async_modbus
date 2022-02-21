#!/usr/bin/env python
"""Tests for `async_modbus` package."""
import struct
import sys
from contextlib import contextmanager

import pytest
from umodbus.client import tcp
from umodbus.client.serial import rtu
from umodbus.client.serial.redundancy_check import get_crc
from umodbus.exceptions import IllegalDataValueError
from umodbus.functions import create_function_from_request_pdu
from umodbus.utils import pack_mbap
from umodbus.utils import unpack_mbap

from async_modbus import AsyncClient
from async_modbus import AsyncRTUClient
from async_modbus import AsyncTCPClient
from async_modbus import modbus_for_url


class BaseServer:
    def __init__(self, slave_id, starting_address, values):
        self.multiple = isinstance(values, (list, tuple))
        self.slave_id = slave_id
        self.starting_address = starting_address
        self.response = values
        self.request_adu = b""
        self.reply_adu = None

    @property
    def request_pdu(self):
        raise NotImplementedError

    def response_adu(self, pdu):
        raise NotImplementedError

    def process(self):
        pdu = self.request_pdu
        func = create_function_from_request_pdu(pdu)
        if self.multiple:
            n = func.quantity if hasattr(func, "quantity") else len(func.values)
            assert len(self.response) == n
            assert self.starting_address == func.starting_address
        else:
            assert self.starting_address == func.address
        try:
            response_pdu = func.create_response_pdu(self.response)
        except TypeError:
            response_pdu = func.create_response_pdu()
        return self.response_adu(response_pdu)

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


class TCPServer(BaseServer):
    @property
    def request_header(self):
        return unpack_mbap(self.request_adu[:7])

    @property
    def request_pdu(self):
        return self.request_adu[7:]

    def response_adu(self, pdu):
        (tid, pid, _, uid) = self.request_header
        assert self.slave_id == uid
        return pack_mbap(tid, pid, len(pdu) + 1, uid) + pdu


class RTUServer(BaseServer):
    @property
    def request_header(self):
        return struct.unpack(">B", self.request_adu[:1])[0]

    @property
    def request_pdu(self):
        return self.request_adu[1:-2]

    def response_adu(self, pdu):
        response = self.request_adu[0:1] + pdu
        return response + get_crc(response)


@contextmanager
def otype(otype):
    yield otype


@pytest.mark.parametrize(
    "url, expect",
    [
        ("something silly", pytest.raises(ValueError)),
        ("unknown:///dev/ttyS0", pytest.raises(ValueError)),
        ("tcp://localhost:1000", otype(AsyncTCPClient)),
        pytest.param(
            "serial:///dev/ttyS0",
            otype(AsyncRTUClient),
            marks=pytest.mark.skipif(
                sys.platform.startswith("win"), reason="no /dev on windows"
            ),
        ),
    ],
)
def test_modbus_for_url(url, expect):
    with expect as otype:
        isinstance(modbus_for_url(url), otype)


read_bits_data = [
    (0, 0, [0]),
    (0, 0, [1]),
    (6, 7, [1, 0, 1]),
    (1, 3, [1, 0, 1, 1]),
    (5, 10, 10 * [1] + 15 * [0] + 5 * [1]),
    (0, 0, 1200 * [0] + 10 * [1]),
    (0, 0, 400 * [0, 1, 0, 1, 1]),  # max of 2000 bits
    (0, 0, []),
]


write_bits_data = [
    (0, 0, [0]),
    (0, 0, [1]),
    (6, 7, [1, 0, 1]),
    (1, 3, [1, 0, 1, 1]),
    (5, 10, 10 * [1] + 15 * [0] + 5 * [1]),
    (0, 0, 1200 * [0] + 10 * [1]),
    (0, 0, 492 * [0, 1, 0, 0]),  # max of 1968 bits
    (0, 0, []),
]


write_bit_data = [
    (0, 0, 0),
    (0, 0, 1),
    (6, 7, 0),
    (6, 7, 1),
    (1, 3, 0),
    (1, 3, 1),
]


u16_data = [
    (0, 0, [0]),
    (0, 0, [12345]),
    (0, 0, [2**16 - 1]),
    (6, 7, [2**16 - 1, 0, 2**14]),
    (1, 3, [12345, 0, 2**16 - 1, 2**16 - 1]),
    (5, 10, 10 * [123] + 16 * [2**16 - 1] + 5 * [0]),
    (0, 0, 115 * [7654] + 10 * [2**16 - 1]),
    (0, 0, []),
]


protocols = [
    (TCPServer, AsyncTCPClient, tcp),
    (RTUServer, AsyncRTUClient, rtu),
]


def ids(v):
    if isinstance(v, (list, tuple)) and len(v) > 5:
        return f"SEQ#{len(v)}"
    return str(v)


@pytest.mark.asyncio
@pytest.mark.parametrize("proto", protocols, ids=["tcp", "rtu"])
@pytest.mark.parametrize(
    "slave_id, starting_address, expected_reply", read_bits_data, ids=ids
)
async def test_read_coils(proto, slave_id, starting_address, expected_reply):

    Server, Client, protocol = proto
    quantity = len(expected_reply)

    server = Server(slave_id, starting_address, expected_reply)
    client = Client(server)
    coro = client.read_coils(slave_id, starting_address, quantity)
    if not quantity:
        with pytest.raises(IllegalDataValueError):
            await coro
    else:
        reply = await coro
        assert (reply == expected_reply).all()

    server = Server(slave_id, starting_address, expected_reply)
    client = AsyncClient(server, protocol)
    coro = client.read_coils(slave_id, starting_address, quantity)
    if not quantity:
        with pytest.raises(IllegalDataValueError):
            await coro
    else:
        reply = await coro
        assert (reply == expected_reply).all()


@pytest.mark.asyncio
@pytest.mark.parametrize("proto", protocols, ids=["tcp", "rtu"])
@pytest.mark.parametrize("slave_id, starting_address, value", write_bit_data, ids=ids)
async def test_write_coil(proto, slave_id, starting_address, value):
    Server, Client, protocol = proto

    server = Server(slave_id, starting_address, value)
    client = Client(server)
    reply = await client.write_coil(slave_id, starting_address, value)
    assert reply == value

    server = Server(slave_id, starting_address, value)
    client = AsyncClient(server, protocol)
    reply = await client.write_coil(slave_id, starting_address, value)
    assert reply == value


@pytest.mark.asyncio
@pytest.mark.parametrize("proto", protocols, ids=["tcp", "rtu"])
@pytest.mark.parametrize("slave_id, starting_address, values", write_bits_data, ids=ids)
async def test_write_coils(proto, slave_id, starting_address, values):
    Server, Client, protocol = proto

    quantity = len(values)

    server = Server(slave_id, starting_address, values)
    client = Client(server)
    coro = client.write_coils(slave_id, starting_address, values)
    if not quantity:
        with pytest.raises(IllegalDataValueError):
            await coro
    else:
        reply = await coro
        assert reply == quantity

    server = Server(slave_id, starting_address, values)
    client = AsyncClient(server, protocol)
    coro = client.write_coils(slave_id, starting_address, values)
    if not quantity:
        with pytest.raises(IllegalDataValueError):
            await coro
    else:
        reply = await coro
        assert reply == quantity


@pytest.mark.asyncio
@pytest.mark.parametrize("proto", protocols, ids=["tcp", "rtu"])
@pytest.mark.parametrize(
    "slave_id, starting_address, expected_reply",
    read_bits_data,
    ids=ids,
)
async def test_read_discrete_inputs(proto, slave_id, starting_address, expected_reply):
    Server, Client, protocol = proto

    quantity = len(expected_reply)

    server = Server(slave_id, starting_address, expected_reply)
    client = Client(server)
    coro = client.read_discrete_inputs(slave_id, starting_address, quantity)
    if not quantity:
        with pytest.raises(IllegalDataValueError):
            await coro
    else:
        reply = await coro
        assert (reply == expected_reply).all()

    server = Server(slave_id, starting_address, expected_reply)
    client = AsyncClient(server, protocol)
    coro = client.read_discrete_inputs(slave_id, starting_address, quantity)
    if not quantity:
        with pytest.raises(IllegalDataValueError):
            await coro
    else:
        reply = await coro
        assert (reply == expected_reply).all()


@pytest.mark.asyncio
@pytest.mark.parametrize("proto", protocols, ids=["tcp", "rtu"])
@pytest.mark.parametrize(
    "slave_id, starting_address, expected_reply", u16_data, ids=ids
)
async def test_read_holding_registers(
    proto, slave_id, starting_address, expected_reply
):
    Server, Client, protocol = proto

    quantity = len(expected_reply)

    server = Server(slave_id, starting_address, expected_reply)
    client = Client(server)
    coro = client.read_holding_registers(slave_id, starting_address, quantity)
    if not quantity:
        with pytest.raises(IllegalDataValueError):
            await coro
    else:
        reply = await coro
        assert (reply == expected_reply).all()

    server = Server(slave_id, starting_address, expected_reply)
    client = AsyncClient(server, protocol)
    coro = client.read_holding_registers(slave_id, starting_address, quantity)
    if not quantity:
        with pytest.raises(IllegalDataValueError):
            await coro
    else:
        reply = await coro
        assert (reply == expected_reply).all()


@pytest.mark.asyncio
@pytest.mark.parametrize("proto", protocols, ids=["tcp", "rtu"])
@pytest.mark.parametrize("slave_id, starting_address, value", write_bit_data, ids=ids)
async def test_write_register(proto, slave_id, starting_address, value):
    Server, Client, protocol = proto

    server = Server(slave_id, starting_address, value)
    client = Client(server)
    reply = await client.write_register(slave_id, starting_address, value)
    assert reply == value

    server = Server(slave_id, starting_address, value)
    client = AsyncClient(server, protocol)
    reply = await client.write_register(slave_id, starting_address, value)
    assert reply == value


@pytest.mark.asyncio
@pytest.mark.parametrize("proto", protocols, ids=["tcp", "rtu"])
@pytest.mark.parametrize("slave_id, starting_address, values", u16_data, ids=ids)
async def test_write_registers(proto, slave_id, starting_address, values):
    Server, Client, protocol = proto

    quantity = len(values)

    server = Server(slave_id, starting_address, values)
    client = Client(server)
    coro = client.write_registers(slave_id, starting_address, values)
    if not quantity:
        with pytest.raises(IllegalDataValueError):
            await coro
    else:
        reply = await coro
        assert reply == quantity

    server = Server(slave_id, starting_address, values)
    client = AsyncClient(server, protocol)
    coro = client.write_registers(slave_id, starting_address, values)
    if not quantity:
        with pytest.raises(IllegalDataValueError):
            await coro
    else:
        reply = await coro
        assert reply == quantity


@pytest.mark.asyncio
@pytest.mark.parametrize("proto", protocols, ids=["tcp", "rtu"])
@pytest.mark.parametrize(
    "slave_id, starting_address, expected_reply", u16_data, ids=ids
)
async def test_read_input_registers(proto, slave_id, starting_address, expected_reply):
    Server, Client, protocol = proto

    quantity = len(expected_reply)

    server = Server(slave_id, starting_address, expected_reply)
    client = Client(server)
    coro = client.read_input_registers(slave_id, starting_address, quantity)
    if not quantity:
        with pytest.raises(IllegalDataValueError):
            await coro
    else:
        reply = await coro
        assert (reply == expected_reply).all()

    server = Server(slave_id, starting_address, expected_reply)
    client = AsyncClient(server, protocol)
    coro = client.read_input_registers(slave_id, starting_address, quantity)
    if not quantity:
        with pytest.raises(IllegalDataValueError):
            await coro
    else:
        reply = await coro
        assert (reply == expected_reply).all()
