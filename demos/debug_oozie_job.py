#!/usr/bin/env python
#-*- coding:utf-8 -*-

# Description: Get the logsLinks on related nodemanagers for Oozie failed job debuging
# Author: Dong Guo
# Last modified: 2016-09-23

import os
import sys

def parse_opts():
    """Help messages(-h, --help)."""
    
    import textwrap
    import argparse
    
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
        '''
        examples:
          {0} --server idc1-hive1 --job_id 0021221-141009012304672-oozie-oozi-C@7296
          {0} --server idc2-hive1 --job_id 0471242-150120233308020-oozie-oozi-W
          {0} --server idc1-hive1 --job_id 0021221-141009012304672-oozie-oozi-C@7296 --active_rm idc1-rm2
        '''.format(__file__)
        ))
    
    parser.add_argument('--server', type=str, required=True, help='the oozie server address')
    parser.add_argument('--job_id', type=str, required=True, help='the oozie job id')
    parser.add_argument('--active_rm', type=str, help='the active resourcemanager server address')
    args = parser.parse_args()

    return {'server':args.server, 'job_id':args.job_id, 'active_rm':args.active_rm}

class _AttributeString(str):
    """
    Simple string subclass to allow arbitrary attribute access.
    """
    @property
    def stdout(self):
        return str(self)

def remote(cmd, hostname, username, password=None, pkey=None, pkey_type="rsa", port=22):

    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import paramiko
    
    p = paramiko.SSHClient()
    p.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    if pkey is not None:
        if pkey_type == "dsa":
            pkey = paramiko.DSSKey.from_private_key_file(pkey)
        else:
            pkey = paramiko.RSAKey.from_private_key_file(pkey)
        p.connect(hostname=hostname, username=username, pkey=pkey, port=port)
    else:
        p.connect(hostname=hostname, username=username, password=password, port=port)

    (stdin, stdout, stderr) = p.exec_command(cmd)

    stdout_str=""
    stderr_str=""
    for line in stdout.readlines():
        stdout_str = stdout_str + line
    for line in stderr.readlines():
        stderr_str = stderr_str + line

    out = _AttributeString(stdout_str.strip() if stdout else "")
    err = _AttributeString(stderr_str.strip() if stderr else "")

    out.cmd = cmd
    out.failed = False
    out.return_code = stdout.channel.recv_exit_status()
    out.stderr = err
    if out.return_code != 0:
        out.failed = True
    out.succeeded = not out.failed

    p.close()
    return out

def get_ports(hostname,nm_port):
    username = "root"
    pkey = "/root/.ssh/id_rsa"
    pkey_type = "rsa"

    nm_pid = remote("""netstat -lntp |grep -w %s |awk '{print $NF}' |cut -d/ -f1""" % (nm_port),
                    hostname=hostname,username=username,pkey=pkey,pkey_type=pkey_type)
    if nm_pid:
        ports = remote("""netstat -lntp |grep -w %s |awk '{print $4}' |sed s/://g |grep -Ev '8040|8042|13562' |xargs""" % (nm_pid),
                       hostname=hostname,username=username,pkey=pkey,pkey_type=pkey_type)
        if ports:
            return ports

    return False

