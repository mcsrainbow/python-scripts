#!/usr/bin/env python
#-*- coding:utf-8 -*-

from kazoo.client import KazooClient
from kazoo.client import KazooState
from kazoo.retry import KazooRetry

# Connection Handling
zk = KazooClient(hosts='127.0.0.1:2181')
zk.start()

# Creating Nodes
# Ensure a path, create if necessary
zk.ensure_path("/my/favorite")

# Reading data
# Determine if a node exists
if zk.exists("/my/favorite/node"):
    print "Node /my/favorite exists"
else:
    # Create a node with data
    zk.create("/my/favorite/node", b"a value")
# Print the version of a node and its data
data, stat = zk.get("/my/favorite")
print("Version: %s, data: %s" % (stat.version, data.decode("utf-8")))

# List the children
children = zk.get_children("/my/favorite")
print("There are %s children with names %s" % (len(children), children))

# Updating Data 
zk.set("/my/favorite", b"some data")

# Deleting Nodes
#zk.delete("/my/favorite/node", recursive=True)

# Drop Connection
zk.stop()
