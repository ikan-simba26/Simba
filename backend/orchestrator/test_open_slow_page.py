"""A page that never says it has loaded does not hang the run (2026-11-16).

PakWheels, one of the cluttered Pakistani websites added to the list on
2026-11-16, never fires its `load` event inside 30 seconds (ads, trackers).
`page.goto` raised, nothing caught it, the websocket handler died, and the
overlay stayed on "Give me a moment." with no word of why, for good — seen in
the real window: "open goal on pakwheels.com", then seven minutes of nothing.

Two cases, both against a server on this machine that holds its connection
open: a page whose HTML has arrived but whose load never completes (go on, as
the person would: it is there to read), and a server that never answers (say
so in plain words, change nothing, and end).
"""

import asyncio
import socket
import threading
import time

from playwright.async_api import async_playwright

from backend.orchestrator import loop, voice
from backend.orchestrator.loop import _Run
from backend.orchestrator.test_verification import FakeConnection


class Server:
    """Answers with a page and then never finishes the response, or says nothing."""

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.port = self.sock.getsockname()[1]
        self.clients: list[socket.socket] = []
        threading.Thread(target=self.run, daemon=True).start()

    def run(self) -> None:
        while True:
            try:
                client, _ = self.sock.accept()
            except OSError:
                return
            self.clients.append(client)
            if self.mode == "partial":
                client.recv(4096)
                body = b"<html><body><h1>Cars for sale</h1>"
                client.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n"
                               b"Transfer-Encoding: chunked\r\n\r\n"
                               + hex(len(body))[2:].encode() + b"\r\n" + body + b"\r\n")
                # ... and never the end: `load` does not fire.

    def close(self) -> None:
        self.sock.close()
        for client in self.clients:
            client.close()


def opened(mode: str) -> tuple[FakeConnection, str, float]:
    server = Server(mode)
    connection = FakeConnection()
    url = f"http://127.0.0.1:{server.port}/"

    async def go() -> tuple[str, float]:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                page = await browser.new_page()
                run = _Run(page, connection, None, None)
                started = time.monotonic()
                await run.open("Find a used car", 3, url)
                return page.url, time.monotonic() - started
            finally:
                await browser.close()

    try:
        final_url, took = asyncio.run(go())
    finally:
        server.close()
    return connection, final_url, took


def test_a_page_that_never_finishes_loading_is_gone_on_with(monkeypatch) -> None:
    monkeypatch.setattr(loop, "OPEN_TIMEOUT_MS", 2000)
    connection, url, took = opened("partial")

    assert url.startswith("http://127.0.0.1"), url
    assert "task.failed" not in connection.types(), connection.types()
    assert took < 15


def test_a_page_that_never_answers_ends_the_run_in_plain_words(monkeypatch) -> None:
    monkeypatch.setattr(loop, "OPEN_TIMEOUT_MS", 2000)
    connection, _, took = opened("silent")

    failed = connection.payload_of("task.failed")
    assert failed["reason"] == voice.COULD_NOT_OPEN
    assert failed["recoverable"] is True
    assert took < 15
