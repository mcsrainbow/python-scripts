#!/usr/bin/env python
#-*- coding:utf-8 -*-

# Description: 
# Author: Dong Guo
# Last modified: 2015-07-30 08:50 UTC

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
          {0} --server idc1-server1 --job_id 0441398-150120233308020-oozie-oozi-W
        '''.format(__file__)
        ))
    
    parser.add_argument('--server', type=str, required=True, help='the oozie server address')
    parser.add_argument('--job_id', type=str, required=True, help='the oozie job id')
    args = parser.parse_args()

    return {'server':args.server, 'job_id':args.job_id}

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

def get_ports(hostname):
    username = "root"
    pkey = "/root/.ssh/id_dsa"
    pkey_type = "dsa"

    nm_pid = remote("""netstat -lntp |grep -w 8042 |awk '{print $NF}' |cut -d/ -f1""",hostname=hostname,username=username,pkey=pkey,pkey_type=pkey_type)
    if nm_pid:
        ports = remote("""netstat -lntp |grep -w %s |awk '{print $4}' |sed s/://g |grep -Ev '8040|8042|13562' |xargs""" % (nm_pid),hostname=hostname,username=username,pkey=pkey,pkey_type=pkey_type)
        if ports:
            return ports

    return False

def oozie_debug(server,job_id):
    
    import requests
    import json

    req = requests.get('http://{0}:11000/oozie/v1/job/{1}'.format(server,job_id))

    req_dict = req.json()
    job_user = req_dict['user']
    if req_dict['status'] == "KILLED":
        for item_id in range(0,len(req_dict['actions'])):
            item_dict = req_dict['actions'][item_id]
            print "status: '{0}', name: '{1}'".format(item_dict['status'],item_dict['name'])
            if item_dict['status'] == 'ERROR':
                print "  consoleUrl: '{0}'".format(item_dict['consoleUrl'])
                if 'proxy/application' not in item_dict['consoleUrl']:
                    print "  *NOTE*: The above consoleUrl from API may not correct, please manually check the URL:'http://{0}:11000/oozie'.".format(server)
                else:
                    rm_server = item_dict['consoleUrl'].split('http://')[1].split('/')[0].replace('8100','19888')
                    jobhistoryUrl_0 = item_dict['consoleUrl'].replace('proxy/application','ws/v1/history/mapreduce/jobs/job').replace('8100','19888')
                    jobhistoryUrl_1 = jobhistoryUrl_0 + 'tasks'
                    jobhistoryUrl_1_req = requests.get(jobhistoryUrl_1)
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
                            nm_hostname = nodeHttpAddress.replace(':8042','')
                            nm_logsports = get_ports(nm_hostname).split()
                            for port in nm_logsports:
                                nodeHttpAddress_logs = nodeHttpAddress.replace('8042',port)
                                finalUrl = "http://{0}/jobhistory/logs/{1}/{2}/{3}/{4}".format(rm_server,nodeHttpAddress_logs,assignedContainerId,taskAttemptId,job_user)
                                finalreq = requests.get(finalUrl)
                                if 'Logs not available' not in finalreq.text:
                                    print "    " + finalUrl

    return True

def main():
    if len(sys.argv) < 2:
        os.system(__file__ + ' -h')
        return 2
    
    opts = parse_opts()
    print '##################################'
    oozie_debug(opts['server'],opts['job_id'])
    print '##################################'
    print 'Please check the URLs in "logsLinks" above for detailed informations.'
    print 'Do NOT ignore the messages in "Log Type: stdout".'

    return 0

if __name__=='__main__':
    sys.exit(main())
