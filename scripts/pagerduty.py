#!/usr/bin/env python

# Author: Dong Guo
# Last Modified: 2014/07/28
# Reports:
# 1. number of incidents per day (total, breakdown by host, breakdown by service)
# 2. for each incident, time between first notification to ack, number of notifications, number of ack, number of escalation, if resolved by API

import requests
import json
import datetime
import os
import sys
import time
import re
import calendar
import requests

api_url = "https://YOUR-SUBDOMAIN.pagerduty.com/api/v1/"
api_token = "YOUR-API-TOKEN"

date_format = "%Y-%m-%d"
time_format = "%Y-%m-%dT%H:%M:%S"

def parse_opts():
    """Help messages(-h, --help)"""
    import textwrap
    import argparse

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
        '''
        examples:
          {0} -d 7
          {0} -s 2014-07-26
        '''.format(__file__)
        ))

    exclusion = parser.add_mutually_exclusive_group(required=True)
    exclusion.add_argument('-d', metavar='days', type=int, help='only summary info of the number of days')
    exclusion.add_argument('-s', metavar='date', type=str, help='detailed info of the specified date')

    args = parser.parse_args()
    return {'days':args.d, 'date':args.s}

class TokenAuth(requests.auth.AuthBase):
    """Attaches PagerDuty Token Authentication to the given Request object"""
    def __init__(self, token):
        self.token = token

    def __call__(self, req):
        req.headers['Authorization'] = "Token token=%s" % self.token
        return req

def prettify(object):
    '''Format JSON in human-readable form'''
    return json.dumps(object,indent=1)

def get_incidents(start_date,end_date):
    '''Get incidents'''
    res_url = api_url + "incidents"  
    req = requests.get(res_url,auth=TokenAuth(api_token),
                       params={'since':start_date,'until':end_date})
    return req.json()

def get_incident_by_id(id):
    '''Get an incident by id'''
    res_url = api_url + "incidents/{0}".format(id)
    req = requests.get(res_url,auth=TokenAuth(api_token))
    return req.json()

def get_log_entries_by_incident(incid):
    '''Get log entries by incident id'''

    from datetime import datetime

    headers = {
        'Authorization': 'Token token={0}'.format(api_token),
        'Content-type': 'application/json',
    }

    r1 = requests.get('{0}incidents/{1}/log_entries?include[]=channel'.format(api_url,incid), headers=headers, stream=True)
    od=list(reversed(r1.json()['log_entries']))
    od_first = od[0]
    res_method = first_notification_time = first_ack_time = 'None'
    od_number_of_notifications = od_number_of_acks = 0
    was_there_an_initial_alert = was_there_an_ack = False
    for ea_logentry in od:
        if ea_logentry['type'] == 'notify':
            od_first_notification = ea_logentry
            was_there_an_initial_alert = True
            first_notification_time = od_first_notification['created_at']
            break
    for ea_logentry in od:
        if ea_logentry['type'] == 'notify':
            od_number_of_notifications += 1
    for ea_logentry in od:
        if ea_logentry['type'] == 'acknowledge':
            was_there_an_ack = True
            first_ack_time = ea_logentry['created_at']
            break
    for ea_logentry in od:
        if ea_logentry['type'] == 'acknowledge':
            od_number_of_acks += 1
    for ea_logentry in od:
        if ea_logentry['type'] == 'resolve':
            res_method = ea_logentry['channel']['type']
    tf="%Y-%m-%dT%H:%M:%SZ"
    time_bet_1stalert_and_1stack = 0
    if not was_there_an_initial_alert or not was_there_an_ack:
        time_bet_1stalert_and_1stack = 'None'
    else:
        time_bet_1stalert_and_1stack = datetime.strptime(first_ack_time, tf) - datetime.strptime(first_notification_time, tf)
        time_bet_1stalert_and_1stack = "{0}m{1}s".format(str(time_bet_1stalert_and_1stack).split(":")[1],str(time_bet_1stalert_and_1stack).split(":")[2])
    
    return {'time_bet': time_bet_1stalert_and_1stack, 'num_noti': str(od_number_of_notifications), 'num_acks': str(od_number_of_acks), 'res_method': res_method}

