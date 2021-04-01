# Copyright 2020 Matthias Urlichs
#
# License: MIT

from __future__ import annotations

from functools import partial
from typing import Any, Type, TypeVar

import anyio
import serial as pyserial
from anyio import run_async_from_thread, run_sync_in_worker_thread
from anyio.abc import ByteStream
from anyio.streams.buffered import BufferedByteReceiveStream
from serial.serialutil import PortNotOpenError


T = TypeVar("T", bound="Serial")


class Serial(ByteStream):
    """
    Async ByteStream for pyserial's `Serial` interface.

    This object can be asynchronously iterated upon::

        async with Serial(...) as serial:
            async for data in serial:
                print(data)
                await serial.send(b"I got data from you!")

    Args:
        serial: a pyserial `Serial` instance.
        max_read_size: The maximum size of a read from the serial port in the background thread.
    """

    def __init__(self, serial: pyserial.Serial, max_read_size: int = 1024) -> None:
        self._serial = serial
        self.max_read_size = max_read_size

        self._task_group = anyio.create_task_group()

        self._read_producer, self._read_consumer = anyio.create_memory_object_stream(
            0, item_type=bytes
        )
        self._write_producer, self._write_consumer = anyio.create_memory_object_stream(
            0, item_type=bytes
        )
        self._read_stream = BufferedByteReceiveStream(self._read_consumer)

    @classmethod
    def from_url(cls: Type[T], url: str, **kwargs: Any) -> T:
        """
        Open an `Serial` port with a URL.
        See https://pyserial.readthedocs.io/en/latest/url_handlers.html
        """
        kwargs["do_not_open"] = True
        serial = pyserial.serial_for_url(url, **kwargs)
        return cls(serial)

    async def __aenter__(self) -> Serial:
        if not self._serial.is_open:
            await run_sync_in_worker_thread(self._serial.open)
        await self._task_group.__aenter__()
        await self._task_group.spawn(
            partial(run_sync_in_worker_thread, self._read_worker, cancellable=True)
        )
        await self._task_group.spawn(
            partial(run_sync_in_worker_thread, self._write_worker, cancellable=True)
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()
        await self._task_group.__aexit__(*args)

    async def aclose(self) -> None:
        """
        Close the serial port.
        """
        async with anyio.open_cancel_scope(shield=True):
            await self._read_producer.aclose()
            await self._write_producer.aclose()
            if self._serial.is_open:  # pragma: nocover
                await run_sync_in_worker_thread(self._serial.close)

    def _read(self) -> bytes:
        serial = self._serial
        if not serial.in_waiting:
            # block until data is ready
            return serial.read()  # type: ignore
        # read immediately available data
        size = min(serial.in_waiting, self.max_read_size)
        return serial.read(size)  # type: ignore

    def _read_worker(self) -> None:
        while True:
            try:
                data = self._read()
                run_async_from_thread(self._read_producer.send, data)
            except (PortNotOpenError, anyio.ClosedResourceError):
                return

    def _write_worker(self) -> None:
        while True:
            try:
                data = run_async_from_thread(self._write_consumer.receive)
                self._serial.write(data)
            except (PortNotOpenError, anyio.EndOfStream):
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
        if not self._serial.is_open:
            raise anyio.ClosedResourceError()
        await self._write_producer.send(data)

    async def send_eof(self) -> None:
        raise NotImplementedError("Serial ports don't support sending EOF")

    @property
    def in_waiting(self) -> int:
        """
        Return the number of bytes currently in the input buffer.
        """
        return self._serial.in_waiting  # type: ignore

    @property
    def baudrate(self) -> int:
        """
        The baudrate of the serial port.
        """
        return self._serial.baudrate  # type: ignore

    @baudrate.setter
    def baudrate(self, value: int) -> None:
        self._serial.baudrate = value

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
