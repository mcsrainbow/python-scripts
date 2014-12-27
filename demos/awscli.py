#!/usr/bin/env python
#-*- coding:utf-8 -*-

# Author: Dong Guo
# Last Modified: 2014/12/26

import os
import sys
import json
import time

# import boto to control aws
try:
    import boto
    import boto.ec2
    import boto.ec2.elb
except ImportError:
    sys.stderr.write("ERROR: Requires boto, try 'pip install boto'")
    sys.exit(1)

# global settings
AWS_ACCESS_KEY_ID='YOUR_AWS_ACCESS_KEY_ID'
AWS_SECRET_ACCESS_KEY='YOUR_AWS_SECRET_ACCESS_KEY'
SECONDARY_VOLUME_DEVICE='/dev/sdf'

def parse_opts():
    """Help messages (-h, --help)"""

    import textwrap
    import argparse

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
        '''
        examples:
          {0} --create --region us-west-1 --instance_name idc1-server2 --image_id ami-30f01234 --instance_type t1.micro \\
                       --key_name idc1-keypair1 --security_group_ids sg-eaf01234f --subnet_id subnet-6d901234
          {0} --create --region us-west-1 --instance_name idc1-server3 --image_id ami-30f01234 --instance_type t1.micro \\
                       --key_name idc1-keypair1 --security_group_ids sg-eaf01234f --subnet_id subnet-6d901234 \\
                       --volume_size 10 --volume_type gp2 --volume_zone us-west-1a --volume_delete_on_termination \\
                       --load_balancer_name idc1-elb1 --private_ip_address 172.16.2.23
          {0} --clone --region us-west-1 --src_instance_name idc1-server1 --dest_instance_name idc1-server2
          {0} --clone --region us-west-1 --src_instance_name idc1-server1 --dest_instance_name idc1-server3 \\
                      --private_ip_address 172.16.2.23
          {0} --terminate --region us-west-1 --instance_name idc1-server3
          {0} --terminate --region us-west-1 --instance_id i-01234abc
          {0} --terminate --region us-west-1 --instance_id i-01234abc --quick
          ...
        '''.format(__file__)
        ))

    exclusion = parser.add_mutually_exclusive_group(required=True)
    exclusion.add_argument('--create', action="store_true", default=False, help='create instance')
    exclusion.add_argument('--clone', action="store_true", default=False, help='clone instance')
    exclusion.add_argument('--terminate', action="store_true", default=False, help='terminate instance')

    parser.add_argument('--region', type=str, required=True)
    parser.add_argument('--instance_name', type=str)
    parser.add_argument('--image_id', type=str)
    parser.add_argument('--instance_type', type=str)
    parser.add_argument('--key_name', type=str)
    parser.add_argument('--security_group_ids', type=str)
    parser.add_argument('--subnet_id', type=str)
    parser.add_argument('--src_instance_name', type=str)
    parser.add_argument('--dest_instance_name', type=str)
    parser.add_argument('--private_ip_address', type=str)
    parser.add_argument('--instance_id', type=str)
    parser.add_argument('--volume_size', type=int, help='in GiB')
    parser.add_argument('--volume_type', type=str, choices=['standard','io1','gp2'])
    parser.add_argument('--volume_zone', type=str)
    parser.add_argument('--volume_iops', type=int)
    parser.add_argument('--volume_delete_on_termination', action="store_true", default=False, help='delete volumes on termination')
    parser.add_argument('--load_balancer_name', type=str)
    parser.add_argument('--quick', action="store_true", default=False, help='no wait on termination')

    args = parser.parse_args()
    return {'create':args.create, 'clone':args.clone, 'terminate':args.terminate, 
            'region':args.region, 'instance_name':args.instance_name, 'image_id':args.image_id,
            'instance_type':args.instance_type, 'key_name':args.key_name, 'security_group_ids':args.security_group_ids,
            'subnet_id':args.subnet_id, 'src_instance_name':args.src_instance_name, 'dest_instance_name':args.dest_instance_name,
            'private_ip_address':args.private_ip_address, 'instance_id':args.instance_id,
            'volume_size':args.volume_size, 'volume_type':args.volume_type, 'volume_zone':args.volume_zone,
            'volume_iops':args.volume_iops, 'volume_delete_on_termination':args.volume_delete_on_termination, 
            'load_balancer_name':args.load_balancer_name, 'quick':args.quick}

