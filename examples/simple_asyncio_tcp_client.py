import asyncio

import numpy

from async_modbus import AsyncTCPClient


async def main():
    reader, writer = await asyncio.open_connection("0", 15020)
    client = AsyncTCPClient((reader, writer))

    # bits

    values = numpy.array([1, 0, 1, 1, 0, 0, 1, 0, 1])
    reply = await client.write_coils(slave_id=1, starting_address=1, values=values)
    assert reply is len(values)
    print(reply)

    reply = await client.read_coils(
        slave_id=1, starting_address=1, quantity=len(values)
    )
    assert (reply == values).all()
    print(reply)

    reply = await client.read_discrete_inputs(
        slave_id=1, starting_address=1, quantity=len(values)
    )
    assert (reply == values).all()
    print(reply)

    # int16

    values = numpy.array([0, 2**15 - 1, 10, 3, 32766])
    reply = await client.write_registers(slave_id=1, starting_address=1, values=values)
    assert reply is len(values)
    print(reply)

    reply = await client.read_holding_registers(
        slave_id=1, starting_address=1, quantity=len(values)
    )
    assert (reply == values).all()
    print(reply)

    reply = await client.read_input_registers(
        slave_id=1, starting_address=1, quantity=len(values)
    )
    assert (reply == values).all()
    print(reply)

    writer.close()
    await writer.wait_closed()


asyncio.run(main())
