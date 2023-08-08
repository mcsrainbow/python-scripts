#!/bin/env python
#-*- coding:utf-8 -*-

# Author: Damon Guo
# Last Modified: 2019/08/30

import os
import sys
import subprocess

class _AttributeString(str):
    """
    Simple string subclass to allow arbitrary attribute access.
    """
    @property
    def stdout(self):
        return str(self)

def local_cmd(cmd, capture=True, shell=None):
    out_stream = subprocess.PIPE
    err_stream = subprocess.PIPE
    p = subprocess.Popen(cmd, shell=True, stdout=out_stream, stderr=err_stream, executable=shell)
    (stdout, stderr) = p.communicate()

    out = _AttributeString(stdout.strip() if stdout else "")
    err = _AttributeString(stderr.strip() if stderr else "")

    out.cmd = cmd
    out.failed = False
    out.return_code = p.returncode
    out.stderr = err
    if out.return_code != 0:
        out.failed = True
    out.succeeded = not out.failed

    return out

def update_dnspod_record(public_ip,sub_domain_name,domain_name):
    import pydnspod

    user_id = "857857"
    user_token = "857abc857abc857abc857abc85723333"

    dp = pydnspod.connect(user_id, user_token)

    domain_id = ''
    domain_list = dp.domain.list()
    for domain_item in domain_list['domains']:
        if domain_item['name'] == domain_name:
            domain_id = domain_item['id']

    record_id = ''
    if domain_id is not None:
        record_list = dp.record.list(domain_id)
        for record_item in record_list['records']:
            if record_item['name'] == sub_domain_name:
                record_id = record_item['id']

    if record_id is not None:
        dp.record.modify(domain_id,record_id, sub_domain_name,'A',public_ip)
        print("""Updated the domain: '{0}.{1}' with IP: '{2}' successfully.""".format(sub_domain_name,domain_name,public_ip))
        return True

    return False

def main():
    public_ip = local_cmd('curl -s http://instance-data/latest/meta-data/public-ipv4')
    sub_domain_name = 'sub-domain-name'
    domain_name = 'domain.name'

    update_dnspod_record(public_ip,sub_domain_name,domain_name)

    return 0

if __name__ == '__main__':
    sys.exit(main())
