# -*- coding: utf-8 -*-
#
# This file is part of the Async ModBus project
#
# Copyright (c) 2020 Tiago Coutinho
# Distributed under the GNU General Public License v3. See LICENSE for info.

"""Top-level package for async modbus library"""

import struct
import inspect
import urllib.parse

from umodbus import conf, functions
from umodbus.client import tcp
from umodbus.client.serial import rtu
from umodbus.exceptions import IllegalDataValueError

import numpy


__author__ = """Tiago Coutinho"""
__email__ = "coutinhotiago@gmail.com"
__version__ = "0.1.4"


async def send_message_tcp(adu, reader, writer):
    """ Send ADU over asyncio reader/writer and return parsed response.

    :param adu: Request ADU.
    :param reader: an async stream reader (ex: asyncio.StreamReader)
    :param writer: an async stream writer (ex: asyncio.StreamWriter)
    :return: Parsed response from server.
    """
    writer.write(adu)
    await writer.drain()

    exception_adu_size = 9
    response_error_adu = await reader.readexactly(exception_adu_size)
    tcp.raise_for_exception_adu(response_error_adu)

    expected_response_size = (
        tcp.expected_response_pdu_size_from_request_pdu(adu[7:]) + 7
    )
    response_remainder = await reader.readexactly(
        expected_response_size - exception_adu_size
    )

    return tcp.parse_response_adu(response_error_adu + response_remainder, adu)


async def send_message_rtu(adu, reader, writer):
    """ Send ADU over serial to to server and return parsed response.

    :param adu: Request ADU.
    :param reader: an async stream reader (ex: asyncio.StreamReader)
    :param writer: an async stream writer (ex: asyncio.StreamWriter)
    :return: Parsed response from server.
    """
    writer.write(adu)
    await writer.drain()

    # Check exception ADU (which is shorter than all other responses) first.
    exception_adu_size = 5
    response_error_adu = await reader.readexactly(exception_adu_size)
    rtu.raise_for_exception_adu(response_error_adu)

    expected_response_size = (
        rtu.expected_response_pdu_size_from_request_pdu(adu[1:-2]) + 3
    )
    response_remainder = await reader.readexactly(
        expected_response_size - exception_adu_size
    )

    return rtu.parse_response_adu(response_error_adu + response_remainder, adu)


tcp._async_send_message = send_message_tcp
rtu._async_send_message = send_message_rtu


def unpack_bits(resp_pdu, req_pdu):
    count = struct.unpack(">H", req_pdu[-2:])[0]
    byte_count = struct.unpack(">B", resp_pdu[1:2])[0]
    packed = numpy.frombuffer(resp_pdu, dtype="u1", offset=2, count=byte_count)
    return numpy.unpackbits(packed, count=count, bitorder="little")


def pack_bits(function_code, starting_address, values):
    if not isinstance(values, numpy.ndarray):
        values = numpy.array(values, dtype="u1")
    packed = numpy.packbits(values, bitorder="little")
    count = values.size
    header = struct.pack(
        ">BHHB", function_code, starting_address, count, (count + 7) // 8
    )
    return header + packed.tobytes()


def unpack_16bits(resp_pdu, req_pdu):
    count = struct.unpack(">H", req_pdu[-2:])[0]
    dtype = ">{}2".format("i" if conf.SIGNED_VALUES else "u")
    return numpy.frombuffer(resp_pdu, dtype=dtype, count=count, offset=2)


def pack_16bits(function_code, starting_address, values):
    dtype = ">{}2".format("i" if conf.SIGNED_VALUES else "u")
    values = numpy.array(values, dtype=dtype, copy=False)
    header = struct.pack(
        ">BHHB", function_code, starting_address, values.size, values.nbytes
    )
    return header + values.tobytes()


class ReadCoils(functions.ReadCoils):
    @classmethod
    def create_from_response_pdu(cls, resp_pdu, req_pdu):
        """ Create instance from response PDU.

        Response PDU is required together with the quantity of coils read.

        :param resp_pdu: Byte array with request PDU.
        :param quantity: Number of coils read.
        :return: Instance of :class:`ReadCoils`.
        """
        read_coils = cls()
        read_coils.data = unpack_bits(resp_pdu, req_pdu)
        read_coils.quantity = read_coils.data.size
        return read_coils


