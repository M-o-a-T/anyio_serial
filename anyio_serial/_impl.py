# Copyright 2020 Matthias Urlichs
#
# License: MIT

from contextlib import asynccontextmanager

import anyio.abc
import serial
from anyio import BrokenResourceError, ClosedResourceError
from anyio.abc import ByteStream
from anyio.streams.buffered import BufferedByteReceiveStream
from serial import SerialException
from serial.serialutil import PortNotOpenError  # type: ignore
from functools import partial


class Serial(anyio.abc.ByteStream):
    _port = None

    def __init__(self, *a, max_read_size=1024, **kw):
        self._a = a
        self._kw = kw
        if not a and not kw:
            raise RuntimeError("No arguments given")
        self.max_read_size = max_read_size

        self._read_producer, self._read_consumer = anyio.create_memory_object_stream(
            0, item_type=bytes
        )
        self._write_producer, self._write_consumer = anyio.create_memory_object_stream(
            0, item_type=bytes
        )
        self._read_stream = BufferedByteReceiveStream(self._read_consumer)


    async def __aenter__(self):
        self._ctx = self._gen_ctx()
        return await self._ctx.__aenter__()

    async def __aexit__(self, *tb):
        return await self._ctx.__aexit__(*tb)


    @asynccontextmanager
    async def _gen_ctx(self):
        if self._port is not None:
            yield self
            return
        await anyio.to_thread.run_sync(self._open)
        if self._port is None:
            raise RuntimeError("Port not opened: %r %r", self._a, self._kw)
        async with anyio.create_task_group() as tg:
            tg.start_soon(partial(anyio.to_thread.run_sync, self._read_worker, cancellable=True))
            tg.start_soon(partial(anyio.to_thread.run_sync, self._write_worker, cancellable=True))
            try:
                yield self
            finally:
                tg.cancel_scope.cancel()
                with anyio.fail_after(0.2, shield=True):
                    await self.aclose()

    async def aclose(self):
        port, self._port = self._port, None
        if port is None:
            return
        await anyio.to_thread.run_sync(self._close, port)


    def _open(self):
        self._port = serial.Serial(*self._a, **self._kw)

    def _close(self, port):
        port.close()

    async def send_eof(self):
        raise NotImplementedError("Serial ports don't support sending EOF")

    def _read(self):
        p = self._port
        if p is None:
            raise ClosedResourceError
        try:
            if not p.in_waiting:
                return p.read()
        except TypeError:
            raise ClosedResourceError from None  # closed under us
        return p.read(min(p.in_waiting, self.max_read_size))

    def _read_worker(self) -> None:
        while True:
            try:
                data = self._read()
                anyio.from_thread.run(self._read_producer.send, data)
            except (PortNotOpenError, anyio.ClosedResourceError):
                return

    def _write_worker(self) -> None:
        p = self._port
        while True:
            try:
                data = anyio.from_thread.run(self._write_consumer.receive)
                p.write(data)
            except (PortNotOpenError, anyio.EndOfStream, TypeError):
                return

    async def receive(self, max_bytes: int = 4096) -> bytes:
        """
        Read at most max_bytes bytes from the serial port.
        """
        return await self._read_stream.receive(max_bytes=max_bytes)

    async def receive_exactly(self, nbytes: int) -> bytes:
        """
        Read exactly the given amount of bytes from the serial port.
        """
        return await self._read_stream.receive_exactly(nbytes)

    async def receive_until(self, delimiter: bytes, max_bytes: int) -> bytes:
        """
        Read from the serial port until the `delimiter` is found or `max_bytes` have been read.
        """
        return await self._read_stream.receive_until(delimiter, max_bytes)

    async def send(self, data: bytes) -> None:
        """
        Write data to the serial port.
        """
        if not self._port.is_open:
            raise anyio.ClosedResourceError()
        await self._write_producer.send(data)

    @property
    def cd(self):
        return self._port.cd if self._port else None

    @property
    def cts(self):
        return self._port.cts if self._port else None

    @property
    def dsr(self):
        return self._port.dsr if self._port else None

    @property
    def ri(self):
        return self._port.ri if self._port else None

    @property
    def baudrate(self):
        return self._port.baudrate if self._port else None

    @baudrate.setter
    def baudrate(self, val):
        self._port.baudrate = val

    @property
    def bytesize(self):
        return self._port.bytesize if self._port else None

    @bytesize.setter
    def bytesize(self, val):
        self._port.bytesize = val

    @property
    def parity(self):
        return self._port.parity if self._port else None

    @parity.setter
    def parity(self, val):
        self._port.parity = val

    @property
    def stopbits(self):
        return self._port.stopbits if self._port else None

    @stopbits.setter
    def stopbits(self, val):
        self._port.stopbits = val

    @property
    def dtr(self):
        return self._port.dtr if self._port else None

    @dtr.setter
    def dtr(self, val):
        self._port.dtr = val

    @property
    def rts(self):
        return self._port.rts if self._port else None

    @rts.setter
    def rts(self, val):
        self._port.rts = val

    @property
    def break_condition(self):
        return self._port.break_condition if self._port else None

    @break_condition.setter
    def break_condition(self, val):
        self._port.break_condition = val

    async def send_break(self, duration=0.25):
        """\ 
        Send break condition. Timed, returns to idle state after given
        duration.
        """
        self.break_condition = True
        await anyio.sleep(duration)
        self.break_condition = False  

