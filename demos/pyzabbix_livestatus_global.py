#!/usr/bin/env python

# Description: Summarize the triggers values
# Author: Dong Guo
# Last modified: 12/14/2016

import os
import sys
import re
from pyzabbix import ZabbixAPI, ZabbixAPIException

zabbix_site = "http://localhost/zabbix"
zabbix_user = "username"
zabbix_pass = "password"

def parse_opts():
    """Help messages (-h, --help)"""

    import textwrap
    import argparse

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
        '''
        examples:
          {0} --trigger 'Free disk space is less than 10%'
          {0} --trigger 'Free disk space is less than 5%'
          ...
        '''.format(__file__)
        ))
    
    parser.add_argument('--trigger',type=str,required=True,help='part of trigger name or full trigger name')
    args = parser.parse_args()

    return {'trigger':args.trigger}

def check_cluster(trigger):
    zapi = ZabbixAPI(zabbix_site)
    zapi.login(zabbix_user,zabbix_pass)
    
    trigger_notok = zapi.trigger.get(monitored=1,selectHosts=1,
                                     output=['hosts'],withLastEventUnacknowledged=1,
                                     search={'description':trigger},filter={"value":1})

    trigger_host_list = []
    for trigger_item in trigger_notok:
        trigger_host = trigger_item['hosts'][0]['hostid']
        trigger_host_list.append(int(trigger_host))

    trigger_host_msglist = []
    trigger_host_list_nondup = list(set(trigger_host_list))
    for trigger_host_nondup in trigger_host_list_nondup:
        trigger_host_dict = zapi.host.get(hostids=trigger_host_nondup)
        trigger_host_name = trigger_host_dict[0]['host']
        trigger_host_count = trigger_host_list.count(trigger_host_nondup)
        trigger_host_msg = "{0} trigger(s) on {1}".format(trigger_host_count,trigger_host_name)
        trigger_host_msglist.append(trigger_host_msg)

    if not trigger_host_msglist:
        print "OK"
    else:
        print '; '.join(trigger_host_msglist)

    return True

if __name__=='__main__':
    if len(sys.argv) < 2:
        os.system(__file__ + " -h")
        sys.exit(1)
    opts = parse_opts()

    check_cluster(opts['trigger'])