class ReadDiscreteInputs(functions.ReadDiscreteInputs):
    @classmethod
    def create_from_response_pdu(cls, resp_pdu, req_pdu):
        """ Create instance from response PDU.

        Response PDU is required together with the quantity of inputs read.

        :param resp_pdu: Byte array with request PDU.
        :param quantity: Number of inputs read.
        :return: Instance of :class:`ReadDiscreteInputs`.
        """
        read_discrete_inputs = cls()
        read_discrete_inputs.data = unpack_bits(resp_pdu, req_pdu)
        read_discrete_inputs.quantity = read_discrete_inputs.data.size
        return read_discrete_inputs


class ReadHoldingRegisters(functions.ReadHoldingRegisters):
    @classmethod
    def create_from_response_pdu(cls, resp_pdu, req_pdu):
        """ Create instance from response PDU.

        Response PDU is required together with the number of registers read.

        :param resp_pdu: Byte array with request PDU.
        :param quantity: Number of registers to read.
        :return: Instance of :class:`ReadHoldingRegisters`.
        """
        read_holding_registers = cls()
        read_holding_registers.data = unpack_16bits(resp_pdu, req_pdu)
        read_holding_registers.quantity = read_holding_registers.data.size
        return read_holding_registers


class ReadInputRegisters(functions.ReadInputRegisters):
    @classmethod
    def create_from_response_pdu(cls, resp_pdu, req_pdu):
        """ Create instance from response PDU.

        Response PDU is required together with the number of registers read.

        :param resp_pdu: Byte array with request PDU.
        :param quantity: Number of coils read.
        :return: Instance of :class:`ReadCoils`.
        """
        read_input_registers = cls()
        read_input_registers.data = unpack_16bits(resp_pdu, req_pdu)
        read_input_registers.quantity = read_input_registers.data.size
        return read_input_registers


def request_pdu_coils(self):
    if self.starting_address is None or self._values is None:
        raise IllegalDataValueError
    return pack_bits(self.function_code, self.starting_address, self._values)


def request_pdu_registers(self):
    if self.starting_address is None or self._values is None:
        raise IllegalDataValueError
    return pack_16bits(self.function_code, self.starting_address, self._values)


# Patch umodbus to do our biding (which is to handle numpy arrays)
functions.WriteMultipleCoils.request_pdu = property(request_pdu_coils)
functions.WriteMultipleRegisters.request_pdu = property(request_pdu_registers)


function_code_to_function_map = {
    functions.READ_COILS: ReadCoils,
    functions.READ_DISCRETE_INPUTS: ReadDiscreteInputs,
    functions.READ_HOLDING_REGISTERS: ReadHoldingRegisters,
    functions.READ_INPUT_REGISTERS: ReadInputRegisters,
}


functions.function_code_to_function_map.update(function_code_to_function_map)


class _Stream:
    """
    Internal usage only.

    Make sure we have a nice and clean Reader/Writer API compatible with
    asyncio. This makes using curio's `socket.from_stream()` or sockio's TCP()
    straight forward.
    """

    def __init__(self, stream):
        if isinstance(stream, (tuple, list)):
            self.reader, self.writer = stream
        else:
            self.reader = self.writer = stream
        if hasattr(self.reader, "read_exactly"):
            self.readexactly = self.reader.read_exactly
        elif hasattr(self.reader, "readexactly"):
            self.readexactly = self.reader.readexactly
        else:
            self.readexactly = self.reader.read
        if inspect.iscoroutinefunction(self.writer.write):
            self._write_coro = None

            def write(data):
                self._write_coro = self.writer.write(data)

            async def drain():
                assert self._write_coro is not None
                await self._write_coro
                self._write_coro = None
        else:
            write = self.writer.write
            drain = self.writer.drain
        self.write = write
        self.drain = drain
        self.close = self.writer.close


