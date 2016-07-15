#!/usr/bin/env python
#-*- coding:utf-8 -*-

# Description: HTTP requests check for Zabbix
# Author: Dong Guo

import os
import sys
import requests
import time

def parse_opts():
    """Help messages(-h, --help)."""

    import textwrap
    import argparse

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
        '''
        examples:
          {0} -u idc1-web1/health
          {0} -u http://idc1-web1/health
          {0} -u http://idc1-web1/health -c ok
          {0} -u http://idc1-web1/health -c ok -V
          {0} -u http://idc1-web1/health -c ok -t 2 -V
          {0} -u http://idc1-web2:3000
          {0} -u http://idc1-web3/login.php?page=redirect_string -a username:password -V
          {0} -u https://idc2-web1.yourdomain.com -V
        '''.format(__file__)
        ))

    parser.add_argument('-u', metavar='url', type=str, required=True, help='URL to GET or POST [default: / with http://]')
    parser.add_argument('-t', metavar='timeout', type=float, help='seconds before connection times out [default: 10]')
    parser.add_argument('-c', metavar='content', type=str, help='string to expect in the content')
    parser.add_argument('-a', metavar='auth', type=str, help='username:password on sites with basic authentication')
    parser.add_argument('-V', action="store_true", default=False, help='return actual value instead of 0 and 1')
    parser.add_argument('-p', metavar='payload', type=str, help='URL encoded http POST data')

    args = parser.parse_args()
    return {'url':args.u, 'timeout':args.t, 'content':args.c, 'auth':args.a, 'value':args.V, 'payload':args.p}

def get_results(opts):
    """Get results with given parameters."""

    url = opts['url']
    if "http://" not in url and "https://" not in url:
        url = "http://" + url

    start_timestamp = time.time()
    if opts['timeout']:
        timeout = opts['timeout']
    else:
        timeout = 10

    try:
        if opts['auth']:
            from requests.auth import HTTPBasicAuth
            username = opts['auth'].split(':')[0]
            password = opts['auth'].split(':')[1]
            httpauth = HTTPBasicAuth(username, password)
            if opts['payload']:
                payload = opts['payload']
                req = requests.post(url, data=payload, auth=httpauth, timeout=opts['timeout'])
            else:
                req = requests.get(url, auth=httpauth, timeout=opts['timeout'])
        else:
            if opts['payload']:
                payload = opts['payload']
                req = requests.post(url, data=payload, timeout=opts['timeout'])
            else:
                req = requests.get(url, timeout=opts['timeout'])

        end_timestamp = time.time()
        response_secs = round(end_timestamp - start_timestamp,3)

        if opts['value']:
            if opts['content']:
                print req.content
            elif opts['timeout']:
                print response_secs
            else:
                print req.status_code
        else:
            if req.status_code == requests.codes.ok:
                if opts['content']:
                    if req.content == opts['content']:
                        print 0
                    else:
                        print 1
                else:
                    print 0
            else:
                print 1

    except requests.exceptions.Timeout:
        if opts['value']:
            print "Timeout"
        else:
            print 1

    except requests.exceptions.ConnectionError:
        if opts['value']:
            print "ConnectionError"
        else:
            print 1

    return True

def main():
    if len(sys.argv) < 2:
        os.system(__file__ + " -h")
        return 2

    opts = parse_opts()
    get_results(opts)

    return 0

if __name__=='__main__':
    sys.exit(main())
