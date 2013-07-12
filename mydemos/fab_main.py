#!/usr/bin/env python
#-*- coding:utf-8 -*-

from fab_demo import FabricSupport

hosts = ['localhost', '127.0.0.1', 'heydevops-workspace']

myfab = FabricSupport()
myfab.execute("hostname",hosts)
