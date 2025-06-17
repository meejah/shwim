

from __future__ import annotations

from typing import Any

from twisted.internet.defer import Failure
from twisted.internet.task import LoopingCall, deferLater, react
from twisted.web.websocket import WebSocketClientEndpoint, WebSocketTransport


class WebSocketClientDemo:
    @classmethod
    def buildProtocol(cls, uri: str) -> WebSocketClientDemo:
        return cls()

    def textMessageReceived(self, data: str) -> None:
        print(f"received text: {data!r}")

    def negotiationStarted(self, transport: WebSocketTransport) -> None:
        self.transport = transport
        print("neg started")

    def negotiationFinished(self) -> None:
        print("neg finished")
        ##self.transport.sendTextMessage("hello, world!")

    def bytesMessageReceived(self, data: bytes) -> None:
        print("got message", data)

    def connectionLost(self, reason: Failure) -> None:
        print("connection lost", reason)

    def pongReceived(self, payload: bytes) -> None:
        print("pong", payload)


async def main(reactor: Any) -> None:
    endpoint = WebSocketClientEndpoint.new(
        reactor, "ws://localhost:8000/s/ws
    )
    print("connecting...")
    await endpoint.connect(WebSocketClientDemo)
    print("connected!")
    await deferLater(reactor, 10)


if __name__ == "__main__":
    react(main)
