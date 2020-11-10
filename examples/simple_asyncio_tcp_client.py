import asyncio
from async_modbus import AsyncTCPClient


async def main():
    reader, writer = await asyncio.open_connection("0", 15020)
    client = AsyncTCPClient((reader, writer))
    values = [1, 0, 1, 1]
    reply = await client.write_coils(slave_id=1, starting_address=1, values=values)
    assert reply is len(values)
    print(reply)

    reply = await client.read_coils(slave_id=1, starting_address=1, quantity=len(values))
    assert reply == values
    print(reply)

    writer.close()
    await writer.wait_closed()

asyncio.run(main())
