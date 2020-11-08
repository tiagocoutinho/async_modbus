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

import numpy


__author__ = """Tiago Coutinho"""
__email__ = "coutinhotiago@gmail.com"
__version__ = "0.1.0"


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


class ReadHoldingRegisters(functions.ReadHoldingRegisters):
    @classmethod
    def create_from_response_pdu(cls, resp_pdu, req_pdu):
        """ Create instance from response PDU.

        Response PDU is required together with the number of registers read.

        :param resp_pdu: Byte array with request PDU.
        :param quantity: Number of coils read.
        :return: Instance of :class:`ReadHoldingRegisters`.
        """
        read_holding_registers = cls()
        read_holding_registers.quantity = struct.unpack(">H", req_pdu[-2:])[0]
        read_holding_registers.byte_count = struct.unpack(">B", resp_pdu[1:2])[0]

        dtype = ">{}2".format("i" if conf.SIGNED_VALUES else "u")

        read_holding_registers.data = numpy.frombuffer(
            resp_pdu, dtype=dtype, count=read_holding_registers.quantity, offset=2
        )

        return read_holding_registers


functions.function_code_to_function_map[
    functions.READ_HOLDING_REGISTERS
] = ReadHoldingRegisters


class _Transport:
    """
    Internal usage only.

    Make sure we have a nice and clean Reader/Writer API compatible with asyncio
    """
    def __init__(self, transport):
        if isinstance(transport, (tuple, list)):
            self.reader, self.writer = transport
        else:
            self.reader = self.writer = transport
        if hasattr(self.reader, 'read_exactly'):
            self.readexactly = self.reader.read_exactly
        else:
            self.readexactly = self.reader.readexactly
        if inspect.iscoroutinefunction(self.writer.write):
            self._data = None
            def write(data):
                self._data = data
            async def drain():
                assert self._data is not None
                await self.writer.write(self._data)
                self._data = None
        else:
            write = self.writer.write
            drain = self.writer.drain
        self.write = write
        self.drain = drain
        self.close = self.writer.close


class AsyncClient:
    """Asynchronous modbus client.

    :param transport:
        a tuple of objects implementing <StreamReader, StreamWriter> protocol
        or an object implementing both
    :param protocol:
        either tcp module or rtu module
    """

    protocol = None

    def __init__(self, transport, protocol=None):
        self.transport = _Transport(transport)
        if protocol is not None:
            self.protocol = protocol

    async def _send_message(self, request):
        return await self.protocol._async_send_message(
            request, self.transport, self.transport
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

    async def write_single_coil(self, slave_id, address, value):
        """Write a single coil to modbus (function code 05)

        :param slave_id: Slave number.
        :param address: The coil address
        :param value: value to write (1, 0, True orFalse)
        """
        request = self.protocol.write_single_coil(slave_id, address, value)
        return await self._send_message(request)

    async def write_single_register(self, slave_id, address, value):
        """Write a single registers to modbus (function code 06)

        :param slave_id: Slave number.
        :param address: The register address
        :param value: value to write
        """
        request = self.protocol.protocol.write_single_register(slave_id, address, value)
        return await self._send_message(request)

    async def write_multiple_coils(self, slave_id, starting_address, values):
        """Write multiple registers to modbus (function code 06)

        :param slave_id: Slave number.
        :param starting_address: The starting address
        :param value: sequence of values to write
        """
        request = self.protocol.write_multiple_coils(slave_id, starting_address, values)
        return await self._send_message(request)

    async def write_multiple_registers(self, slave_id, starting_address, values):
        """Write multiple registers to modbus (function code 06)

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
    transport = connio.connection_for_url(url, **conn_options)
    if scheme in connio.SOCKET_SCHEMES:
        return AsyncTCPClient(transport)
    elif scheme in connio.SERIAL_SCHEMES:
        return AsyncRTUClient(transport)
    else:
        raise ValueError("unsupported scheme {!r} for {}".format(scheme, url))
