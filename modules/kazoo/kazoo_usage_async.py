#!/usr/bin/env python
#-*- coding:utf-8 -*-

from kazoo.client import KazooClient
from kazoo.handlers.gevent import SequentialGeventHandler

zk = KazooClient(handler=SequentialGeventHandler())

# returns immediately
event = zk.start_async()
event.wait(timeout=30)

if not zk.connected:
    # Not connected, stop trying to connect
    zk.stop()
    raise Exception("Unable to connect.")
