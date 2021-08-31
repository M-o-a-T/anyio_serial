# Copyright 2020 Matthias Urlichs
#
# License: MIT

from contextlib import asynccontextmanager

import anyio.abc
import serial
from anyio import BrokenResourceError, ClosedResourceError
from serial import SerialException


class Serial(anyio.abc.ByteStream):
    _port = None

    def __init__(self, *a, **kw):
        self._a = a
        self._kw = kw
        self._send_lock = anyio.create_lock()
        self._receive_lock = anyio.create_lock()

    async def __aenter__(self):
        self._ctx = self._gen_ctx()
        return await self._ctx.__aenter__()

    async def __aexit__(self, *tb):
        return await self._ctx.__aexit__(*tb)


    @asynccontextmanager
    async def _gen_ctx(self):
        await anyio.run_sync_in_worker_thread(self._open)
        try:
            yield self
        finally:
            await self.aclose()

    async def aclose(self):
        port, self._port = self._port, None
        if port is None:
            return
        await anyio.run_sync_in_worker_thread(self._close, port)


    def _open(self):
        self._port = serial.Serial(*self._a, **self._kw)

    def _close(self, port):
        port.close()

    async def send_eof(self):
        raise NotImplementedError("Serial ports don't support sending EOF")

    async def receive(self, max_bytes=4096):
        if not self._port.isOpen():
            raise ClosedResourceError

        async with self._receive_lock:
            try:
                return await anyio.run_sync_in_worker_thread(self._read, max_bytes,
                                                             cancellable=True)
            except (OSError, SerialException) as exc:
                raise BrokenResourceError from exc

    async def send(self, bytes):
        if not self._port.isOpen():
            raise ClosedResourceError

        async with self._send_lock:
            try:
                return await anyio.run_sync_in_worker_thread(self._port.write, bytes,
                                                             cancellable=True)
            except (OSError, SerialException) as exc:
                raise BrokenResourceError from exc

    def _read(self, max_bytes):
        p = self._port
        if not p.in_waiting:
            return p.read()
        if p.in_waiting < max_bytes:
            max_bytes = p.in_waiting
        return p.read(max_bytes)

    @property
    def cd(self):
        return self._port.cd

    @property
    def cts(self):
        return self._port.cts

    @property
    def dsr(self):
        return self._port.dsr

    @property
    def ri(self):
        return self._port.ri

    @property
    def baudrate(self):
        return self._port.baudrate

    @baudrate.setter
    def baudrate(self, val):
        self._port.baudrate = val

    @property
    def bytesize(self):
        return self._port.bytesize

    @bytesize.setter
    def bytesize(self, val):
        self._port.bytesize = val

    @property
    def parity(self):
        return self._port.parity

    @parity.setter
    def parity(self, val):
        self._port.parity = val

    @property
    def stopbits(self):
        return self._port.stopbits

    @stopbits.setter
    def stopbits(self, val):
        self._port.stopbits = val

    @property
    def dtr(self):
        return self._port.dtr

    @dtr.setter
    def dtr(self, val):
        self._port.dtr = val

    @property
    def rts(self):
        return self._port.rts

    @rts.setter
    def rts(self, val):
        self._port.rts = val

    @property
    def break_condition(self):
        return self._port.break_condition

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

