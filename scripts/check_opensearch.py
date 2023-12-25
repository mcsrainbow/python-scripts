#!/usr/bin/env python
#-*- coding:utf-8 -*-

# Description: HTTPS requests check index-name-* for OpenSearch
# Author: Damon Guo

import os
import sys
import requests
from requests.auth import HTTPBasicAuth
import json

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def parse_opts():
    """Help messages(-h, --help)."""

    import textwrap
    import argparse

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
        '''
        examples:
          {0} -n opensearch.heylinux.com -a username:password -d app_name:foo,case:bar -o severity
          {0} -n opensearch.heylinux.com -a username:password -d app_name:foo,case:bar -o severity -v
          {0} -n opensearch.heylinux.com -a username:password -d app_name:foo,case:bar -o summary
          {0} -n opensearch.heylinux.com -a username:password -d app_name:foo,case:bar -o severity -m 15
        '''.format(__file__)
        ))

    parser.add_argument('-n', metavar='domain', type=str, required=True, help='OpenSearch domain')
    parser.add_argument('-a', metavar='auth', type=str, required=True, help='username:password for basic authentication')
    parser.add_argument('-d', metavar='data', type=str, required=True, help='key1:value1,key2:value2 to search')
    parser.add_argument('-o', metavar='output', type=str, choices=['severity','summary'], required=True, help='display value of the key in output')
    parser.add_argument('-m', metavar='minute', type=int, help='period to search [default: 1440]')
    parser.add_argument('-v', action="store_true", default=False, help='debug with json body')

    args = parser.parse_args()
    return {'domain':args.n, 'auth':args.a, 'data':args.d, 'output':args.o, 'minute':args.m, 'debug':args.v}

def get_results(opts):
    """Get results with given parameters."""

    url = "https://{0}/index-name-*/_search".format(opts['domain'])

    username = opts['auth'].split(':')[0]
    password = opts['auth'].split(':')[1]
    httpauth = HTTPBasicAuth(username, password)

    if opts['minute']:
      gte_str = "now-{0}m".format(opts['minute'])
    else:
      # search in 1440 minutes by default
      gte_str = "now-1440m"

    k1 = opts['data'].split(',')[0].split(':')[0]
    v1 = opts['data'].split(',')[0].split(':')[1]
    k2 = opts['data'].split(',')[1].split(':')[0]
    v2 = opts['data'].split(',')[1].split(':')[1]

    data = {"size":1,
            "sort":{"publish_time":"desc"},
            "query":{
              "bool":{
                "must":[
                  {"range":{"publish_time":{"gte":gte_str,"lt":"now"}}},
                  {"match":{k1:v1}},
                  {"match":{k2:v2}}
                ]}}}

    headers = {"Content-Type": "application/json; charset=utf-8"}

    try:
        res = requests.post(url, headers=headers, auth=httpauth, json=data, verify=False, timeout=5)
        if res.status_code == requests.codes.ok:
            res_dict = res.json()
            output = res_dict["hits"]["hits"][0]["_source"][opts['output']]
            print(output)
            if opts['debug']:
                print(json.dumps(res_dict,indent=2))
        else:
            if opts['output'] == "severity":
                print(5)
                if opts['debug']:
                    print("StatusCode: {0}, Error: {1}".format(res.status_code,res.content))
            else:
                print("StatusCode: {0}, Error: {1}".format(res.status_code,res.content))

    except KeyError:
        if opts['output'] == "severity":
            print(5)
        else:
            print("Exception: KeyError")
            if opts['debug']:
                print(json.dumps(res_dict,indent=2))

    except IndexError:
        if opts['output'] == "severity":
            print(5)
        else:
            print("Exception: IndexError")
            if opts['debug']:
                print(json.dumps(res_dict,indent=2))

    except requests.exceptions.Timeout:
        if opts['output'] == "severity":
            print(5)
        else:
            print("Exception: Timeout")

    except requests.exceptions.ConnectionError:
        if opts['output'] == "severity":
            print(5)
        else:
            print("Exception: ConnectionError")

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
