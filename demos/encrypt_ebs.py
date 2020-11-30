#!/usr/bin/env python
#-*- coding:utf-8 -*-
#
# Encrypt the EBS Volumes of EC2 Instance
# Author: Damon Guo
# Last Modified: 11/26/2020

import os
import sys
import json
from datetime import datetime
import boto3
import textwrap

REGION_NAME = 'ap-east-1'

def parse_opts():
    """Help messages(-h, --help)."""
    
    import argparse

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
        '''
        examples:
          {0} -n heylinux-sandbox-server-1 -k cmk-heylinux-sandbox-app-1
        '''.format(__file__)
        ))

    parser.add_argument('-n', metavar='name', type=str, required=True, help='instance tag name')
    parser.add_argument('-k', metavar='key', type=str, required=True, help='alias of CMK')

    args = parser.parse_args()
    return {'name':args.n, 'key':args.k}

def single_yes_or_no_question(question, default_no=True):
    choices = ' [y/N]: ' if default_no else ' [Y/n]: '
    default_answer = 'n' if default_no else 'y'
    reply = str(input(question + choices)).lower().strip() or default_answer
    if reply[0] == 'y':
        return True
    if reply[0] == 'n':
        return False
    else:
        return False if default_no else True

def show_done_msg():
    done_msg=textwrap.dedent('''\
        DONE: Please manually take the actions as below:
              1. Verify the attached volumes of instance via AWS Web Console, ensure they are encrypted with correct CMKs
              2. Start the instance via AWS Web Console
              3. Login the instance via SSH/RDP, verify the services running on the instance
               
              If anything does NOT work properly:
              1. Troubleshoot the issues
              2. Fallback with previous nonkms volumes if cannot fix the issues''')
    print(done_msg)
    
    return True

