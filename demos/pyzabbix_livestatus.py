#!/usr/bin/env python

# Description: Summarize the triggers values of multiple hosts for Cluster Level Checks
# Author: Dong Guo
# Last modified: 12/01/2016

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
          {0} --group idc1-server --trigger 'Number of metrics.err in /data/stats/metrics' --display ratio
          {0} --group idc1-server --trigger 'No string ok found on health page' --display decimal

          {0} --host idc1-server2[0-1].* --trigger 'Number of metrics.err in /data/stats/metrics' --display ratio --debug
          {0} --host idc1-server2[0-1].* --trigger 'No string ok found on health page' --display decimal
          ...
        '''.format(__file__)
        ))
    
    exclusion = parser.add_mutually_exclusive_group(required=True)
    exclusion.add_argument('--host',type=str,help='host name regular expression')
    exclusion.add_argument('--group',type=str,help='exact group name')

    parser.add_argument('--trigger',type=str,required=True,help='part of trigger name or full trigger name')
    parser.add_argument('--display',type=str,required=True,choices=['ratio','decimal'])
    parser.add_argument('--debug',action="store_true",default=False,help='show debug messages when check with host name regular expression')
    args = parser.parse_args()

    return {'host':args.host,'group':args.group,'trigger':args.trigger,'display': args.display,'debug': args.debug}

def check_cluster(host,group,trigger,display,debug):
    zapi = ZabbixAPI(zabbix_site)
    zapi.login(zabbix_user,zabbix_pass)
    if debug:
        print("Connected to Zabbix API Version {0}".format(zapi.api_version()))
    
    notok_num = 0
    total_num = 0

    if group:
        trigger_obj_notok = zapi.trigger.get(group=group,monitored=1,withLastEventUnacknowledged=1,search={'description':trigger},filter={'value':1})
        trigger_obj_total = zapi.trigger.get(group=group,monitored=1,search={'description':trigger})
        notok_num = len(trigger_obj_notok)
        total_num = len(trigger_obj_total)

    if host:
        host_name_rex = host
        hosts = zapi.host.get(monitored_hosts=1,output="extend")
        for i in range(0,len(hosts)):
            host_name = hosts[i]["name"]
            if re.match(host_name_rex,host_name):
                total_num += 1
                trigger_obj = zapi.trigger.get(host=host_name,search={'description':trigger})
                if not trigger_obj:
                    if debug:
                        print("No such trigger: '{0}' on host: {1}".format(trigger,host_name))
                    else:
                        return False
                else:    
                    trigger_id = trigger_obj[0]["triggerid"]
                    trigger_retval = trigger_obj[0]["value"]
                    trigger_item = zapi.trigger.get(triggerids=trigger_id,withLastEventUnacknowledged=1)
                    if trigger_item and trigger_retval == '1':
                        if debug:
                            print("Found host:'{0}' with trigger return value:'{1}'".format(host_name,trigger_retval))
                        notok_num += 1
                    elif trigger_retval == '1':
                        if debug:
                            print("Found host:'{0}' with acknowledged trigger return value:'{1}'".format(host_name,trigger_retval))
                    elif trigger_retval == '0':
                        if debug:
                            print("Found host:'{0}' with trigger return value:'{1}'".format(host_name,trigger_retval))
  
    dicimal_number =  float(notok_num) / float(total_num)
    if display == 'ratio': 
        print("{0} of {1} servers not ok".format(notok_num,total_num))
    if display == 'decimal':
        print dicimal_number

    return True

if __name__=='__main__':
    if len(sys.argv) < 2:
        os.system(__file__ + " -h")
        sys.exit(1)
    opts = parse_opts()

    check_cluster(opts['host'],opts['group'],opts['trigger'],opts['display'],opts['debug'])
