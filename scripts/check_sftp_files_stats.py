#!/usr/bin/env python
#-*- coding:utf-8 -*-

# Description: Get list and time received results of SFTP files
# Author: Damon Guo

import os
import sys
import yaml
import datetime

def get_results(sftp_opts,folder_list,stats_yml):
    """Get results with given parameters"""

    import pysftp
    import time

    host = sftp_opts['host']
    user = sftp_opts['user']
    pkey = sftp_opts['pkey']
    port = sftp_opts['port']

    cnopts = pysftp.CnOpts()
    cnopts.hostkeys = None

    sftp = pysftp.Connection(host, username=user, private_key=pkey, port=port, cnopts=cnopts)

    file_list = []
    dir_list = []
    other_list = []

    def store_file_list(file_name):
        file_list.append(file_name)

    def store_dir_list(dir_name):
        dir_list.append(dir_name)

    def store_other_list(other_name):
        other_list.append(other_name)

    now_timestamp = int(time.time())
    now_time = datetime.datetime.fromtimestamp(now_timestamp).strftime('%Y-%m-%d %H:%M:%S')

    for folder in folder_list:
        sftp.walktree("{0}/{0}".format(folder),store_file_list,store_dir_list,store_other_list,recurse=True)

    suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    def humansize(nbytes):
        i = 0
        while nbytes >= 1024 and i < len(suffixes)-1:
            nbytes /= 1024.
            i += 1
        j = ('%.2f' % nbytes).rstrip('0').rstrip('.')
        return('{0}{1}'.format(j, suffixes[i]))

    def human_time_duration(seconds):
        time_duration_units = (
            ('day', 60*60*24),
            ('hour', 60*60),
            ('min', 60),
            ('sec', 1)
        )

        if seconds == 0:
            return('inf')
        parts = []
        for unit, div in time_duration_units:
            amount, seconds = divmod(int(seconds), div)
            if amount > 0:
                parts.append('{}{}{}'.format(amount, unit, "" if amount == 1 else "s"))
        return(' '.join(parts))

    with open(stats_yml) as f:
        data_dict = yaml.load(f)
        if not data_dict['stats_results'].has_key("file_list"):
            file_list_pre = []
        else:
            file_list_pre = data_dict['stats_results']['file_list']

    file_list_arrived = set(file_list) - set(file_list_pre)

    stat_list_arrived = []
    for f in list(file_list_arrived):
        f_stat = sftp.lstat(f)

        f_size = humansize(f_stat.st_size)
        f_mtimestamp = f_stat.st_mtime
        f_mtime = datetime.datetime.fromtimestamp(f_mtimestamp).strftime('%Y-%m-%d %H:%M:%S')
        f_seconds_arrived = now_timestamp - f_mtimestamp
        f_time_arrived = human_time_duration(f_seconds_arrived)

        stat_list_arrived.append("{0},{1},{2},{3},{4},{5},{6}".format(f,f_size,f_mtimestamp,f_mtime,now_timestamp,now_time,f_time_arrived))

        #print("{0},{1},{2},{3},{4},{5},{6}".format(f,f_size,f_mtimestamp,f_mtime,now_timestamp,now_time,f_time_arrived))
        print("File '{0}' has arrived in '{1}'".format(f,f_time_arrived))

    data_dict['stats_results']['file_list'] = file_list
    data_dict['stats_results']['stat_list_arrived'] = stat_list_arrived

    return(data_dict)

def csv_save(stats_dir,stat_list_arrived):
    """Save the results as a CSV file"""

    today_str = datetime.date.today().strftime("%Y%m%d")

    stats_csv = "{0}/stats-{1}.csv".format(stats_dir,today_str)

    for item in stat_list_arrived:
        with open(stats_csv, "a") as f:
            f.write("{0}\n".format(item))
        f.close()

    return(stats_csv)

def s3_copy(profile_name,stats_csv,s3_bucket_dir):
    """Copy the stats_csv to S3 bucket"""

    import boto3

    session = boto3.Session(profile_name=profile_name)
    s3_client = session.client('s3')

    s3_bucket_name = s3_bucket_dir.split('/')[0]
    stats_csv_key = stats_csv.split('/')[-1]
    s3_bucket_key = "{0}/{1}".format('/'.join(s3_bucket_dir.split('/')[1:]),stats_csv_key)

    try:
        res = s3_client.upload_file(stats_csv, s3_bucket_name, s3_bucket_key)
    except:
        print("ERROR: Failed to upload '{0}' to 's3://{1}/{2}'".format(stats_csv,s3_bucket_name,s3_bucket_key))
        return(False)
    else:
        print("INFO: Uploaded '{0}' to 's3://{1}/{2}'".format(stats_csv,s3_bucket_name,s3_bucket_key))
        return(True)

def main():
    """The main function"""

    sftp_opts = {}

    sftp_opts['user'] = "username"
    sftp_opts['port'] = 22
    sftp_opts['host'] = "10.8.5.7"
    sftp_opts['pkey'] = "/path/to/sshkey"

    folder_list = ["foo_dirs","bar_dirs"]

    stats_dir = "{0}/stats".format(os.path.abspath(os.path.dirname(sys.argv[0])))
    stats_yml = "{0}/stats.yml".format(stats_dir)

    if not os.path.isdir(stats_dir):
        os.mkdir(stats_dir)

    if not os.path.isfile(stats_yml) or os.stat(stats_yml).st_size == 0:
        with open(stats_yml, "w") as f:
            f.write("stats_results: {}")

    print("INFO: Checking arrived SFTP files...")
    data_dict = get_results(sftp_opts,folder_list,stats_yml)
    with open(stats_yml, 'w') as f:
        yaml.dump(data_dict, f, default_flow_style=False)

    stat_list_arrived = data_dict['stats_results']['stat_list_arrived']
    if len(stat_list_arrived) == 0:
        print("INFO: No any file arrived since last check")
        return(0)
    else:
        stats_csv = csv_save(stats_dir,stat_list_arrived)

        profile_name = "reports"
        s3_bucket_dir = "heylinux-reports/sftp/stats"
        if s3_copy(profile_name,stats_csv,s3_bucket_dir):
            return(0)
        else:
            return(1)

if __name__=='__main__':
    sys.exit(main())
