import os
import sys
import tty
import pty
import fcntl
import array
import termios
import click
import signal
import shutil
import wormhole
import attrs
from wormhole.cli import public_relay
from wormhole._status import ConsumedCode, ConnectedPeer, ReconnectingPeer
from fowl.api import create_coop
from fowl._proto import create_fowl
from fowl.observer import When
from fowl.tcp import allocate_tcp_port
from twisted.internet.defer import ensureDeferred, Deferred
from twisted.internet.task import react, deferLater
from twisted.internet.protocol import Protocol
from twisted.internet.stdio import StandardIO
from twisted.internet.error import ProcessDone

from .status import WormholeStatus


@click.command()
@click.option(
    "--mailbox",
    default="ws://relay.magic-wormhole.io:4000/v1",
    help="The Mailbox URL to use",
    required=False,
)
@click.option(
    "--read-only",
    "-R",
    help="Peers cannot provide input to the terminal",
    flag_value="read_only",
    default=False,
)
@click.argument("code", default=None, required=False)
def shwim(code, mailbox, read_only):
    """
    SHell WIth Me allows you to share you shell with another computer.

    This uses the great tty-share under the hood, except that it never
    uses tty-share's public server -- all communications are
    end-to-end encrypted over Magic Wormhole.
    """
    if code is None:
        react(
            lambda r: ensureDeferred(_host(r, mailbox, read_only))
        )
    else:
        react(
            lambda r: ensureDeferred(_guest(r, mailbox, code))
        )


async def _guest(reactor, mailbox, code):
    """
    Join another person's terminal via tty-share
    """

    def status(st):
        print("status", st)
    wh = wormhole.create("meejah.ca/shwim", mailbox, reactor, dilation=True, on_status_update=status)
    coop = create_coop(reactor, wh)

    wh.set_code(code)
    c = await wh.get_code()

    print("Connecting to peer")
    dilated = await coop.dilate(transit_relay_location=public_relay.TRANSIT_RELAY)

    x = coop.roost("tty-share")
    print(f"roosting {x}")
    channel = await coop.when_roosted("tty-share")
    port = channel.connect_port
    url = f"http://localhost:{port}/s/local/"

    print(f"...connected, launching tty-share: {url}")
    await launch_tty_share(reactor, url)


class TtyShare(Protocol):
    """
    Speak stdin/stdout to a tty-share

    This also handles synchronizing terminal sizes between our
    controlling terminal and the tty-share subprocess via SIGWINCH
    """

    def __init__(self, reactor):
        self._reactor = reactor
        self._done = When()

    def when_done(self):
        return self._done.when_triggered()

    def connectionMade(self):
        self.transport.write(b"\n")
        # we need to make some terminal Raw somewhere, how about here?
        self._origstate = termios.tcgetattr(0)
        tty.setraw(0)
        self._sync_terminal_size()

    def _sync_terminal_size(self):
        # we should also sync terminal size on SIGWINCH I believe?
        size = termios.tcgetwinsize(0)
        termios.tcsetwinsize(self.transport.fileno(), size)

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
        if isinstance(why.value, ProcessDone):
            why = None
        self._done.trigger(self._reactor, why)


class WriteTo(Protocol):
    """
    Write any incoming data to the attached tty-share
    """

    def __init__(self, ttyshare):
        self._ttyshare = ttyshare

    def connectionMade(self):
        pass

    def dataReceived(self, data):
        self._ttyshare.transport.write(data)

    def processEnded(self, why):
        pass


async def launch_tty_share(reactor, *args):
    """
    run a tty-share subprocess
    """
    proto = TtyShare(reactor)
    # print(f"RUN: {args}")
    proc = reactor.spawnProcess(
        proto,
        shutil.which("tty-share"),
        args=('tty-share',) + args,
        env=os.environ,
        usePTY=True,
    )


    # respond to re-sizes more-or-less properly?
    def forward_winch(sig, frame):
        proto._sync_terminal_size()
    signal.signal(signal.SIGWINCH, forward_winch)

    std = StandardIO(WriteTo(proto))
    proto.std = std

    await proto.when_done()


async def _host(reactor, mailbox, read_only):
    """
    Run the host side interaction, launching a tty-share
    subprocess and basically turning over 'this' terminal to it.
    """

    from rich.live import Live
    status = WormholeStatus()

    live = Live(
        get_renderable=lambda: status,
        # we can set screen=True here but I kind of prefer seeing the
        # "leftover" status information above?
        #screen=True,
    )

    winning_hint = None

    def on_status(ds):
        # print(ds)
        nonlocal winning_hint
        if isinstance(ds.mailbox.code, ConsumedCode):
            status.set_code("<consumed>")
        if isinstance(ds.peer_connection, ConnectedPeer):
            winning_hint = ds.peer_connection.hint_description
        elif isinstance(ds.peer_connection, ReconnectingPeer):
            print("Disconnected?")
            winning_hint = None

    with live:
        tid0 = status.progress.add_task(f"Connecting [b]{mailbox}", total=1)
        wh = wormhole.create("meejah.ca/shwim", mailbox, reactor, dilation=True)
        coop = create_coop(reactor, wh)
        wh.allocate_code()
        code = await wh.get_code()
        status.progress.update(tid0, completed=True, description=f"Connected [b]{mailbox}")
        status.set_code(code)
        tid1 = status.progress.add_task("waiting for peer...", total=5)

        def on_status(st):
            status.progress.update(tid1, advance=1)
        dilated_d = ensureDeferred(coop.dilate(on_status_update=on_status))

        while not dilated_d.called:
            d = Deferred()
            reactor.callLater(.25, lambda: d.callback(None))
            await d

        dilated = await dilated_d
        print(f"host: dilated.")
        status.progress.update(tid1, completed=5)
        status.progress.update(
            tid1,
            completed=True,
            description=f"Peer connected: {winning_hint}",
        )

        # we're running the server -- we want a random port, but also we
        # _NEED_ to have the same port in use on the far side, for boring
        # HTTP reasons (the "same origin" check includes the port, so
        # "localhost:1234" is not the same origin as "localhost:<other port>")
        random_port = allocate_tcp_port()
        # race between here, and when we acutally listen...
        channel = await coop.fledge("tty-share", random_port, random_port)
        print(f"running tty-share on: {channel.listen_port}")

    ## actually run tty-share (we've gotten rid of the status display now)
    ro_args = ["-readonly"] if read_only else []

    tty_done = ensureDeferred(
        launch_tty_share(
            reactor,
            "--listen", f"localhost:{channel.listen_port}",
            *ro_args,
        )
    )
    while not tty_done.called:
        await deferLater(reactor, 0.25, lambda: None)
        if winning_hint is None:
            print("Peer disconnected")
            status.progress.remove_task(tid1)
            tid2 = status.progress.add_task("Reconnecting to Peer...", total=1)
            with live:
                while winning_hint is None:
                    await deferLater(reactor, 0.25, lambda: None)
            status.progress.update(
                tid2,
                completed=True,
                description=f"Peer connected: {winning_hint}",
            )

    await tty_done