class AsyncClient:
    """Asynchronous modbus client.

    :param stream:
        a tuple of objects implementing <StreamReader, StreamWriter> protocol
        or an object implementing both
    :param protocol:
        either tcp module or rtu module
    """

    protocol = None

    def __init__(self, stream, protocol=None):
        self.stream = _Stream(stream)
        if protocol is not None:
            self.protocol = protocol

    async def _send_message(self, request):
        return await self.protocol._async_send_message(
            request, self.stream, self.stream
        )

    async def read_coils(self, slave_id, starting_address, quantity):
        """Read coils from modbus (function code 01)

        :param slave_id: Slave number.
        :param starting_address: The starting address
        :param quantity: Number of coils to read
        :return: array of bits
        """
        request = self.protocol.read_coils(slave_id, starting_address, quantity)
        return await self._send_message(request)

    async def read_discrete_inputs(self, slave_id, starting_address, quantity):
        """Read discrete inputs from modbus (function code 02).

        :param slave_id: Slave number.
        :param starting_address: The starting address
        :param quantity: Number of discrete inputs to read
        :return: array of bits
        """
        request = self.protocol.read_discrete_inputs(
            slave_id, starting_address, quantity
        )
        return await self._send_message(request)

    async def read_holding_registers(self, slave_id, starting_address, quantity):
        """Read holding registers from modbus (function code 03):

        :param slave_id: Slave number.
        :param starting_address: The starting address
        :param quantity: Number of holding registers to read
        :return: array of (u)int16
        """
        request = self.protocol.read_holding_registers(
            slave_id, starting_address, quantity
        )
        return await self._send_message(request)

    async def read_input_registers(self, slave_id, starting_address, quantity):
        """Read input registers from modbus (function code 04):

        :param slave_id: Slave number.
        :param starting_address: The starting address
        :param quantity: Number of holding registers to read
        :return: array of (u)int16
        """
        request = self.protocol.read_input_registers(
            slave_id, starting_address, quantity
        )
        return await self._send_message(request)

    async def write_coil(self, slave_id, address, value):
        """Write a single coil to modbus (function code 05)

        :param slave_id: Slave number.
        :param address: The coil address
        :param value: value to write (1, 0, True orFalse)
        """
        request = self.protocol.write_single_coil(slave_id, address, value)
        return await self._send_message(request)

    async def write_register(self, slave_id, address, value):
        """Write a single register to modbus (function code 06)

        :param slave_id: Slave number.
        :param address: The register address
        :param value: value to write
        """
        request = self.protocol.protocol.write_single_register(slave_id, address, value)
        return await self._send_message(request)

    async def write_coils(self, slave_id, starting_address, values):
        """Write multiple coils to modbus (function code 15)

        :param slave_id: Slave number.
        :param starting_address: The starting address
        :param value: sequence of values to write
        """
        request = self.protocol.write_multiple_coils(slave_id, starting_address, values)
        return await self._send_message(request)

    async def write_registers(self, slave_id, starting_address, values):
        """Write multiple registers to modbus (function code 16)

        :param slave_id: Slave number.
        :param starting_address: The starting address
        :param value: sequence of values to write
        """
        request = self.protocol.write_multiple_registers(
            slave_id, starting_address, values
        )
        return await self._send_message(request)


class AsyncTCPClient(AsyncClient):
    """Convenience asynchronous modbus client with tcp protocol"""

    protocol = tcp


class AsyncRTUClient(AsyncClient):
    """Convenience asynchronous modbus client with RTU protocol"""

    protocol = rtu


def modbus_for_url(url, conn_options=None):
    """
    Create a modbus for the given url.

    * if url scheme is "tcp" (ex: "tcp://plc.acme.org:502") it returns an
      AsyncTCPClient. If port is not given it defaults to 502. conn_options are
      the same as in `sockio.socket_for_url`.
    * if url scheme is one of "serial", "serial-tcp", "rfc2217" or
      "serial-tango" it returns an AsyncRTUClient. conn_options are
      the same as in `serialio.serial_for_url`.
    """
    import connio

    if conn_options is None:
        conn_options = {}
    conn_options["concurrency"] = "async"
    url_result = urllib.parse.urlparse(url)
    scheme = url_result.scheme
    if scheme == "tcp" and url_result.port is None:
        url += ":502"
    stream = connio.connection_for_url(url, **conn_options)
    if scheme in connio.SOCKET_SCHEMES:
        return AsyncTCPClient(stream)
    elif scheme in connio.SERIAL_SCHEMES:
        return AsyncRTUClient(stream)
    else:
        raise ValueError("unsupported scheme {!r} for {}".format(scheme, url))
