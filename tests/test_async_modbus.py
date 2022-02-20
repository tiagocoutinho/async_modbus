#!/usr/bin/env python
"""Tests for `async_modbus` package."""
import pytest
import umodbus.client.tcp
import umodbus.exceptions
import umodbus.functions
import umodbus.utils

import async_modbus


class Server:
    def __init__(self, slave_id, starting_address, values):
        self.multiple = isinstance(values, (list, tuple))
        self.slave_id = slave_id
        self.starting_address = starting_address
        self.response = values
        self.request_adu = b""
        self.reply_adu = None

    def get_header_pdu(self):
        return umodbus.utils.unpack_mbap(self.request_adu[:7]), self.request_adu[7:]

    def process(self):
        (tid, pid, length, uid), pdu = self.get_header_pdu()
        func_obj = umodbus.functions.create_function_from_request_pdu(pdu)
        assert self.slave_id == uid
        if self.multiple:
            n = (
                func_obj.quantity
                if hasattr(func_obj, "quantity")
                else len(func_obj.values)
            )
            assert len(self.response) == n
            assert self.starting_address == func_obj.starting_address
        else:
            assert self.starting_address == func_obj.address
        try:
            response_pdu = func_obj.create_response_pdu(self.response)
        except TypeError:
            response_pdu = func_obj.create_response_pdu()
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

    with pytest.raises(ValueError):
        async_modbus.modbus_for_url("unknown:///dev/ttyS0")

    modbus = async_modbus.modbus_for_url("tcp://localhost:1000")
    assert isinstance(modbus, async_modbus.AsyncTCPClient)

    modbus = async_modbus.modbus_for_url("serial:///dev/ttyS0")
    assert isinstance(modbus, async_modbus.AsyncRTUClient)


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


read_u16_data = [
    (0, 0, [0]),
    (0, 0, [12345]),
    (0, 0, [2**15 - 1]),
    (6, 7, [2**15 - 1, 0, 2**14]),
    (1, 3, [12345, 0, 2**15 - 1, 2**15 - 1]),
    (5, 10, 10 * [123] + 15 * [2**15 - 1] + 5 * [0]),
    (0, 0, 115 * [7654] + 10 * [2**15 - 1]),
    (0, 0, []),
]


write_u16_data = [
    (0, 0, [0]),
    (0, 0, [12345]),
    (0, 0, [2**15 - 1]),
    (6, 7, [2**15 - 1, 0, 2**14]),
    (1, 3, [12345, 0, 2**15 - 1, 2**15 - 1]),
    (5, 10, 10 * [123] + 15 * [2**15 - 1] + 5 * [0]),
    (0, 0, 115 * [7654] + 10 * [2**15 - 1]),
    (0, 0, []),
]


def ids(v):
    if isinstance(v, (list, tuple)) and len(v) > 5:
        return f"SEQ#{len(v)}"
    return str(v)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "slave_id, starting_address, expected_reply", read_bits_data, ids=ids
)
async def test_read_coils(slave_id, starting_address, expected_reply):

    quantity = len(expected_reply)

    server = Server(slave_id, starting_address, expected_reply)
    client = async_modbus.AsyncTCPClient(server)
    coro = client.read_coils(slave_id, starting_address, quantity)
    if not quantity:
        with pytest.raises(umodbus.exceptions.IllegalDataValueError):
            await coro
    else:
        reply = await coro
        assert (reply == expected_reply).all()

    server = Server(slave_id, starting_address, expected_reply)
    client = async_modbus.AsyncClient(server, umodbus.client.tcp)
    coro = client.read_coils(slave_id, starting_address, quantity)
    if not quantity:
        with pytest.raises(umodbus.exceptions.IllegalDataValueError):
            await coro
    else:
        reply = await coro
        assert (reply == expected_reply).all()


@pytest.mark.asyncio
@pytest.mark.parametrize("slave_id, starting_address, value", write_bit_data, ids=ids)
async def test_write_coil(slave_id, starting_address, value):

    server = Server(slave_id, starting_address, value)
    client = async_modbus.AsyncTCPClient(server)
    reply = await client.write_coil(slave_id, starting_address, value)
    assert reply == value

    server = Server(slave_id, starting_address, value)
    client = async_modbus.AsyncClient(server, umodbus.client.tcp)
    reply = await client.write_coil(slave_id, starting_address, value)
    assert reply == value


