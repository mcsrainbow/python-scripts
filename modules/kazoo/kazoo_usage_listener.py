#!/usr/bin/env python
#-*- coding:utf-8 -*-

from kazoo.client import KazooClient
from kazoo.client import KazooState
from kazoo.retry import KazooRetry

# Connection Handling
zk = KazooClient(hosts='127.0.0.1:2181')
zk.start()

# Listening for Connection Events
def my_listener(state):
    if state == KazooState.LOST:
        # Register somewhere that the session was LOST
        print "KazooState.LOST"
    elif state == KazooState.SUSPENDED:
        # Handle being disconnected from Zookeeper
        print "KazooState.SUSPENDED"
    else:
        # Handle being connected/reconnected to Zookeeper
        print "KazooState.Other"

zk.add_listener(my_listener)

# Drop Connection
zk.stop()
