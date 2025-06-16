SHwiM
=====

``SHell With Me`` lets a "host" share their terminal with a guest peer on another computer.

This combines the cryptography of Magic Wormhole and the terminal-sharing of [tty-share](https://tty-share.com/) into a secure, peer-to-peer terminal sharing application.


Getting Started
---------------

To install, use ``pip install shwim`` (see longer instructions below).
This should enable you to run ``shwim --help``.

The *Host* computer runs ``shwim`` by itself, producing a ``<magic-code>``.
The *Guest* computer runs ``shwim <magic-code>``.


Both sides 

Once these two things happens, there is a secure tunnel between both computers: one is running a ``tty-share`` server and the other is