@pytest.mark.asyncio
@pytest.mark.parametrize("slave_id, starting_address, values", write_bits_data, ids=ids)
async def test_write_coils(slave_id, starting_address, values):

    quantity = len(values)

    server = Server(slave_id, starting_address, values)
    client = async_modbus.AsyncTCPClient(server)
    coro = client.write_coils(slave_id, starting_address, values)
    if not quantity:
        with pytest.raises(umodbus.exceptions.IllegalDataValueError):
            await coro
    else:
        reply = await coro
        assert reply == quantity

    server = Server(slave_id, starting_address, values)
    client = async_modbus.AsyncClient(server, umodbus.client.tcp)
    coro = client.write_coils(slave_id, starting_address, values)
    if not quantity:
        with pytest.raises(umodbus.exceptions.IllegalDataValueError):
            await coro
    else:
        reply = await coro
        assert reply == quantity


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "slave_id, starting_address, expected_reply",
    read_bits_data,
    ids=ids,
)
async def test_read_discrete_inputs(slave_id, starting_address, expected_reply):

    quantity = len(expected_reply)

    server = Server(slave_id, starting_address, expected_reply)
    client = async_modbus.AsyncTCPClient(server)
    coro = client.read_discrete_inputs(slave_id, starting_address, quantity)
    if not quantity:
        with pytest.raises(umodbus.exceptions.IllegalDataValueError):
            await coro
    else:
        reply = await coro
        assert (reply == expected_reply).all()

    server = Server(slave_id, starting_address, expected_reply)
    client = async_modbus.AsyncClient(server, umodbus.client.tcp)
    coro = client.read_discrete_inputs(slave_id, starting_address, quantity)
    if not quantity:
        with pytest.raises(umodbus.exceptions.IllegalDataValueError):
            await coro
    else:
        reply = await coro
        assert (reply == expected_reply).all()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "slave_id, starting_address, expected_reply", read_u16_data, ids=ids
)
async def test_read_holding_registers(slave_id, starting_address, expected_reply):

    quantity = len(expected_reply)

    server = Server(slave_id, starting_address, expected_reply)
    client = async_modbus.AsyncTCPClient(server)
    coro = client.read_holding_registers(slave_id, starting_address, quantity)
    if not quantity:
        with pytest.raises(umodbus.exceptions.IllegalDataValueError):
            await coro
    else:
        reply = await coro
        assert (reply == expected_reply).all()

    server = Server(slave_id, starting_address, expected_reply)
    client = async_modbus.AsyncClient(server, umodbus.client.tcp)
    coro = client.read_holding_registers(slave_id, starting_address, quantity)
    if not quantity:
        with pytest.raises(umodbus.exceptions.IllegalDataValueError):
            await coro
    else:
        reply = await coro
        assert (reply == expected_reply).all()


@pytest.mark.asyncio
@pytest.mark.parametrize("slave_id, starting_address, value", write_bit_data, ids=ids)
async def test_write_register(slave_id, starting_address, value):

    server = Server(slave_id, starting_address, value)
    client = async_modbus.AsyncTCPClient(server)
    reply = await client.write_register(slave_id, starting_address, value)
    assert reply == value

    server = Server(slave_id, starting_address, value)
    client = async_modbus.AsyncClient(server, umodbus.client.tcp)
    reply = await client.write_register(slave_id, starting_address, value)
    assert reply == value


@pytest.mark.asyncio
@pytest.mark.parametrize("slave_id, starting_address, values", write_u16_data, ids=ids)
async def test_write_registers(slave_id, starting_address, values):

    quantity = len(values)

    server = Server(slave_id, starting_address, values)
    client = async_modbus.AsyncTCPClient(server)
    coro = client.write_registers(slave_id, starting_address, values)
    if not quantity:
        with pytest.raises(umodbus.exceptions.IllegalDataValueError):
            await coro
    else:
        reply = await coro
        assert reply == quantity

    server = Server(slave_id, starting_address, values)
    client = async_modbus.AsyncClient(server, umodbus.client.tcp)
    coro = client.write_registers(slave_id, starting_address, values)
    if not quantity:
        with pytest.raises(umodbus.exceptions.IllegalDataValueError):
            await coro
    else:
        reply = await coro
        assert reply == quantity


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "slave_id, starting_address, expected_reply", read_u16_data, ids=ids
)
async def test_read_input_registers(slave_id, starting_address, expected_reply):

    quantity = len(expected_reply)

    server = Server(slave_id, starting_address, expected_reply)
    client = async_modbus.AsyncTCPClient(server)
    coro = client.read_input_registers(slave_id, starting_address, quantity)
    if not quantity:
        with pytest.raises(umodbus.exceptions.IllegalDataValueError):
            await coro
    else:
        reply = await coro
        assert (reply == expected_reply).all()

    server = Server(slave_id, starting_address, expected_reply)
    client = async_modbus.AsyncClient(server, umodbus.client.tcp)
    coro = client.read_input_registers(slave_id, starting_address, quantity)
    if not quantity:
        with pytest.raises(umodbus.exceptions.IllegalDataValueError):
            await coro
    else:
        reply = await coro
        assert (reply == expected_reply).all()
