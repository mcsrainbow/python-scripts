#!/usr/bin/env python
#-*- coding:utf-8 -*-

from fabric.api import *

class FabricSupport:
    def __init__(self):
        pass

    def hostname(self):
        run("hostname")

    def df(self):
        run("df -h")

    def execute(self,task,hosts):
        env.parallel = True
        env.pool_size = 3

        get_task = "task = self.%s" % task
        exec get_task

        execute(task,hosts=hosts)
