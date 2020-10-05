============
anyio_serial
============

A small Python wrapper that combines [anyio](https://anyio.readthedocs.io)
and [pySerial](https://pypi.org/project/pyserial/).

Implementation detail: This library is using too many short-lived threads.
Yes this should be improved.

Quick start
===========

A simple serial port reader
+++++++++++++++++++++++++++

::
   import anyio
   from anyio_serial import Serial


   async def read_and_print(port: Serial):
      while True:
         print((await port.read).decode(errors='ignore'), end='', flush=True)

   async def main():
      async with Serial(port='COM1') as port:
         await read_and_print(port)

   anyio.run(main)

API
===

Serial
++++++

::
   from anyio_serial import Serial

Constructor
-----------

::
   async with Serial(...) as port:  # same options as serial.Serial
      ...
      # use "port" like any other anyio ByteStream

Attributes
----------

The states of the serial status lines ``cd``, ``cts``, ``dsr`` and ``ri``
are supported.

