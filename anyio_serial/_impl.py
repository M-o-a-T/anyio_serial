# Copyright 2020 Matthias Urlichs
#
# License: MIT

import anyio
import serial

from contextlib import asynccontextmanager

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
        pass

    async def receive(self, max_bytes=4096):
        async with self._receive_lock:
            return await anyio.run_sync_in_worker_thread(self._read, max_bytes, cancellable=True)

    async def send(self, bytes):
        async with self._send_lock:
            return await anyio.run_sync_in_worker_thread(self._port.write, bytes, cancellable=True)

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
    def dts(self):
        return self._port.dts

    @property
    def dsr(self):
        return self._port.dsr

    @property
    def ri(self):
        return self._port.ri

