#!/usr/bin/env python
#-*- coding:utf-8 -*-

from kazoo.client import KazooClient
from kazoo.client import KazooState
from kazoo.retry import KazooRetry

# Connection Handling
zk = KazooClient(hosts='127.0.0.1:2181')
zk.start()

# Retrying Commands
kr = KazooRetry(max_tries=3, ignore_expire=False)
result = kr(zk.get, "/my/favorite/node")

def my_func(event):
    print "my_func"
    # check to see what the children are now

# Call my_func when the children change
children = zk.get_children("/my/favorite", watch=my_func)

@zk.ChildrenWatch("/my/favorite")
def watch_children(children):
    print("Children are now: %s" % children)
# Above function called immediately, and from then on

@zk.DataWatch("/my/favorite/node")
def watch_node(data, stat):
    print("Version: %s, data: %s" % (stat.version, data.decode("utf-8")))

# Drop Connection
zk.stop()       
