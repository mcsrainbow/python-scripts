#!/usr/bin/env python
#-*- coding:utf-8 -*-

# Last Modified: 2015-01-28
# Author: Dong Guo

import os
import sys
import requests
import json
import ast

def parse_opts():
    """Help messages(-h, --help)"""
    import textwrap
    import argparse

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
        '''
        examples:
          {0} YOUR-DOMAIN.COM
          {0} YOUR.DOMAIN.COM
        '''.format(__file__)
        ))
    parser.add_argument('zone_name', action="store", type=str)

    args = parser.parse_args()
    return {'zone_name': args.zone_name}

def dump_records(zone_name):
    customer_name="YOUR-CUSTOMER-NAME"
    user_name="YOUR-USER-NAME"
    password="YOUR-PASSWORD"
    
    api_url = "https://api.dynect.net"
    session_url = "/REST/Session/"
    nodelist_url = "/REST/NodeList/"
    anyrecord_url = "/REST/ANYRecord/"
    
    headers_raw = {'Content-type': 'application/json'}
    auth_data = {'customer_name': customer_name, 'user_name': user_name, 'password': password}
    req_token = requests.post(api_url+session_url, data=json.dumps(auth_data), headers=headers_raw)
    
    api_token = req_token.json()['data']['token']
    
    headers_api = {'Auth-Token': '{0}'.format(api_token), 'Content-type': 'application/json'}
    
    req_nodelist = requests.get(api_url+nodelist_url+zone_name, headers=headers_api)
    
    for node in req_nodelist.json()['data']:
        print "nodename: {0}".format(node)
        req_anyrecord = requests.get(api_url+anyrecord_url+zone_name+"/"+node+"/", headers=headers_api)
        for record_url in req_anyrecord.json()['data']:
            req_record = requests.get(api_url+record_url, headers=headers_api)
            rec_ttl = req_record.json()['data']['ttl']
            rec_type = req_record.json()['data']['record_type']
            rec_rdata = req_record.json()['data']['rdata']
            print """  ttl: {0} type: {1} rdata: {2}""".format(rec_ttl,rec_type,ast.literal_eval(json.dumps(rec_rdata)))

if __name__=='__main__':
    # show help messages if no parameter
    argv_len = len(sys.argv)
    if argv_len < 2:
        os.system(__file__ + " -h")
        sys.exit(1)
    opts = parse_opts()

    dump_records(opts['zone_name'])
