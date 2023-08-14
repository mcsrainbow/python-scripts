#!/usr/bin/env python
#-*- coding:utf-8 -*-

# Author: Dong Guo
# Last Modified: 2013/12/9

import os
import sys
import fileinput

# import fabric api to run commands remotely
try:
    from fabric.api import env, execute, cd, sudo, run, hide, settings
except ImportError:
    sys.stderr.write("ERROR: Requires Fabric, try 'pip install fabric'.\n")
    sys.exit(1)

def parse_opts():
    """Help messages (-h, --help)"""
    
    import textwrap
    import argparse

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
        '''
        examples:
          {0} -s idc1-server3 -f idc1-server3.list
          {0} -s idc1-server3 -t t_c64_min -n idc2-server21 -i 10.100.1.65 -e 255.255.252.0 -g 10.100.1.1 -c 4 -m 8G -d 50G

          idc1-server3.list:
            t_c64_min,idc2-server21,10.100.1.65,255.255.252.0,10.100.1.1,4,8G,50G,
            t_c64_min,idc2-server41,10.100.1.66,255.255.252.0,10.100.1.1,4,8G,50G,
            ...
        '''.format(__file__)
        ))

    exclusion = parser.add_mutually_exclusive_group(required=True)

    parser.add_argument('-s', metavar='server', type=str, required=True, help='hostname of xenserver')
    exclusion.add_argument('-f', metavar='filename', type=str, help='filename of list')
    exclusion.add_argument('-t', metavar='template', type=str, help='template of vm')
    parser.add_argument('-n', metavar='hostname', type=str, help='hostname of vm')
    parser.add_argument('-i', metavar='ipaddr', type=str, help='ipaddress of vm')
    parser.add_argument('-e', metavar='netmask', type=str, help='netmask of vm')
    parser.add_argument('-g', metavar='gateway', type=str, help='gateway of vm')
    parser.add_argument('-c', metavar='cpu', type=int, help='cpu cores of vm')
    parser.add_argument('-m', metavar='memory', type=str, help='memory size of vm')
    parser.add_argument('-d', metavar='disk', type=str, help='disk size of vm')

    args = parser.parse_args()
    return {'server':args.s, 'filename':args.f, 'template':args.t, 'hostname':args.n, 'ipaddr':args.i, 
            'netmask':args.e, 'gateway':args.g, 'cpu':args.c, 'memory':args.m, 'disk':args.d}

def isup(host):
    """Check if host is up"""

    import socket

    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    conn.settimeout(1)
    try:
        conn.connect((host,22))
        conn.close()
    except:
        print "Connect to host {0} port 22: Network is unreachable".format(host)
        sys.exit(1)

def fab_execute(host,task):
    """Execute the task in class FabricSupport."""

    user = "heydevops"
    keyfile = "/home/heydevops/.ssh/id_rsa"
    
    myfab = FabricSupport()
    return myfab.execute(host,task,user,keyfile)

class FabricSupport(object):
    """Remotely get information about servers"""
    
    def __init__(self):
        self.server = opts['server']
        self.template = opts['template']
        self.hostname = opts['hostname']
        self.ipaddr = opts['ipaddr']
        self.netmask = opts['netmask']
        self.gateway = opts['gateway']
        self.cpu = opts['cpu']
        self.memory = opts['memory']
        self.disk = opts['disk']

    def execute(self,host,task,user,keyfile):
        env.parallel = False
        env.user = user
        env.key_filename = keyfile

        get_task = "task = self.{0}".format(task)
        exec get_task
        
        with settings(warn_only=True):
            return execute(task,host=host)[host]

    def clone(self):
        print "Choosing the storage has most available spaces..."
        sr_items = sudo("""xe sr-list |grep -A2 -B3 -w %s |grep -A1 -B4 -Ew 'lvm|ext' |grep -w name-label |awk -F ": " '{print $2}'""" % (self.server))
        sr_disk = 0
        for item in sr_items.splitlines():
            item_uuid = sudo("""xe sr-list |grep -A2 -B3 -w %s |grep -B1 -w '%s' |grep -w uuid |awk -F ": " '{print $2}'""" % (self.server,item))
            t_disk = sudo("""xe sr-param-list uuid={0} |grep physical-size |cut -d: -f2""".format(item_uuid))
            u_disk = sudo("""xe sr-param-list uuid={0} |grep physical-utilisation |cut -d: -f2""".format(item_uuid))
            f_disk = int(t_disk) - int(u_disk)
            if f_disk > sr_disk:
                sr_disk = f_disk
                sr_name = item
                sr_uuid = item_uuid

        print "Copying the vm:{0} from template:{1} on storage:'{2}'...".format(self.hostname,self.template,sr_name)
        vm_uuid = sudo("""xe vm-copy new-name-label={0} vm={1} sr-uuid={2}""".format(self.hostname,self.template,sr_uuid))
        if vm_uuid.failed:
            print "Failed to copy vm:{0}".format(self.hostname)
            return False
        
        print "Setting up the bootloader,vcpus,memory of vm:{0}...".format(self.hostname)
        sudo('''xe vm-param-set uuid={0} HVM-boot-policy=""'''.format(vm_uuid))
        sudo('''xe vm-param-set uuid={0} PV-bootloader="pygrub"'''.format(vm_uuid))

        sudo('''xe vm-param-set VCPUs-max={0} uuid={1}'''.format(self.cpu,vm_uuid))
        sudo('''xe vm-param-set VCPUs-at-startup={0} uuid={1}'''.format(self.cpu,vm_uuid))

        sudo('''xe vm-memory-limits-set uuid={0} dynamic-min={1}iB dynamic-max={1}iB static-min={1}iB static-max={1}iB'''.format(vm_uuid,self.memory))

        print "Setting up the disk size of vm:{0}...".format(self.hostname)
        vdi_uuid = sudo("""xe vm-disk-list vm=%s |grep -B2 '%s' |grep -w uuid |awk '{print $5}'""" % (self.hostname,sr_name))
        sudo('''xe vdi-resize uuid={0} disk-size={1}iB'''.format(vdi_uuid,self.disk))

        print "Setting up the network of vm:{0}...".format(self.hostname)
        sudo('''xe vm-param-set uuid={0} PV-args="_hostname={1} _ipaddr={2} _netmask={3} _gateway={4}"'''.format(vm_uuid,self.hostname,self.ipaddr,self.netmask,self.gateway))

        print "Starting vm:{0}...".format(self.hostname)
        vm_start = sudo('''xe vm-start uuid={0}'''.format(vm_uuid))
        if vm_start.failed:
            print "Failed to start vm:{0}".format(self.hostname)
            return False
        return True

if __name__ == '__main__':
    if len(sys.argv) < 2:
        os.system(__file__ + " -h")
        sys.exit(1)
    opts = parse_opts()

    # check if host is up
    isup(opts['server'])

    # clone
    if opts['filename']:
        for i in fileinput.input(opts['filename']):
            a = i.split(',')
            opts = {'server':opts['server'], 'template':a[0], 'hostname':a[1], 'ipaddr':a[2], 
                    'netmask':a[3], 'gateway':a[4], 'cpu':a[5], 'memory':a[6], 'disk':a[7]}
            fab_execute(opts['server'],"clone")
        sys.exit(0)
    fab_execute(opts['server'],"clone")
