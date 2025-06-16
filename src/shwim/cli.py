import os
import sys
import tty
import termios
import click
import wormhole
from fowl.api import create_coop
from fowl.observer import When
from twisted.internet.defer import ensureDeferred, Deferred
from twisted.internet.task import react
from twisted.internet.protocol import Protocol
from twisted.internet.stdio import StandardIO


@click.command()
@click.option(
    "--mailbox",
    default="ws://relay.magic-wormhole.io:4000/v1",
    help="The Mailbox URL to use",
    required=False,
)
@click.argument("code", default=None, required=False)
def shwim(code, mailbox):
    """
    """
    if code is None:
        react(
            lambda r: ensureDeferred(_host(r, mailbox))
        )
    else:
        react(
            lambda r: ensureDeferred(_guest(r, mailbox, code))
        )


async def _guest(reactor, mailbox, code):
    wh = wormhole.create("meejah.ca/shwim", mailbox, reactor, dilation=True)
    coop = create_coop(reactor, wh)
    wh.set_code(code)
    c = await wh.get_code()
    print("code", c)

    dilated = await coop.dilate()
    print("dilated")
    coop._set_ready()

    x = coop.roost("tty-share")
    print("roosted", x)
    channel = await coop.when_roosted("tty-share")
    print(f"peer connected: {channel}")
    port = channel.connect_port

    await launch_tty_share(reactor, f"http://localhost:{port}/s/local")


class TtyShare(Protocol):

    def __init__(self, reactor):
        self._reactor = reactor
        self._done = When()

    def when_done(self):
        return self._done.when_triggered()

    def connectionMade(self):
        print("connected")
        self.transport.write(b"\n")
        # we need to make some terminal Raw somewhere, how about here?
        self._origstate = termios.tcgetattr(0)
        tty.setraw(0)

    def childDataReceived(self, fd, data):
        #print(fd, data)
        self.std.write(data)
        return
        if fd == 1:
            os.write(1, data)
        elif fd == 2:
            os.write(2, data)
        else:
            print("weird", fd)

    def processEnded(self, why):
        termios.tcsetattr(0, termios.TCSADRAIN, self._origstate)
        self._done.trigger(self._reactor, why)
        print("ended", why)


class WriteTo(Protocol):

    def __init__(self, ttyshare):
        self._ttyshare = ttyshare

    def connectionMade(self):
        pass

    def dataReceived(self, data):
        self._ttyshare.transport.write(data)

    def processEnded(self, why):
        pass


async def launch_tty_share(reactor, *args):
    proto = TtyShare(reactor)
    proc = reactor.spawnProcess(
        proto,
        '/usr/bin/tty-share',
        args=('tty-share',) + args,
        env=os.environ,
        usePTY=True,
    )
    std = StandardIO(WriteTo(proto))
    proto.std = std
    await proto.when_done()


async def _host(reactor, mailbox):
    wh = wormhole.create("meejah.ca/shwim", mailbox, reactor, dilation=True)
    coop = create_coop(reactor, wh)
    wh.allocate_code()
    code = await wh.get_code()
    print(f"magic code: {code}")

    dilated = await coop.dilate()
    print("peer connected")
    coop._set_ready()

    # we're running the server
    channel = await coop.fledge("tty-share", 5666, 5666)
    print(f"running tty-share on: {channel.listen_port}")

    await launch_tty_share(reactor, "--listen", f"localhost:{channel.listen_port}")