def oozie_debug(server,job_id,active_rm):
    
    import requests
    import json

    if "oozie-oozi-C" in job_id:
        c_job_id = job_id
        c_req = requests.get('http://{0}:11000/oozie/v1/job/{1}'.format(server,c_job_id))
        c_req_dict = c_req.json()
        if 'externalId' not in c_req_dict:
            print "ERROR: No such key: 'externalId', please verify the 'job_id'"
            return False

        w_job_id = c_req_dict['externalId']
        print "externalId: {0}".format(w_job_id)
        if not w_job_id:
            return False
   
    elif "oozie-oozi-W" in job_id:
        w_job_id = job_id

    else:
        print "ERROR: Please verify the 'job_id'"
        return False
   
    w_req = requests.get('http://{0}:11000/oozie/v1/job/{1}'.format(server,w_job_id))
    w_req_dict = w_req.json()
    job_user = w_req_dict['user']
    for item_id in range(0,len(w_req_dict['actions'])):
        item_dict = w_req_dict['actions'][item_id]
        print "status: '{0}', name: '{1}'".format(item_dict['status'],item_dict['name'])
        if item_dict['status'] in ['ERROR','KILLED']:
            print "  consoleUrl: '{0}'".format(item_dict['consoleUrl'])
            if item_dict['status'] == 'ERROR' and item_dict['consoleUrl']:
                if 'proxy/application' not in item_dict['consoleUrl']:
                    print "  *NOTE*: The above consoleUrl from API may not correct, please manually check the URL:'http://{0}:11000/oozie'.".format(server)
                else:
                    rm_server = item_dict['consoleUrl'].split('http://')[1].split('/')[0].replace('8100','19888').split(':')[0]
                    rm_server_port = item_dict['consoleUrl'].split('http://')[1].split('/')[0].replace('8100','19888').split(':')[1]
                    if active_rm:
                        jobhistoryUrl_0 = item_dict['consoleUrl'].replace(
                            'proxy/application','ws/v1/history/mapreduce/jobs/job').replace('8100','19888').replace(rm_server,active_rm)
                    else:
                        jobhistoryUrl_0 = item_dict['consoleUrl'].replace(
                            'proxy/application','ws/v1/history/mapreduce/jobs/job').replace('8100','19888')
                    jobhistoryUrl_1 = jobhistoryUrl_0 + 'tasks'
                    jobhistoryUrl_1_req = requests.get(jobhistoryUrl_1)
                    if jobhistoryUrl_1_req.status_code == requests.codes.ok:
                        jobhistoryUrl_1_dict = jobhistoryUrl_1_req.json()
                        for item_id in range(0,len(jobhistoryUrl_1_dict['tasks']['task'])):
                            jobhistoryUrl_2 = jobhistoryUrl_1 + "/" + jobhistoryUrl_1_dict['tasks']['task'][item_id]['id'] + "/attempts"
                            jobhistoryUrl_2_req = requests.get(jobhistoryUrl_2)
                            jobhistoryUrl_2_dict = jobhistoryUrl_2_req.json()
                            print "  logsLinks:"
                            for item_id in range(0,len(jobhistoryUrl_2_dict['taskAttempts']['taskAttempt'])):
                                nodeHttpAddress = jobhistoryUrl_2_dict['taskAttempts']['taskAttempt'][item_id]['nodeHttpAddress']
                                assignedContainerId = jobhistoryUrl_2_dict['taskAttempts']['taskAttempt'][item_id]['assignedContainerId']
                                taskAttemptId = jobhistoryUrl_2_dict['taskAttempts']['taskAttempt'][item_id]['id']
                                nm_hostname = nodeHttpAddress.split(':')[0]
                                nm_port = nodeHttpAddress.split(':')[1]
                                nm_logsports = get_ports(nm_hostname,nm_port).split()
                                for port in nm_logsports:
                                    nodeHttpAddress_logs = nodeHttpAddress.replace(nm_port,port)
                                    finalUrl = "http://{0}:{1}/jobhistory/logs/{2}/{3}/{4}/{5}".format(
                                        rm_server,rm_server_port,nodeHttpAddress_logs,assignedContainerId,taskAttemptId,job_user)
                                    finalreq = requests.get(finalUrl)
                                    if 'Logs not available' not in finalreq.text:
                                        print "    " + finalUrl

            print "  *DEBUG*:"
            for key, value in item_dict.items():
                if key == "conf":
                    item_dict_conf_xml = "/tmp/{0}_{1}.xml".format(job_id,item_dict['name'])
                    file = open(item_dict_conf_xml,'w')
                    for item_dict_conf_row in item_dict['conf'].split('\r\n'):
                        file.write("{0}\n".format(item_dict_conf_row))
                    print "    conf: '{0}'".format(item_dict_conf_xml)
                else:
                    print "    {0}: '{1}'".format(key,value)

    return True

def main():
    if len(sys.argv) < 2:
        os.system(__file__ + ' -h')
        return 2
    
    opts = parse_opts()
    print '##################################'
    oozie_debug(opts['server'],opts['job_id'],opts['active_rm'])
    print '##################################'
    print 'Please check the URLs in "logsLinks" above for detailed informations.'
    print 'Do NOT ignore the messages in "Log Type: stdout".'

    return 0

if __name__=='__main__':
    sys.exit(main())
