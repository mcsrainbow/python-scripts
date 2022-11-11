#!/usr/bin/env python3
#-*- coding:utf-8 -*-

# Description: Update CloudWatch Log Groups Retention
# Author: Damon Guo

import os
import sys
import boto3

def parse_opts():
    """Help messages(-h, --help)"""

    import textwrap
    import argparse

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
        '''
        examples:
          {0} -p /aws/lambda -d 30
          {0} -p /aws/lambda/function-name -d 7
        '''.format(__file__)
        ))

    parser.add_argument('-p', metavar='prefix', type=str, required=True, help='The prefix of CloudWatch Log Groups')
    parser.add_argument('-d', metavar='days', type=int, required=True, help='Retention in days')

    args = parser.parse_args()
    return({'prefix':args.p, 'days':args.d})

def update_retention(profile_name,prefix,days):
    """Update CloudWatch log groups retention to specific days"""

    session = boto3.Session(profile_name=profile_name)
    logs_client = session.client('logs')
    paginator = logs_client.get_paginator('describe_log_groups')

    log_groups_list=[]
    for page in paginator.paginate():
        for log_group in page['logGroups']:
            log_groups_list.append(log_group['logGroupName'])

    for log_group in log_groups_list:
        if log_group.startswith(prefix):
            policy_res=logs_client.put_retention_policy(
                logGroupName=log_group,
                retentionInDays=days
            )
            if policy_res['ResponseMetadata']['HTTPStatusCode'] == 200:
                print("INFO: Updated log_group: {0} with retention days: {1}".format(log_group,days))
            else:
                print("ERROR: Failed to update log_group: {0}, return code: {1}".format(log_group,policy_res['ResponseMetadata']['HTTPStatusCode']))
                return(False)

    return(True)

def main():
    if len(sys.argv) < 2:
        os.system(__file__ + " -h")
        return(2)

    opts = parse_opts()
    profile_name = "admin"

    prefix = opts['prefix']
    days = opts['days']

    if update_retention(profile_name,prefix,days):
        return(0)
    else:
        return(1)

if __name__=='__main__':
    sys.exit(main())