def create_instance(region,instance_name,image_id,instance_type,key_name,security_group_ids,subnet_id,
                    private_ip_address,volume_size,volume_type,volume_zone,
                    volume_iops,volume_delete_on_termination,load_balancer_name):
    conn = boto.ec2.connect_to_region(region,
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

    # check if instance already exists
    existing_reservations = conn.get_all_instances(filters={"tag:Name": "{0}".format(instance_name)})
    for existing_reservation in existing_reservations:
        existing_instance = existing_reservation.instances[0]
        if existing_instance:
            print "instance_name: {0} already exists".format(instance_name)
            return False

    # launch instance
    print "1. Launching instance: {0}".format(instance_name)
    reservation = conn.run_instances(image_id,instance_type=instance_type,key_name=key_name,
                                     security_group_ids=security_group_ids,
                                     subnet_id=subnet_id,private_ip_address=private_ip_address,
                                     instance_initiated_shutdown_behavior="stop")

    # get instance info
    instance = reservation.instances[0]

    # set instance name
    print """2. Creating tag as instance name: {"Name": %s}""" % (instance_name)
    conn.create_tags(instance.id,{"Name":instance_name})
    while instance.state == u'pending':
        time.sleep(10)
        instance.update()
        print "Instance state: {1}".format(instance_name, instance.state)

    if volume_delete_on_termination:
        root_device = instance.root_device_name
        instance.modify_attribute('blockDeviceMapping', {root_device: True})

    # create volume
    if volume_size and volume_type:
        print "3. Creating secondary volume for instance: {0} as {1} {2}G".format(instance_name,volume_type,volume_size)
        volume = conn.create_volume(volume_size,zone=volume_zone,volume_type=volume_type,iops=volume_iops)
        while volume.status == u'creating':
            time.sleep(10)
            volume.update()
            print "Volume status: {0}".format(volume.status)

        # attache volume
        volume_device = SECONDARY_VOLUME_DEVICE
        print "4. Attaching volume: {0} to instance: {1} as device: {2}".format(volume.id,instance_name,volume_device)
        conn.attach_volume(volume.id,instance.id,volume_device)
        if volume_delete_on_termination:
            instance.modify_attribute('blockDeviceMapping', {volume_device: True})

    # register load balancer
    if load_balancer_name:
        elb_conn = boto.ec2.elb.connect_to_region(region,
                                                  aws_access_key_id=AWS_ACCESS_KEY_ID,
                                                  aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

        elb = elb_conn.get_all_load_balancers(load_balancer_name)[0]
        print '5. Adding instance: {0} to ELB: {1}'.format(instance_name, elb.name)
        elb.register_instances(instance.id)

    return True

def clone_instance(region,src_instance_name,dest_instance_name,private_ip_address):
    conn = boto.ec2.connect_to_region(region,
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

    reservations = conn.get_all_instances(filters={"tag:Name": "{0}".format(src_instance_name)})
    reservation = reservations[0]
    src_instance = reservation.instances[0]

    instance_name = dest_instance_name
    image_id = src_instance.image_id
    instance_type = src_instance.instance_type
    key_name = src_instance.key_name
    security_group_ids = src_instance.groups[0].id.split()
    subnet_id = src_instance.subnet_id
    private_ip_address = private_ip_address
    volume_delete_on_termination = src_instance.block_device_mapping[SECONDARY_VOLUME_DEVICE].delete_on_termination

    src_volumes = conn.get_all_volumes(filters={'attachment.instance-id': "{0}".format(src_instance.id)})
    volume_size = None
    volume_type = None
    volume_zone = None
    volume_iops = None
    for src_volume in src_volumes:
        if src_volume.attach_data.device == SECONDARY_VOLUME_DEVICE:
            volume_size = src_volume.size
            volume_type = src_volume.type
            volume_zone = src_volume.zone
            if volume_type == "io1":
                volume_iops = src_volume.iops

    elb_conn = boto.ec2.elb.connect_to_region(region,
                                              aws_access_key_id=AWS_ACCESS_KEY_ID,
                                              aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

    elbs = elb_conn.get_all_load_balancers()
    load_balancer_name = None
    for elb in elbs:
        for elb_instance in elb.instances:
            if src_instance.id == elb_instance.id:
                load_balancer_name = elb.name

    create_instance(region,instance_name,image_id,instance_type,key_name,security_group_ids,subnet_id,
                    private_ip_address,volume_size,volume_type,volume_zone,volume_iops,
                    volume_delete_on_termination,load_balancer_name)

    return True

def terminate_instance(region,instance_name,instance_id,quick):
    conn = boto.ec2.connect_to_region(region,
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

    if instance_name:
        reservations = conn.get_all_instances(filters={"tag:Name": "{0}".format(instance_name)})
        for reservation in reservations:
            instance = reservation.instances[0]
    
            instance_id_list = instance.id.split()
            print "Terminating instance: {0} id: {1}".format(instance_name, instance.id)
            conn.terminate_instances(instance_ids=instance_id_list)
            if not quick:
                while instance.state != u'terminated':
                    time.sleep(20)
                    instance.update()
                    print "Instance state: {0}".format(instance.state)

    if instance_id:
        instance_id_list = instance_id.split()
        print "Terminating instance by id: {0}".format(instance_id)
        conn.terminate_instances(instance_ids=instance_id_list)
        reservations = conn.get_all_reservations(instance_id)
        reservation = reservations[0]
        instance = reservation.instances[0]
        if not quick:
            while instance.state != u'terminated':
                time.sleep(20)
                instance.update()
                print "Instance state: {0}".format(instance.state)
    
    return True

if __name__=='__main__':
    argv_len = len(sys.argv)
    if argv_len < 2:
        os.system(__file__ + " -h")
        sys.exit(1)
    opts = parse_opts()

    if opts['create']:
        create_instance(opts['region'],opts['instance_name'],opts['image_id'],opts['instance_type'],
                        opts['key_name'],opts['security_group_ids'].split(),opts['subnet_id'],opts['private_ip_address'],
                        opts['volume_size'],opts['volume_type'],opts['volume_zone'],opts['volume_iops'],
                        opts['volume_delete_on_termination'],opts['load_balancer_name'])

    if opts['clone']:
        clone_instance(opts['region'],opts['src_instance_name'],opts['dest_instance_name'],opts['private_ip_address'])
            
    if opts['terminate']:
        terminate_instance(opts['region'],opts['instance_name'],opts['instance_id'],opts['quick'])
