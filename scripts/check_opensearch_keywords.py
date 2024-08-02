#!/usr/bin/env python
#-*- coding:utf-8 -*-

# Description: HTTPS requests check key words from index-name-* for OpenSearch
# Author: Damon Guo

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
          {0} -n opensearch.heylinux.com -a username:password -i "index-name-*" -d key1:value1,key2:"word1 word2 word3"
          {0} -n opensearch.heylinux.com -a username:password -i "logstash-eks-containers-log-*" \
              -d kubernetes.container.name:"app-auth",message:"LOGIN_ERROR LinuxPlatform" -m 240
          {0} -n opensearch.heylinux.com -a username:password -i "logstash-eks-containers-log-*" \
              -d kubernetes.container.name:"app-auth",message:"LOGIN_ERROR LinuxPlatform" -m 240 -c
          {0} -n opensearch.heylinux.com -a username:password -i "logstash-eks-containers-log-*" \
              -d "kubernetes.pod.name:*job*,message:*error*" -m 240 -w
          {0} -n opensearch.heylinux.com -a username:password -i "logstash-eks-containers-log-*" \
              -d "kubernetes.pod.name:*job*,message:*error*" -m 240 -w -c
        '''.format(__file__)
        ))

    parser.add_argument('-n', metavar='domain', type=str, required=True, help='OpenSearch domain')
    parser.add_argument('-a', metavar='auth', type=str, required=True, help='username:password for basic authentication')
    parser.add_argument('-i', metavar='index', type=str, required=True, help='index to search')
    parser.add_argument('-d', metavar='data', type=str, required=True, help='key1:value1,key2:value2,... to search')
    parser.add_argument('-o', metavar='output', type=str, default='message', help='display value of the key in output [default: message]')
    parser.add_argument('-m', metavar='minute', type=int, default=1440, help='period to search [default: 1440]')
    parser.add_argument('-w', action="store_true", default=False, help='wildcard search')
    parser.add_argument('-v', action="store_true", default=False, help='debug with json body')
    parser.add_argument('-c', action="store_true", default=False, help='count the lines of output')

    if len(sys.argv) < 2:
        parser.print_help()
        sys.exit(2)

    args = parser.parse_args()
    return {'domain':args.n, 'auth':args.a, 'index':args.i, 'data':args.d, 'output':args.o, 'minute':args.m, 'wildcard':args.w, 'debug':args.v, 'count':args.c}

def get_results(opts):
    """Get results with given parameters."""

    url = "https://{0}/{1}/_search".format(opts['domain'],opts['index'])

    username = opts['auth'].split(':')[0]
    password = opts['auth'].split(':')[1]
    httpauth = HTTPBasicAuth(username, password)

    gte_str = "now-{0}m".format(opts['minute'])

    kv_dict = {}
    for kv_item in opts['data'].split(','):
        k = kv_item.split(':')[0]
        v = kv_item.split(':')[1]
        kv_dict[k] = v

    data = {"sort":{"@timestamp":"desc"},
            "query":{
              "bool":{
                "must":[
                  {"range":{"@timestamp":{"gte":gte_str,"lt":"now"}}}
                ]}}}

    for k,v in kv_dict.items():
        if opts['wildcard']:
            match_item = {"wildcard":{k:{"wildcard":v,"boost":1}}}
        else:
            match_item = {"match":{k:{"query":v,"operator":"and"}}}
        data["query"]["bool"]["must"].append(match_item)

    headers = {"Content-Type": "application/json; charset=utf-8"}

    try:
        res = requests.post(url, headers=headers, auth=httpauth, json=data, verify=False, timeout=5)
        if res.status_code == requests.codes.ok:
            res_dict = res.json()
            hits_count = len(res_dict["hits"]["hits"])
            if not opts['count']:
                if hits_count == 0:
                    print("INFO: No such message found")
                else:
                    for i in range(hits_count):
                        output = res_dict["hits"]["hits"][i]["_source"][opts['output']]
                        print(output)
            else:
                print(hits_count)

            if opts['debug']:
                print(json.dumps(res_dict,indent=2))
        else:
            print("StatusCode: {0}, Error: {1}".format(res.status_code,res.content))

    except KeyError:
        print("Exception: KeyError")
        if opts['debug']:
            print(json.dumps(res_dict,indent=2))

    except IndexError:
        print("Exception: IndexError")
        if opts['debug']:
            print(json.dumps(res_dict,indent=2))

    except requests.exceptions.Timeout:
        print("Exception: Timeout")

    except requests.exceptions.ConnectionError:
        print("Exception: ConnectionError")

    return True

def main():
    opts = parse_opts()
    get_results(opts)

    return 0

if __name__=='__main__':
    sys.exit(main())
