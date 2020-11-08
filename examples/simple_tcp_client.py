import asyncio

from async_modbus import modbus_for_url


async def main():
    client = modbus_for_url("tcp://localhost:15020")

    values = [1, 0, 1, 1]
    reply = await client.write_multiple_coils(slave_id=1, starting_address=1, values=values)
    assert reply is len(values)
    print(reply)

    reply = await client.read_coils(slave_id=1, starting_address=1, quantity=len(values))
    assert reply == values
    print(reply)

    await client.transport.close()


asyncio.run(main())
