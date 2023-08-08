#!/usr/bin/env python
#-*- coding:utf-8 -*-

# Description: Pre-configure a host for Ansible
# Author: Dong Guo
# Last modified: 2016-12-12

import os
import sys
import subprocess
import paramiko

WORKHOME = '/local/path/to/workhome'

def parse_opts():
    """Help messages(-h, --help)."""

    import textwrap
    import argparse

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
        '''
        examples:
          {0} -s demo.heylinux.com -p 'demo_password'
          {0} -s demo.heylinux.com -p 'demo_password' -P 2022
        '''.format(__file__)
        ))

    parser.add_argument('-s', metavar='server', type=str, required=True, help='the server address')
    parser.add_argument('-p', metavar='password', type=str, required=True, help='the root password')
    parser.add_argument('-P', metavar='port', type=int, help='the ssh port')
    args = parser.parse_args()

    return {'server':args.s, 'password':args.p, 'port':args.P}

class _AttributeString(str):
    """
    Simple string subclass to allow arbitrary attribute access.
    """
    @property
    def stdout(self):
        return str(self)

def remote(cmd, hostname, username, password=None, pkey=None, pkey_type="rsa", port=22):
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

    stdout_str = ""
    stderr_str = ""
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

def sftp(src_path, dest_path, hostname, username, password=None, pkey=None, pkey_type="rsa",
         port=22, transfer_type=None):
    p = paramiko.Transport((hostname,port))

    if pkey is not None:
        if pkey_type == "dsa":
            pkey = paramiko.DSSKey.from_private_key_file(pkey)
        else:
            pkey = paramiko.RSAKey.from_private_key_file(pkey)
        p.connect(username=username, pkey=pkey)
    else:
        p.connect(username=username, password=password)

    sftp = paramiko.SFTPClient.from_transport(p)

    out = _AttributeString()
    out.failed = False
    out.stderr = None

    if transfer_type is not None:
        try:
            if transfer_type == "get":
                sftp.get(src_path, dest_path)
            if transfer_type == "put":
                sftp.put(src_path, dest_path)
        except Exception, e:
            out.failed = True
            out.stderr = e.args[1]

    out.succeeded = not out.failed

    p.close()
    return out

def get(remote_path, local_path, hostname, username, password=None, pkey=None, pkey_type="rsa", port=22):
    return sftp(remote_path, local_path, hostname, username, password=password, pkey=pkey, pkey_type=pkey_type,
                port=port, transfer_type="get")

def put(local_path, remote_path, hostname, username, password=None, pkey=None, pkey_type="rsa", port=22):
    return sftp(local_path, remote_path, hostname, username, password=password, pkey=pkey, pkey_type=pkey_type,
                port=port, transfer_type="put")

def main():
    if len(sys.argv) < 2:
        os.system(__file__ + ' -h')
        return 2

    # locate ansible workhome
    os.chdir(WORKHOME)

    # get parameters
    opts = parse_opts()

    hostname = opts['server']
    password = opts['password']
    ssh_port = opts['port']
    username = 'root'

    cmd_list = ['setenforce 0; /bin/true',
                'mkdir -p /root/.ssh',
                'chmod 700 /root/.ssh']

    cmd = ' && '.join(cmd_list)
    if ssh_port is not None:
        out = remote(cmd,hostname=hostname,username=username,password=password,port=ssh_port)
    else:
        out = remote(cmd,hostname=hostname,username=username,password=password)

    if out.failed:
        print "Failed to run command:'{0}' on server:'{1}'".format(cmd,hostname)
        return 2

    print "Succeeded to run command:'{0}' on server:'{1}'".format(cmd,hostname)

    put_list = ['/local/path/to/authorized_keys,/root/.ssh/authorized_keys',
                '/local/path/to/CentOS-Base.repo,/etc/yum.repos.d/CentOS-Base.repo']

    for put_item in put_list:
        src_file = put_item.split(',')[0]
        dest_file = put_item.split(',')[1]

        if ssh_port is not None:
            out = put(src_file,dest_file,hostname=hostname,username=username,password=password,port=ssh_port)
        else:
            out = put(src_file,dest_file,hostname=hostname,username=username,password=password)
        if out.failed:
            print "Failed to upload file:'{0}' to server:'{1}:{2}'".format(src_file,hostname,dest_file)
            return 2

        print "Succeeded to upload file:'{0}' to server:'{1}:{2}'".format(src_file,hostname,dest_file)

    return 0

if __name__ == '__main__':
    sys.exit(main())