def get_reports(date,days,opts):
    '''Get detailed reports'''

    start_date = (date - datetime.timedelta(days=days+1)).strftime(date_format)
    end_date = (date - datetime.timedelta(days=days)).strftime(date_format)
    info = get_incidents(start_date,end_date)

    byservice = 0
    byhost = 0
    details = ""
    byemail = 0

    rbynagios = 0
    rbytimeout = 0
    rbyhuman = 0
    for incident in info['incidents']:
        escanum = incident['number_of_escalations']
        incid = incident['id']
        
        if incident['trigger_type'] == "email_trigger":
            inchost = "byEmail"
            byemail = byemail + 1
            subject = incident['trigger_summary_data']['subject']
        else:
            inchost = incident['trigger_summary_data']['HOSTNAME']
            if incident['trigger_summary_data']['pd_nagios_object'] == "service":
                byservice = byservice + 1
                subject = incident['trigger_summary_data']['SERVICEDESC']
            elif incident['trigger_summary_data']['pd_nagios_object'] == "host":
                byhost = byhost + 1
                subject = "DOWN"

        extra_info = get_log_entries_by_incident(incid)
        res_method = extra_info['res_method']
        if res_method == "nagios":
            rbynagios = rbynagios + 1
        if res_method == "timeout":
            rbytimeout = rbytimeout + 1
        if res_method == "website":
            rbyhuman = rbyhuman + 1

        if not opts['days']:
            time_bet_1stalert_and_1stack = extra_info['time_bet']
            number_of_notifications = extra_info['num_noti']
            number_of_acks = extra_info['num_acks']

            details = details + "\nid: {0}  host: {1}  subject: {2}\n  escalates_num: {3}\n  time_bet_1stAlert_and1stAck: {4}\n  number_of_notifications: {5}\n  number_of_acks: {6}\n  resolve_by: {7}\n"\
                      .format(incid,inchost,subject,escanum,time_bet_1stalert_and_1stack,number_of_notifications,number_of_acks,res_method)

    return {'date':start_date,'total':info['total'],'byservice':byservice,'byhost':byhost,'byemail':byemail,'details':details, 'rbynagios':rbynagios, 'rbytimeout':rbytimeout, 'rbyhuman':rbyhuman }

if __name__=='__main__':
    argv_len = len(sys.argv)
    if argv_len < 2:
        os.system(__file__ + " -h")
        sys.exit(1)
    opts = parse_opts()
    daterex = "^[0-9]{4}-(((0[13578]|(10|12))-(0[1-9]|[1-2][0-9]|3[0-1]))|(02-(0[1-9]|[1-2][0-9]))|((0[469]|11)-(0[1-9]|[1-2][0-9]|30)))$"

    if opts['days']:
        for days in range(opts['days']):
            date = datetime.datetime.today()
            reports = get_reports(date,days,opts)
            print "DATE: {0}  TOTAL: {1}".format(reports['date'],reports['total'])
            print "Trigger: byservice: {0}  byhost: {1}  byemail: {2}".format(reports['byservice'],reports['byhost'],reports['byemail'])
            print "Resolve: bynagios: {0}  bytimeout: {1}  byhuman: {2}\n".format(reports['rbynagios'],reports['rbytimeout'],reports['rbyhuman'])
    elif opts['date']:
        if re.match(daterex,opts['date']):
            date = datetime.datetime.strptime(opts['date'],"%Y-%m-%d")
            reports = get_reports(date,-1,opts)
            print "DATE: {0}  TOTAL: {1}".format(reports['date'],reports['total'])
            print "Trigger: byservice: {0}  byhost: {1}  byemail: {2}".format(reports['byservice'],reports['byhost'],reports['byemail'])
            print "Resolve: bynagios: {0}  bytimeout: {1}  byhuman: {2}".format(reports['rbynagios'],reports['rbytimeout'],reports['rbyhuman'])
            print "{0}".format(reports['details'])
        else:
            print "The date is incorrect"