def encrypt_ebs(opts):
    """Encrypt the EBS volumes of EC2 instance."""

    ec2_c = boto3.client('ec2', region_name=REGION_NAME)
    ec2_r = boto3.resource('ec2', region_name=REGION_NAME)

    ec2_res = ec2_c.describe_instances(Filters=[{'Name': 'tag:Name','Values': [opts['name']]}])

    # get instance id
    if len(ec2_res['Reservations'][0]['Instances']) > 1:
        print("ERROR: Found more than one instance with tag:Name: {0}".format(opts['name']))
        return False

    instance_id = ec2_res['Reservations'][0]['Instances'][0]['InstanceId']
    instance = ec2_r.Instance(instance_id)

    # get CMK id
    kms_c = boto3.client('kms', region_name=REGION_NAME)
    kms_res = kms_c.list_aliases()
    for kms_alias_item in kms_res['Aliases']:
        if kms_alias_item['AliasName'] == "alias/{0}".format(opts['key']):
            cmk_id = kms_alias_item['TargetKeyId']                                                                                               
            break

    if cmk_id is None:
        print("ERROR: No such CMK: {0}".format(opts['key']))
        return False
   
    # skip if attached volumes already encrypted
    volume_encrypted_count = 0
    for volume_item in ec2_res['Reservations'][0]['Instances'][0]['BlockDeviceMappings']:
        volume_device = volume_item['DeviceName']
        volume_id = volume_item['Ebs']['VolumeId']
        volume_res = ec2_r.Volume(volume_id)

        volume_kms_key_id = ''
        if volume_res.kms_key_id is not None:
            volume_kms_key_id = volume_res.kms_key_id.split('/')[-1]

        if volume_res.encrypted == True and volume_kms_key_id == cmk_id:
            print("INFO: Found attached volume: {0} with CMK: {1} encrypted already".format(volume_device,opts['key']))
            volume_encrypted_count += 1
        elif volume_res.encrypted == True and volume_kms_key_id != cmk_id:
            print("NOTICE: Found attached volume: {0} with different CMK: {1} encrypted".format(volume_device,volume_kms_key_id))
            if single_yes_or_no_question("Do you want to continue?") == False:
                return False

    if volume_encrypted_count > 0:
        print("SKIPPED: volume_encrypted_count is greater than 0")
        return True
   
    # stop instance if it is running
    if instance.state['Name'] == 'running':
        print("INFO: Stopping the instance: {0} with id: {1}...".format(opts['name'],instance_id))
        ec2_c.stop_instances(InstanceIds=[instance_id])

        # wait until instance is stopped
        print("INFO: Waiting for the instance to be stopped...")
        instance.wait_until_stopped()

    # get attached volumes ids
    volume_dict = {}
    for volume_dict_item in ec2_res['Reservations'][0]['Instances'][0]['BlockDeviceMappings']:
        volume_device = volume_dict_item['DeviceName']
        volume_id = volume_dict_item['Ebs']['VolumeId']

        volume_res = ec2_r.Volume(volume_id)
        volume_az = volume_res.availability_zone
        volume_size = volume_res.size
        volume_type = volume_res.volume_type
        volume_iops = volume_res.iops

        volume_attr = {'device':volume_device, 'az':volume_az, 'size':volume_size, 'type':volume_type, 'iops':volume_iops}

        volume_dict[volume_id] = volume_attr

    print("INFO: volume_dict: {0}".format(json.dumps(volume_dict, indent=2)))

    # check if volume_dict is null
    if len(volume_dict) == 0:
        print("ERROR: No attached volume found in instance, please manually attach the required volumes first")
        return False

    # get snapshots ids and create if not exist
    snapshot_dict = {}
    for volume_id, volume_attr in volume_dict.items():
        date_str = datetime.now().strftime("%Y%m%d%H%M")
        snapshot_name_nonkms = "{0}_nonkms_{1}_{2}".format(opts['name'],volume_attr['device'].split('/')[-1],date_str)
        snapshot_name_nonkms_prefix = "{0}_nonkms_{1}".format(opts['name'],volume_attr['device'].split('/')[-1])

        snapshot_res = ec2_c.describe_snapshots(
            Filters=[
                {
                    'Name': 'tag:Name',
                    'Values': [
                        '{0}_*'.format(snapshot_name_nonkms_prefix)
                    ]
                },
            ]
        )

        if len(snapshot_res['Snapshots']) > 1:
            print("ERROR: Found more than one snapshot with tag:Name prefix: {0}".format(snapshot_name_nonkms_prefix))
            return False
        elif len(snapshot_res['Snapshots']) == 1:
            snapshot_dict[volume_attr['device']] = snapshot_res['Snapshots'][0]['SnapshotId']
        else:
            volume_res = ec2_r.Volume(volume_id)
            snapshot = volume_res.create_snapshot(
                Description='Created by {0}: {1}'.format(snapshot_name_nonkms,volume_id),
                TagSpecifications=[
                    {
                        'ResourceType': 'snapshot',
                        'Tags': [
                            {
                                'Key': 'Name',
                                'Value': snapshot_name_nonkms
                            },
                        ]
                    },
                ]
            )
            print("INFO: Created snapshot: {0} for device: {1}".format(snapshot.id,volume_attr['device']))
            snapshot_dict[volume_attr['device']] = snapshot.id
    
    print("INFO: snapshot_dict: {0}".format(json.dumps(snapshot_dict, indent=2)))

    # get new volumes ids and create with CMK encrypted if not exist
    kms_volume_dict = {}
    for volume_id, volume_attr in volume_dict.items():
        snapshot_id = snapshot_dict[volume_attr['device']]
        date_str = datetime.now().strftime("%Y%m%d%H%M")
        volume_name_kms = "{0}_kms_{1}_{2}".format(opts['name'],volume_attr['device'].split('/')[-1],date_str)
        volume_name_kms_prefix = "{0}_kms_{1}".format(opts['name'],volume_attr['device'].split('/')[-1])

        volume_res = ec2_c.describe_volumes(
            Filters=[
                {
                    'Name': 'tag:Name',
                    'Values': [
                        '{0}_*'.format(volume_name_kms_prefix)
                    ]
                },
            ]
        )

        if len(volume_res['Volumes']) > 1:
            print("ERROR: Found more than one volume with tag:Name prefix: {0}".format(volume_name_kms_prefix))
            return False
        elif len(volume_res['Volumes']) == 1:
            kms_volume_dict[volume_attr['device']] = volume_res['Volumes'][0]['VolumeId']
        else:
            # wait until snapshot is completed
            snapshot_res = ec2_r.Snapshot(snapshot_id)
            print("INFO: snapshot: {0}_state: {1}".format(snapshot_id,snapshot_res.state))
            if snapshot_res.state != 'completed':
                print("INFO: Waiting for snapshot: {0} to be completed for volume: {1}...".format(snapshot_id,volume_name_kms))
                snapshot_res.wait_until_completed()

            if volume_attr['type'] in ['io1','io2']:
                volume_res = ec2_c.create_volume(
                    AvailabilityZone=volume_attr['az'],
                    Size=volume_attr['size'],
                    SnapshotId=snapshot_id,
                    VolumeType=volume_attr['type'],
                    Iops=volume_attr['iops'],
                    Encrypted=True,
                    KmsKeyId=cmk_id,
                    TagSpecifications=[
                        {
                            'ResourceType': 'volume',
                            'Tags': [
                                {
                                    'Key': 'Name',
                                    'Value': volume_name_kms
                                },
                            ]
                        },
                    ],
                    MultiAttachEnabled=False
                )
            else:
                volume_res = ec2_c.create_volume(
                    AvailabilityZone=volume_attr['az'],
                    Size=volume_attr['size'],
                    SnapshotId=snapshot_dict[volume_attr['device']],
                    VolumeType=volume_attr['type'],
                    Encrypted=True,
                    KmsKeyId=cmk_id,
                    TagSpecifications=[
                        {
                            'ResourceType': 'volume',
                            'Tags': [
                                {
                                    'Key': 'Name',
                                    'Value': volume_name_kms
                                },
                            ]
                        },
                    ],
                    MultiAttachEnabled=False
                )

            print("INFO: Created kms_volume: {0} for device: {1}".format(volume_res['VolumeId'],volume_attr['device']))
            kms_volume_dict[volume_attr['device']] = volume_res['VolumeId']
    
    print("INFO: kms_volume_dict: {0}".format(json.dumps(kms_volume_dict, indent=2)))

    # detache nonkms volumes and attache kms_volumes
    for kms_volume_device, kms_volume_id in kms_volume_dict.items():
        kms_volume_res = ec2_c.describe_volumes(VolumeIds=[kms_volume_id])
        if kms_volume_res['Volumes'][0]['State'] in ['in-use', 'deleting', 'deleted', 'error']:
            print("ERROR: Current kms_volume: {0} status is {1}".format(kms_volume_id,kms_volume_res['Volumes'][0]['State']))
            return False
        elif kms_volume_res['Volumes'][0]['State'] == 'creating':
            print("INFO: Current kms_volume: {0} status is {1}, waiting for it to be available...".format(kms_volume_id,kms_volume_res['Volumes'][0]['State']))
            volume_waiter = ec2_c.get_waiter('volume_available')
            volume_waiter.wait(VolumeIds=[kms_volume_id])
   
    for volume_id, volume_attr in volume_dict.items(): 
        volume_res = ec2_c.describe_volumes(VolumeIds=[volume_id])
        if volume_res['Volumes'][0]['State'] == 'in-use':
            print("INFO: Detaching the volume_device: {0}...".format(volume_attr['device']))
            detach_res = ec2_c.detach_volume(
                Device=volume_attr['device'],
                InstanceId=instance_id,
                VolumeId=volume_id
            )
            volume_waiter = ec2_c.get_waiter('volume_available')
            volume_waiter.wait(VolumeIds=[volume_id])

    for kms_volume_device, kms_volume_id in kms_volume_dict.items():
        print("INFO: Attaching the kms_volume_device: {0} with kms_volume_id: {1}...".format(kms_volume_device,kms_volume_id))
        kms_volume_res = ec2_c.attach_volume(
            Device=kms_volume_device,
            InstanceId=instance_id,
            VolumeId=kms_volume_id
        )

    show_done_msg()

    return True

def main():
    if len(sys.argv) < 2:
        os.system(__file__ + " -h")
        return 2

    opts = parse_opts()
    if encrypt_ebs(opts) == True:
        return 0
    else:
        return 2

if __name__ == '__main__':
    sys.exit(main())
