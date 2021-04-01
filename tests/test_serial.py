import anyio
import pytest
import serial as pyserial

from anyio_serial import Serial

pytestmark = pytest.mark.anyio


@pytest.fixture(
    params=[
        pytest.param(("asyncio", {})),
        pytest.param(("trio", {})),
    ]
)
def anyio_backend(request):
    return request.param


@pytest.fixture()
async def serial():
    yield Serial.from_url("loop://")


async def test_receive_size(serial):
    async with serial:
        await serial.send(b"123" * 2)
        recv = await serial.receive_exactly(1)
        assert recv == b"1"
        recv = await serial.receive_exactly(2)
        assert recv == b"23"
        recv = await serial.receive_exactly(3)
        assert recv == b"123"


async def test_receive_eventually(serial):
    """
    Test that all data will be received with receive() eventually
    """
    data = b"." * 100
    recv = b""
    async with serial:
        await serial.send(data)
        while True:
            recv += await serial.receive()
            if not serial.in_waiting:
                break
    assert recv == data


async def test_receive_until(serial):
    """
    Test receive_until()
    """
    async with serial:
        await serial.send(b"1,2,")
        recv = await serial.receive_until(b",", 10)
        assert recv == b"1"
        recv = await serial.receive_until(b",", 10)
        assert recv == b"2"


async def test_iter(serial):
    """
    Test serial can be used as an iterator
    """
    recv = b""
    async with serial:
        await serial.send(b"." * 10)
        async for data in serial:
            recv += data
            if len(recv) == 10:
                break


async def test_close_while_in_use(serial):
    async with serial:
        await serial.send(b"123")
        await serial.aclose()
        with pytest.raises(anyio.EndOfStream):
            await serial.receive()


async def test_closed_read(serial):
    async with serial:
        pass

    with pytest.raises(anyio.EndOfStream):
        await serial.receive()

    with pytest.raises(anyio.IncompleteRead):
        await serial.receive_exactly(1)

    with pytest.raises(anyio.IncompleteRead):
        await serial.receive_until(b".", 1)


async def test_closed_write(serial):
    async with serial:
        pass

    with pytest.raises(anyio.ClosedResourceError):
        await serial.send(b".")


async def test_opened_already():
    async with Serial(pyserial.serial_for_url("loop://")) as serial:
        await serial.send(b".")
        assert await serial.receive() == b"."


async def test_eof(serial):
    with pytest.raises(NotImplementedError):
        await serial.send_eof()


async def test_baudrate(serial):
    async with serial:
        serial.baudrate = 115200
        assert serial.baudrate == 115200
