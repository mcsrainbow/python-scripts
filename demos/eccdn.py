#!/usr/bin/env python
#-*- coding:utf-8 -*-

# Description: Get EdgeCast CDN usage via API
# Author: Dong Guo
# Last modified: 2015-03-11 02:23 UTC

import os
import sys
import re
import requests
import json
import datetime

api_url = "https://api.edgecast.com/v2/reporting/customers/YOUR-CUSTOMER-ID/"
api_token = "YOUR-API-TOKEN"

date_format = "%Y-%m-%d"
time_format = "%Y-%m-%dT%H:%M:%S"

def parse_opts():
    """Help messages(-h, --help)."""

    import textwrap
    import argparse

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
        '''
        examples:
          {0} -d 31
          {0} -s 2014-10-13
          {0} -r 2014-09-30_2014-10-11
        '''.format(__file__)
        ))

    exclusion = parser.add_mutually_exclusive_group(required=True)
    exclusion.add_argument('-d', metavar='days', type=int, help='the number of days')
    exclusion.add_argument('-s', metavar='date', type=str, help='the specified date')
    exclusion.add_argument('-r', metavar='range', type=str, help='the specified date range')

    args = parser.parse_args()
    return {'days':args.d, 'date':args.s, 'range':args.r}

class TokenAuth(requests.auth.AuthBase):
    """Attaches token authentication to the given requested object."""

    def __init__(self, token):
        self.token = token

    def __call__(self, req):
        req.headers['Authorization'] = "TOK:%s" % self.token
        return req

def prettify(object):
    """Format JSON in human-readable form."""

    return json.dumps(object,indent=1)

def get_bytestransferred(start_date,end_date):
    """Get summary data."""

    res_url = api_url + "bytestransferred"  
    req = requests.get(res_url,auth=TokenAuth(api_token),
                       params={'begindate':start_date,'enddate':end_date})
    return req.json()

def get_cachestats(start_date,end_date):
    """Get cache stats."""

    res_url = api_url + "media/8/cachestats"
    req = requests.get(res_url,auth=TokenAuth(api_token),
                       params={'begindate':start_date,'enddate':end_date})
    return req.json()

def get_reports(date,days,opts):
    """Get reports."""

    if opts['days']:
        start_date = (date - datetime.timedelta(days=days)).strftime(date_format)
        end_date = (date).strftime(date_format)
    if opts['date']:
        start_date = (date - datetime.timedelta(days=days+1)).strftime(date_format)
        end_date = (date - datetime.timedelta(days=days)).strftime(date_format)
    if opts['range']:
        start_date = (date).strftime(date_format)
        end_date = (days).strftime(date_format)

    sum_info = get_bytestransferred(start_date,end_date)
    sum_data = int(sum_info['Bytes']) * 1.00 / 1024 / 1024 / 1024 / 1024

    cache_info = get_cachestats(start_date,end_date)
    
    tcp_expired_hit = 0
    tcp_expired_miss = 0
    tcp_none = 0
    config_nocache = 0
    for dict_id in range(0,len(cache_info)):
        if cache_info[dict_id]['Name'] == 'TCP_HIT':
             tcp_hit = cache_info[dict_id]['Hits']
        if cache_info[dict_id]['Name'] == 'TCP_MISS':
             tcp_miss = cache_info[dict_id]['Hits']
        if cache_info[dict_id]['Name'] == 'TCP_EXPIRED_HIT':
             tcp_expired_hit = cache_info[dict_id]['Hits']
        if cache_info[dict_id]['Name'] == 'TCP_EXPIRED_MISS':
             tcp_expired_miss = cache_info[dict_id]['Hits']
        if cache_info[dict_id]['Name'] == 'NONE':
             tcp_none = cache_info[dict_id]['Hits']
        if cache_info[dict_id]['Name'] == 'CONFIG_NOCACHE':
             config_nocache = cache_info[dict_id]['Hits']

    cache_sum = tcp_hit + tcp_miss + tcp_none
    tcp_hit_ratio = tcp_hit * 100.00 / cache_sum
    tcp_miss_ratio = tcp_miss * 100.00 / cache_sum

    return {'start_date':start_date, 'end_date':end_date, 'sum_data':round(sum_data, 2), 
            'tcp_hit_ratio':round(tcp_hit_ratio, 2), 'tcp_hit':tcp_hit,
            'tcp_miss_ratio':round(tcp_miss_ratio, 2), 'tcp_miss':tcp_miss,
            'config_nocache':config_nocache}

def print_reports(reports):
    """Print reports."""

    print "sum_data: {0} TB".format(reports['sum_data'])
    print "cache_tcp_hit_ratio: {0}%".format(reports['tcp_hit_ratio'])
    print "cache_tcp_hit_num: {0}".format(reports['tcp_hit'])
    print "cache_tcp_miss_ratio: {0}%".format(reports['tcp_miss_ratio'])
    print "cache_tcp_miss_num: {0}".format(reports['tcp_miss'])
    print "cache_config_nocache_num: {0}".format(reports['config_nocache'])

    return True

def main():
    argv_len = len(sys.argv)
    if argv_len < 2:
        os.system(__file__ + " -h")
        return 2

    opts = parse_opts()
    daterex = "^[0-9]{4}-(((0[13578]|(10|12))-(0[1-9]|[1-2][0-9]|3[0-1]))|(02-(0[1-9]|[1-2][0-9]))|((0[469]|11)-(0[1-9]|[1-2][0-9]|30)))$"

    if opts['days']:
        date = datetime.datetime.today()
        reports = get_reports(date,opts['days'],opts)
        print "days: {0}".format(opts['days'])
        print "date_range: {0} ~ {1}".format(reports['start_date'],reports['end_date'])
        print_reports(reports)

    elif opts['date']:
        if re.match(daterex,opts['date']):
            date = datetime.datetime.strptime(opts['date'],"%Y-%m-%d")
            reports = get_reports(date,-1,opts)
            print "date: {0}".format(reports['start_date'])
            print_reports(reports)
        else:
            print "The date is incorrect"
            return 2

    elif opts['range']:
        daterex_raw = "[0-9]{4}-(((0[13578]|(10|12))-(0[1-9]|[1-2][0-9]|3[0-1]))|(02-(0[1-9]|[1-2][0-9]))|((0[469]|11)-(0[1-9]|[1-2][0-9]|30)))"
        daterex_range = "^{0}_{0}$".format(daterex_raw)
        if re.match(daterex_range,opts['range']):
            date = datetime.datetime.strptime(opts['range'].split("_")[0],"%Y-%m-%d")
            days = datetime.datetime.strptime(opts['range'].split("_")[1],"%Y-%m-%d")
            reports = get_reports(date,days,opts)
            print "date_range: {0} ~ {1}".format(reports['start_date'],reports['end_date'])
            print_reports(reports)
        else:
            print "The date range is incorrect"
            return 2

    return 0

if __name__=='__main__':
    sys.exit(main())
