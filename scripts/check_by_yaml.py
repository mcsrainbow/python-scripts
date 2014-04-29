#!/usr/bin/env python

# Author: Dong Guo
# Last Modified: 2014/4/29

# import os moudule to execute local commands
import os

# import sys module to return correct exit states to nagios
import sys

# nagios states
STATE_OK = 0
STATE_WARNING = 1
STATE_CRITICAL = 2
STATE_UNKNOWN = 3
STATE_DEPENDENT = 4

def parse_opts():
    """Help messages (-h, --help)"""

    import textwrap
    import argparse
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
        '''
        examples:
          {0} -f /data/reports -k metrics.err -w 500 -c 1000
          {0} -f /data/reports -k finance.cost -w 6000 -c 10000 -p ^[0-9]+$

          /data/reports:
          ---
          period: daily
          metrics:
            err: 100
            health: 1
            qps: 1000
            req: 10000
            req_last: 20000
            uptime: 3600
            uptime_last: 7200
          finance:
            cost: 5000
            profit: 20000
        '''.format(__file__)
        ))

    parser.add_argument('-f', metavar='file', type=str, required=True, help='the absolute path of yaml file')
    parser.add_argument('-k', metavar='key', type=str, required=True, help='key name')
    parser.add_argument('-w', metavar='warn', type=int, required=True, help='threshold of warn')
    parser.add_argument('-c', metavar='crit', type=int, required=True, help='threshold of critical')
    parser.add_argument('-p', metavar='regex', type=str, help='regular expression pattern')

    args = parser.parse_args()
    return {'file':args.f, 'key':args.k, 'warn':args.w, 'crit':args.c, 'regex':args.p}

def get_value(opts):
    """Get value from YAML file"""

    try:
        import yaml
    except ImportError:
        sys.stderr.write("ERROR: Requires YAML, try 'yum install PyYAML.'\n")
        sys.exit(STATE_DEPENDENT)

    info = open(opts['file'])
    value = yaml.load(info)

    key_list = opts['key'].split('.')
    for eachkey in key_list:
        try:
            value = value[eachkey]
        except KeyError:
            sys.stderr.write("No such key: '{0}'\n".format(opts['key']))
            sys.exit(STATE_UNKNOWN)

    info.close()

    return value

def check_value(value):
    """Check value with threshold settings"""
    
    # import regex module to check the value with given pattern
    import re

    if opts['regex']:
        if not re.match(opts['regex'],str(value)):
            print "The value doesn't match the given regex pattern."
            sys.exit(STATE_WARNING)

    if value > opts['warn'] and value < opts['crit']:
        print "WARN. The value of {0}: {1} is greater than {2}".format(opts['key'],value,opts['warn'])
        sys.exit(STATE_WARNING)

    if value > opts['crit']:
        print "CRIT. The value of {0}: {1} is greater than {2}".format(opts['key'],value,opts['crit'])
        sys.exit(STATE_CRITICAL)
    
    print "OK. The value of {0}: {1}".format(opts['key'],value)
    sys.exit(STATE_OK)

if __name__=='__main__':
    # check arguments
    argv_len = len(sys.argv)
    if argv_len < 2:
        os.system(__file__ + " -h")
        sys.exit(STATE_UNKNOWN)

    # get arguments
    opts = parse_opts()
    
    # get the value
    value = get_value(opts)

    # check with nagios
    check_value(value)
