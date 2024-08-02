#!/usr/bin/env python
#-*- coding:utf-8 -*-

# Author: Dong Guo
# Last Modified: 2015/07/14

import sys
import json
import time

# import boto to control aws
try:
    import boto
    import boto.ec2
    import boto.ec2.volume
except ImportError:
    sys.stderr.write("ERROR: Requires boto, try 'pip install boto'")
    sys.exit(1)

# global settings
AWS_ACCESS_KEY_ID = 'YOUR_AWS_ACCESS_KEY_ID'
AWS_SECRET_ACCESS_KEY = 'YOUR_AWS_SECRET_ACCESS_KEY'

def parse_opts():
    """Help messages (-h, --help)"""

    import textwrap
    import argparse

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
        '''
        examples:
          {0} --region us-east-1 --instance_name cp1e --volume_device /dev/sdf --retention_type day --retention_count 3
          ...
        '''.format(__file__)
        ))

    parser.add_argument('--region', type=str, required=True)
    parser.add_argument('--instance_name', type=str, required=True)
    parser.add_argument('--volume_device', type=str, required=True)
    parser.add_argument('--retention_type', type=str, choices=['day','hour','minute'], required=True)
    parser.add_argument('--retention_count', type=int, required=True)

    if len(sys.argv) < 2:
        parser.print_help()
        sys.exit(2)

    args = parser.parse_args()
    return {'region':args.region, 'instance_name':args.instance_name, 'volume_device':args.volume_device,
            'retention_type':args.retention_type, 'retention_count':args.retention_count}

def update_snapshot(region,instance_name,volume_device,retention_type,retention_count):
    """Create and delete snapshot"""

    # import time libraries
    from datetime import datetime
    import calendar

    if retention_type == 'day':
        retention_timestamp = 24 * 60 * 60 * retention_count
    if retention_type == 'hour':
        retention_timestamp = 60 * 60 * retention_count
    if retention_type == 'minute':
        retention_timestamp = 60 * retention_count

    conn = boto.ec2.connect_to_region(region,
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

    # check if instance already exists
    existing_reservations = conn.get_all_instances(filters={"tag:Name": "{0}".format(instance_name)})
    for existing_reservation in existing_reservations:
        existing_instance = existing_reservation.instances[0]
        if not existing_instance:
            print "instance_name: {0} does not exist".format(instance_name)
            return False

    # get instance info then create and delete snapshot
    volume_device_short = opts['volume_device'].split("/")[2]
    instance_volumes = conn.get_all_volumes(filters={'attachment.instance-id': "{0}".format(existing_instance.id)})
    for instance_volume in instance_volumes:
        if instance_volume.attach_data.device == opts['volume_device']:
            latest_snapshot = instance_volume.create_snapshot()
            if latest_snapshot:
                latest_snapshot_name = "{0}_{1}_{2}".format(opts['instance_name'],volume_device_short,datetime.now().strftime("%Y%m%d%H%M%S"))
                conn.create_tags(latest_snapshot.id,{"Name":latest_snapshot_name})
                print '''Created snapshot: "{0}"'''.format(latest_snapshot_name)

                snapshots = instance_volume.snapshots()
                for snapshot in snapshots:
                    if 'Name' in snapshot.tags.keys():
                        if "{0}_{1}_".format(opts['instance_name'],volume_device_short) in snapshot.tags['Name']:
                            snapshot_creation_date = snapshot.tags['Name'].split("_")[2]
                            snapshot_creation_timestamp = calendar.timegm(datetime.strptime(snapshot_creation_date,"%Y%m%d%H%M%S").utctimetuple())
                            snapshot_retention_timestamp = calendar.timegm(datetime.now().utctimetuple()) - retention_timestamp
                            if snapshot_retention_timestamp > snapshot_creation_timestamp:
                                snapshot.delete()
                                print '''Deleted snapshot: "{0}"'''.format(snapshot.tags['Name'])

    return True

if __name__ == '__main__':
    opts = parse_opts()
    if "/dev/" not in opts['volume_device']:
        print '''The volume_device should start with "/dev/".'''
        sys.exit(1)

    update_snapshot(opts['region'],opts['instance_name'],opts['volume_device'],opts['retention_type'],opts['retention_count'])
