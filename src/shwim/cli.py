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

    wh = wormhole.create("meejah.ca/shwim", mailbox, reactor, dilation=True)  #, on_status_update=print)
    coop = create_coop(reactor, wh)

    wh.set_code(code)
    c = await wh.get_code()

    print("Connecting to peer")
    dilated = await coop.dilate(transit_relay_location=public_relay.TRANSIT_RELAY)

    coop.roost("tty-share")
    channel = await coop.when_roosted("tty-share")
    port = channel.connect_port
    url = f"http://localhost:{port}/s/local/"

    print(f"...connected, launching tty-share: {url}")
    for remaining in range(3, 0, -1):
        try:
            # an up-front delay helps the server tty-share win the
            # race (there's a delay from when you run "tty-share ..."
            # to when it's actually listening)
            await deferLater(reactor, 1.0, lambda: None)
            proto = TtyShare(reactor)
            await launch_tty_share(proto, reactor, url)
            break
        except Exception as e:
            print(f"Failed to launch: {e}")
            if "process ended by signal" in str(e):
                print("Stopping")
                break
            print(f"will try {remaining - 1} more times")
    if 0:
        print(f"tty-share gone, maintaining wormhole")
        await Deferred()


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
    try:
        await proto.when_done()
    finally:
        std.loseConnection()


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
        nonlocal winning_hint
        if isinstance(ds.mailbox.code, ConsumedCode):
            status.set_code("<code consumed>")
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
        tid1 = status.progress.add_task("waiting for peer to use above Magic Code...", total=5)

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

        # could allocate_tcp_port() and pass it twice here to have
        # both sides use the same port
        channel = await coop.fledge("tty-share")
        print(f"running tty-share on: {channel.listen_port}")

    ## actually run tty-share (we've gotten rid of the status display now)
    ro_args = ["-readonly"] if read_only else []

    tty_proto = TtyShare(reactor)
    tty_done = ensureDeferred(
        launch_tty_share(
            tty_proto,
            reactor,
            "--listen", f"localhost:{channel.listen_port}",
            *ro_args,
        )
    )
    # try to get a message to the user when we're re-connecting
    while not tty_done.called:
        await deferLater(reactor, 0.25, lambda: None)
        if winning_hint is None and not tty_done.called:
            print("\nPeer disconnected\nReconnecting...")

            while winning_hint is None:
                await deferLater(reactor, 0.25, lambda: None)
            print(f"Connected via {winning_hint}\n")

    await tty_done
