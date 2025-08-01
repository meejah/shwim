ShWiM
=====

``SHell WIth Me`` lets a “host” share their terminal with a “guest” peer
on another computer.

This combines the cryptography of `Magic Wormhole
<http://magic-wormhole.io>`_ (via `Fowl
<https://github.com/meejah/fowl>`_) and the terminal-sharing of
`tty-share <https://tty-share.com/>`_ into a secure, end-to-end
encrypted, **peer-to-peer terminal sharing application**.

.. image:: media/logo-shell-256.png
    :width: 256px
    :align: right
    :alt: the ShWiM logo, the chicken head from Fowl's logo peeking out of a conch-looking shell



Getting Started
---------------

To install, use ``pip install shwim`` (see longer instructions below).
This should enable you to run ``shwim --help``.

The *Host* computer runs ``shwim`` by itself, producing a
``<magic-code>``. The *Guest* computer runs ``shwim <magic-code>``.

You are now sharing a single terminal running on “host”. **Beware**: the
guest can type, run commands, etc. so only do this with humans you would
hand your local keyboard over to.


Slightly Longer Explanation
---------------------------

Once thetwo things happen (i.e. “shwim” on the host and “shwim ” on the
guest), there is a secure tunnel between both computers. The host will
decide a random port and run ``tty-share`` as a server; the guest will
run ``tty-share`` as a client.

On both computers, ``tty-share`` will be running as a subprocess with
correct options to do networking via Magic Wormhole only. All raw-mode
terminal I/O is forwarded to this ``tty-share`` process so things like
curses etc work as expected.

Once either side exits, the networking forwarding is done – there is no
long-term credential sharing or any other network set preserved or
altered on the “host” nor “guest” computers.
