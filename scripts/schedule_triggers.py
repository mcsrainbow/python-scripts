#!/usr/bin/env python
#-*- coding:utf-8 -*-

# Description: Update triggers within a yaml file to disable and schedule downtime for services
# Author: Dong Guo

import os
import sys
import json
import yaml
import time
from datetime import datetime

YAML_DATA = '/var/lib/zabbix/scheduled_triggers.yml'

def parse_opts():
    """Help messages(-h, --help)."""

    import textwrap
    import argparse

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
        '''
        examples:
          {0} -d -H '*' -T 'No monit process running'
          {0} -d -H '*' -T 'No monit process running' --delete
          {0} -d -H idc1-server.* -T 'Number of files in server logs dir'
          {0} -d -H idc1-server.* -T 'Number of metrics.err in metrics.yml'
          {0} -s -H idc2-server.* -T 'Lack of available memory' --hours 10
          {0} -s -H idc2-server.* -T 'Lack of available memory' --delete
          {0} -s -H idc2-server1 -T 'Disk I/O is overloaded' --hours 4
          {0} -v
        '''.format(__file__)
        ))

    exclusion = parser.add_mutually_exclusive_group(required=True)
    exclusion.add_argument('-d', action="store_true", help='disable the notification for trigger')
    exclusion.add_argument('-s', action="store_true", help='schedule a downtime for trigger')
    exclusion.add_argument('-v', action="store_true", help='view the yaml data')
    
    parser.add_argument('-H', metavar='host', type=str, help='regex name of the host')
    parser.add_argument('-T', metavar='trigger', type=str, help='part of the trigger name')
    parser.add_argument('--hours', type=int, help='downtime hours for the trigger')
    parser.add_argument('--delete', action="store_true", default=False, help='delete the trigger')

    args = parser.parse_args()
    return {'disable':args.d, 'schedule':args.s, 'display':args.v, 'host':args.H, 'trigger':args.T,
            'hours':args.hours, 'delete':args.delete }

def disable_notification(opts):
    host_name = opts['host']
    trigger_name = opts['trigger']
    
    with open(YAML_DATA) as f:
        data_dict = yaml.load(f)
        if not data_dict['notifications'].has_key('disabled'):
            data_dict['notifications']['disabled'] = {}

        if not opts['delete']:
            if data_dict['notifications']['disabled'].has_key(host_name):
                if trigger_name not in data_dict['notifications']['disabled'][host_name]:
                    data_dict['notifications']['disabled'][host_name].append(trigger_name)
                else:
                    print "notifications.disabled.'{0}'.'{1}' already exists".format(host_name,trigger_name)
            else:
                data_dict['notifications']['disabled'][host_name] = [trigger_name]
                print "Disabled {0}:{1}".format(host_name,trigger_name)
        else:
            if data_dict['notifications']['disabled'].has_key(host_name):
                if trigger_name in data_dict['notifications']['disabled'][host_name]:
                    data_dict['notifications']['disabled'][host_name].remove(trigger_name)
                    print "Removed notifications.disabled.'{0}'.'{1}'".format(host_name,trigger_name)
                else:
                    print "notifications.disabled.'{0}'.'{1}' does NOT exist".format(host_name,trigger_name)
                    return False
            else:
                print "notifications.disabled.'{0}' does NOT exist".format(host_name)
                return False

    with open(YAML_DATA, 'w') as f:
        yaml.dump(data_dict, f, default_flow_style=False)

    return True

def schedule_downtime(opts):
    time_format = "%Y-%m-%dT%H_%M_00"
    now_timestamp = int(time.time()) 

    if opts['hours']:
        downtime_hours = opts['hours']
        downtime_timestamp = int(now_timestamp) + 3600 * downtime_hours
        downtime_formatted = datetime.fromtimestamp(int(downtime_timestamp)).strftime(time_format)

    host_name = opts['host']
    trigger_name = opts['trigger']

    with open(YAML_DATA) as f:
        data_dict = yaml.load(f)
        if not data_dict['notifications'].has_key('scheduled'):
            data_dict['notifications']['scheduled'] = {}

        if not opts['delete']:
            if data_dict['notifications']['scheduled'].has_key(downtime_formatted):
                if data_dict['notifications']['scheduled'][downtime_formatted].has_key(host_name):
                    if trigger_name not in data_dict['notifications']['scheduled'][downtime_formatted][host_name]:
                        data_dict['notifications']['scheduled'][downtime_formatted][host_name].append(trigger_name)
                    else:
                        print "notifications.scheduled.'{0}'.'{1}'.'{2}' already exists".format(downtime_formatted,host_name,trigger_name)
                else:
                    data_dict['notifications']['scheduled'][downtime_formatted][host_name] = [trigger_name]
                    print "Scheduled {0} hours downtime for {1}:{2}".format(downtime_hours,host_name,trigger_name)
            else:
                data_dict['notifications']['scheduled'][downtime_formatted] = {}
                data_dict['notifications']['scheduled'][downtime_formatted][host_name] = [trigger_name]
                print "Scheduled {0} hours downtime for {1}:{2}".format(downtime_hours,host_name,trigger_name)
        else:
            for scheduled_downtime_formatted in data_dict['notifications']['scheduled'].keys():
                for scheduled_host_name in data_dict['notifications']['scheduled'][scheduled_downtime_formatted].keys():
                    if scheduled_host_name == opts['host']:
                        if trigger_name in data_dict['notifications']['scheduled'][scheduled_downtime_formatted][scheduled_host_name]:
                            data_dict['notifications']['scheduled'][scheduled_downtime_formatted][scheduled_host_name].remove(trigger_name)
                            print "Removed notifications.scheduled.'{0}'.'{1}'.'{2}'".format(scheduled_downtime_formatted,scheduled_host_name,trigger_name)

        for scheduled_downtime_formatted in data_dict['notifications']['scheduled'].keys():
             scheduled_downtime_timestamp = int(time.mktime(datetime.strptime(scheduled_downtime_formatted,time_format).timetuple()))
             if now_timestamp > scheduled_downtime_timestamp:
                 data_dict['notifications']['scheduled'].pop(scheduled_downtime_formatted)
                 print "Removed overdue scheduled_downtime:{0}".format(scheduled_downtime_formatted)

    with open(YAML_DATA, 'w') as f:
        yaml.dump(data_dict, f, default_flow_style=False)

    return True

def display_yamldata(opts):
    with open(YAML_DATA) as f:
        data_dict = yaml.load(f)

    print "YAML_DATA: {0}".format(YAML_DATA)
    print json.dumps(data_dict,indent=2)
    return True

def main():
    if len(sys.argv) < 2:
        os.system(__file__ + " -h")
        return 2

    if not os.path.isfile(YAML_DATA) or os.stat(YAML_DATA).st_size == 0:
        with open(YAML_DATA, "w") as f:
            f.write("notifications: {}")

    opts = parse_opts()
    if opts['disable']:
        if not opts['host'] or not opts['trigger']:
            print "Missing parameters, run '{0} -h' for help".format(__file__)
            return 2
        disable_notification(opts)

    if opts['schedule']:
        if not opts['host'] or not opts['trigger']:
            print "Missing parameters, run '{0} -h' for help".format(__file__)
            return 2
        if not opts['delete'] and not opts['hours']:
            print "Missing parameters, run '{0} -h' for help".format(__file__)
            return 2
        schedule_downtime(opts)

    if opts['display']:
        display_yamldata(opts)

    return 0

if __name__ == '__main__':
    sys.exit(main())
