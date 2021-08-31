============
anyio_serial
============

A small Python wrapper that combines `anyio <https://anyio.readthedocs.io>`_
and `pySerial <https://pypi.org/project/pyserial/>`_.

Implementation detail: This library is using too many short-lived threads.
Yes this should be improved.

Quick start
===========

A simple serial port reader
+++++++++++++++++++++++++++

anyio_serial is a reasonably intuitive mash-up of `pySerial`_ and anyio's
``Stream``::

   import anyio
   from anyio_serial import Serial
   
   async def main():
      async with Serial(port='COM1') as port:
         while True:
            print((await port.receive()).decode(errors='ignore'), end='', flush=True)
   
   anyio.run(main)

API
===

anyio_serial's interface is really simple::

   from anyio_serial import Serial
   
   async with Serial(...) as port:  # same options as serial.Serial
      ...
      # use "port" like any other anyio ByteStream

Attributes
++++++++++

The states of the serial status lines ``cd``, ``cts``, ``dsr`` and ``ri``
are supported.

