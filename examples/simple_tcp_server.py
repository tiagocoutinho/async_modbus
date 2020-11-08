#!/usr/bin/env python
# scripts/examples/simple_data_store.py
import logging
from socketserver import TCPServer
from collections import defaultdict

from umodbus import log, conf
from umodbus.server.tcp import RequestHandler, get_server
from umodbus.utils import log_to_stream

# Add stream handler to logger 'uModbus'.
#log_to_stream(level=logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)

# A very simple data store which maps addresses against their values.
data_store = defaultdict(int)

hr_data_store = defaultdict(int)

# Enable values to be signed (default is False).
conf.SIGNED_VALUES = True

TCPServer.allow_reuse_address = True
app = get_server(TCPServer, ('localhost', 15020), RequestHandler)


@app.route(slave_ids=[1], function_codes=[1, 2], addresses=list(range(0, 10)))
def read_data_store(slave_id, function_code, address):
    """" Return value of address. """
    return data_store[address]


# Read Holding Registers
@app.route(slave_ids=[1], function_codes=[3], addresses=list(range(0, 1000)))
def read_data_store(slave_id, function_code, address):
    """" Set value for address. """
    return hr_data_store[address] + 10


# Write Single Coil and Write Multiple Coils.
@app.route(slave_ids=[1], function_codes=[5, 15], addresses=list(range(0, 10)))
def write_data_store(slave_id, function_code, address, value):
    """" Set value for address. """
    data_store[address] = value




if __name__ == '__main__':
    try:
        app.serve_forever()
    finally:
        app.shutdown()
        app.server_close()
