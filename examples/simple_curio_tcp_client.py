import curio
from async_modbus import AsyncTCPClient


async def main():
    sock = await curio.open_connection("0", 15020)
    stream = sock.as_stream()
    client = AsyncTCPClient(stream)
    values = [1, 0, 1, 1]
    reply = await client.write_multiple_coils(slave_id=1, starting_address=1, values=values)
    assert reply is len(values)
    print(reply)

    reply = await client.read_coils(slave_id=1, starting_address=1, quantity=len(values))
    assert reply == values
    print(reply)
    await sock.close()

curio.run(main)
