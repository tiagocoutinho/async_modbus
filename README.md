# Async ModBus

[![Async Modbus](https://img.shields.io/pypi/v/async_modbus.svg)](https://pypi.python.org/pypi/async_modbus)
[![Python Versions](https://img.shields.io/pypi/pyversions/async_modbus.svg)](https://pypi.python.org/pypi/async_modbus)

Asynchronous (as in python async/await) modbus python 3 client library.
A thin layer on on top of the venerable
[umodbus](https://github.com/AdvancedClimateSystems/uModbus) library providing
an object oriented client API.

async_modbus is async library agnostic. You should be able to use it with
[asyncio](https://docs.python.org/3/library/asyncio.html),
[curio](https://curio.rtfd.io), [trio](https://trio.rtfd.io) or
[anyio](https://anyio.rtfd.io).

It expects an object with the same interface as
[StreamReader](https://docs.python.org/3/library/asyncio-stream.html#streamreader)
and
[StreamWriter](https://docs.python.org/3/library/asyncio-stream.html#streamwriter)
so you may need to write a thin wrapper if you are not using asyncio.
The examples below show how to use it with curio.

Note: the `modbus_for_url()` relies on the
[connio](https://github.com/tiagocoutinho/connio) library which relies on
the asyncio event loop so you it's usage is limited to asyncio applications.


## Why another modbus library?

This library is not a re-implementation of the ModBus communication protocol.
You can view it instead as a complement to the
[umodbus](https://github.com/AdvancedClimateSystems/uModbus) library.

Here is what async_modbus provides on top of umodbus:

* Simple yet powerful object oriented API
* Convenient `modbus_for_url()` helper function. Type an URL and you're ready
  to go.
* when appropriate, [numpy](https://numpy.org) arrays are used. It's usage not
  only reduces the memory footprint and increases speed, but also makes it easy
  for users to efficiently reformat data.
* Compatible with the [connio](https://github.com/tiagocoutinho/connio),
  [sockio](https://github.com/tiagocoutinho/sockio) and
  [serialio](https://github.com/tiagocoutinho/serialio) libraries which provide
  transparent socket re-connection among other features.


## Installation

From within your favorite python environment type:

`$ pip install async_modbus`

## Library

The core of the async_modbus library consists of a `modbus_for_url()` function
and the two classes `AsyncTCPClient` and `AsyncRTUClient`.

Here are some examples:

### asyncio examples

*simple TCP client*

```python
import asyncio

import numpy

from async_modbus import modbus_for_url


async def main():

    client = modbus_for_url("tcp://localhost:15020")

    values = numpy.array([1, 0, 1, 1])  # would also work with list<bool or int>
    reply = await client.write_coils(slave_id=1, starting_address=1, values=values)
    assert reply is len(values)

    reply = await client.read_coils(slave_id=1, starting_address=1, quantity=len(values))
    assert (reply == values).all()


asyncio.run(main())
```

*RTU over remove serial line using RFC2217*

```python
import asyncio

from async_modbus import modbus_for_url


async def main():

    client = modbus_for_url("rfc2217://moxa.acme.org:6610")

    values = [1, 0, 1, 1]
    reply = await client.write_coils(slave_id=1, starting_address=1, values=values)
    assert reply is len(values)

    reply = await client.read_discrete_inputs(slave_id=1, starting_address=1, quantity=len(values))
    assert (reply == values).all()


asyncio.run(main())
```

*asyncio TCP streams*

```python
import asyncio

import numpy

from async_modbus import AsyncTCPClient


async def main():

    reader, writer = await asyncio.open_connection('localhost', 15020)
    client = AsyncTCPClient((reader, writer))

    values = numpy.array([0, 2**15 - 1, 10, 3, 32766])
    reply = await client.write_registers(slave_id=1, starting_address=1, values=values)
    assert reply is len(values)

    reply = await client.read_holding_registers(slave_id=1, starting_address=1, quantity=len(values))
    assert (reply == values).all()

    writer.close()
    await writer.wait_closed()


asyncio.run(main())
```

*async serial line RTU using remote raw TCP*

```python
import asyncio

import numpy

from async_modbus import AsyncRTUClient
from serial_asyncio import open_serial_connection


async def main():

    reader, writer = await open_serial_connection(url="socket://moxa.acme.org:6610")
    client = AsyncRTUClient((reader, writer))

    values = [0, 2**15 - 1, 10, 3, 32766]
    reply = await client.write_registers(slave_id=1, starting_address=1, values=values)
    assert reply is len(values)

    reply = await client.read_input_registers(slave_id=1, starting_address=1, quantity=len(values))
    assert (reply == values).all()

    writer.close()
    await writer.wait_closed()


asyncio.run(main())
```

### curio examples

**curio TCP streams**

```python
import curio
from async_modbus import AsyncTCPClient


async def main():

    sock = await curio.open_connection("0", 15020)
    client = AsyncTCPClient(sock.as_stream())

    values = [1, 0, 1, 1]
    reply = await client.write_coils(slave_id=1, starting_address=1, values=values)
    assert reply is len(values)

    reply = await client.read_coils(slave_id=1, starting_address=1, quantity=len(values))
    assert (reply == values).all()

    await sock.close()
```


## Credits

### Development Lead

* Tiago Coutinho <coutinhotiago@gmail.com>

### Contributors

None yet. Why not be the first?

### Special thanks to

* [umodbus](https://github.com/AdvancedClimateSystems/uModbus)
* [numpy](https://numpy.org)
