#!/usr/bin/env python
#-*- coding:utf-8 -*-

# Description: Generate Cost Explorer report by Cost Allocation Tag
# Author: Damon Guo

import os
import sys
import datetime
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
          {0} -k user:Application
          {0} -k user:Application -m 2022-07
        '''.format(__file__)
        ))

    parser.add_argument('-k', metavar='tag_key', type=str, required=True, help='The tag key of cost_allocation_tag')
    parser.add_argument('-m', metavar='month', type=str, help='month [default: last month]')

    if len(sys.argv) < 2:
        parser.print_help()
        sys.exit(2)

    args = parser.parse_args()
    return({'tag_key':args.k, 'month':args.m})

def get_costs(start_date,end_date,tag_key,costs_list,nextpage_token):
    """Get monthly costs by cost_allocation_tag key"""

    client = boto3.client('ce')

    if nextpage_token:
        res = client.get_cost_and_usage(
            TimePeriod={
                'Start': start_date,
                'End': end_date
            },
            Granularity='MONTHLY',
            Metrics=[
                'BlendedCost',
            ],
            GroupBy=[
                {
                    'Type': 'DIMENSION',
                    'Key': 'SERVICE'
                },
                {
                    'Type': 'TAG',
                    'Key': tag_key
                },
            ],
            NextPageToken=nextpage_token
        )
    else:
        res = client.get_cost_and_usage(
            TimePeriod={
                'Start': start_date,
                'End': end_date
            },
            Granularity='MONTHLY',
            Metrics=[
                'BlendedCost',
            ],
            GroupBy=[
                {
                    'Type': 'DIMENSION',
                    'Key': 'SERVICE'
                },
                {
                    'Type': 'TAG',
                    'Key': tag_key
                },
            ]
        )

    if "NextPageToken" in res:
        nextpage_token = res['NextPageToken']

    for item in res['ResultsByTime'][0]['Groups']:
        costs_list.append(item)

    return({'costs_list':costs_list, 'nextpage_token':nextpage_token})

def get_results(opts):
    """Get results with given parameters"""

    if opts['month']:
        last_month_str = opts['month']
        last_month_y = last_month_str.split('-')[0]
        last_month_m = last_month_str.split('-')[1]
    else:
        date_today = datetime.date.today()
        date_first = date_today.replace(day=1)
        last_month = date_first - datetime.timedelta(days=1)
        last_month_y = last_month.strftime("%Y")
        last_month_m = last_month.strftime("%m")

    last_month_start_date = "{0}-{1}-01".format(last_month_y,last_month_m)
    last_month_str = "{0}-{1}".format(last_month_y,last_month_m)

    if int(last_month_m) == 12:
        next_month_y = int(last_month_y) + 1
        next_month_m = 1
    else:
        next_month_y = last_month_y
        next_month_m = int(last_month_m) + 1

    next_month_first_date = "{0}-{1:02d}-01".format(next_month_y,next_month_m)
    last_month_end_date = next_month_first_date

    init_costs_list = []
    init_costs_data = get_costs(last_month_start_date,last_month_end_date,opts['tag_key'],init_costs_list,nextpage_token="")

    costs_list = init_costs_data["costs_list"]
    nextpage_token = init_costs_data["nextpage_token"]

    while nextpage_token:
        costs_data = get_costs(last_month_start_date,last_month_end_date,opts['tag_key'],costs_list,nextpage_token)
        costs_list = costs_data["costs_list"]
        nextpage_token = costs_data["nextpage_token"]

    return({'last_month_str':last_month_str, 'costs_list':costs_list})

def csv_save(costs_csv_dir,costs_results):
    """Save the costs list as a CSV file"""

    costs_list = costs_results['costs_list']
    costs_month_str = costs_results['last_month_str']

    cost_dict = {}
    for item in costs_list:
        item_srv = item['Keys'][0]
        item_app = item['Keys'][1].split('$')[1]
        item_usd = item['Metrics']['BlendedCost']['Amount']

        if item_app:
            app_name = "Tag: {0}".format(item_app)
        else:
            app_name = "Service: {0}".format(item_srv)
        if app_name in cost_dict:
            cost_dict[app_name].append(float(item_usd))
        else:
            cost_dict[app_name] = [float(item_usd)]

    csv_dict = {}
    csv_dict_raw = {}
    for k,v in cost_dict.items():
        for i in ["Amazon ", "Amazon", "AWS ", "AWS"]:
            k = k.replace(i,"")
        app_name = k
        app_cost = sum(v)
        csv_dict_raw[app_name] = app_cost
        # ignore costs in [0,1]
        if app_cost > 1 or app_cost < 0:
            csv_dict[app_name] = round(app_cost,2)

    total_cost = sum(csv_dict_raw.values())
    csv_dict['Total'] = round(total_cost,2)

    costs_csv = "{0}/costs-{1}.csv".format(costs_csv_dir,costs_month_str)

    if os.path.exists(costs_csv):
        open(costs_csv, 'w').close()

    for k,v in csv_dict.items():
        with open(costs_csv, "a") as f:
            f.write("{0},{1}\n".format(k,v))
        f.close()

    return(costs_csv)

def s3_copy(profile_name,costs_csv,s3_bucket_dir,last_month_str):
    """Copy the costs_csv to S3 bucket"""

    session = boto3.Session(profile_name=profile_name)
    s3_client = session.client('s3')

    s3_bucket_name = s3_bucket_dir.split('/')[0]
    costs_csv_key = costs_csv.split('/')[-1]
    s3_bucket_key = "{0}/{1}/{2}".format('/'.join(s3_bucket_dir.split('/')[1:]),last_month_str,costs_csv_key)

    try:
        res = s3_client.upload_file(costs_csv, s3_bucket_name, s3_bucket_key)
    except:
        print("ERROR: Failed to upload '{0}' to 's3://{1}/{2}'".format(costs_csv,s3_bucket_name,s3_bucket_key))
        return(False)
    else:
        print("INFO: Uploaded '{0}' to 's3://{1}/{2}'".format(costs_csv,s3_bucket_name,s3_bucket_key))
        return(True)

def main():
    opts = parse_opts()

    costs_csv_dir = "{0}/costs_csv".format(os.path.abspath(os.path.dirname(sys.argv[0])))
    if not os.path.isdir(costs_csv_dir):
        os.mkdir(costs_csv_dir)

    costs_results = get_results(opts)
    costs_csv = csv_save(costs_csv_dir,costs_results)

    profile_name = "reports"
    s3_bucket_dir = "heylinux-reports/aws/costs"
    last_month_str = costs_results['last_month_str']
    if s3_copy(profile_name,costs_csv,s3_bucket_dir,last_month_str):
        return(0)
    else:
        return(1)

if __name__=='__main__':
    sys.exit(main())
