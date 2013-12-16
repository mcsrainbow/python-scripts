#!/usr/bin/env python
#-*- coding:utf-8 -*-

# Author: Dong Guo
# Last Modified: 2013/12/15

import os
import sys
import commands
from decimal import Decimal

# import fabric api to run commands remotely
try:
    from fabric.api import env, execute, cd, sudo, run, hide, settings
except ImportError:
    sys.stderr.write("ERROR: Requires Fabric, try 'pip install fabric'.\n")
    sys.exit(1)

def parse_opts():
    """Help messages (-h, --help) for racktables.py"""

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('hostname', action="store", type=str)
    parser.add_argument('-w', action="store_true", default=False,help='write to database')

    args = parser.parse_args()
    return {'hostname':args.hostname, 'write':args.w}

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

    user = "adsymp"
    keyfile = "/home/adsymp/.ssh/id_rsa"
    
    # execute the given task
    myfab = FabricSupport()
    return myfab.execute(host,task,user,keyfile)

class FabricSupport(object):
    """Remotely get informations about servers"""
    
    def __init__(self):
        pass

    def execute(self,host,task,user,keyfile):
        env.parallel = False
        env.user = user
        env.key_filename = keyfile

        get_task = "task = self.{0}".format(task)
        exec get_task
        
        with settings(warn_only=True):
            with hide('warnings', 'running', 'stdout', 'stderr'):
                return execute(task,host=host)[host]

    def get_server_type(self):
        xapi_sign = run('rpm -q --quiet xapi-xe')
        if xapi_sign.succeeded:
            return "XenServer"
         
        ec2_sign = run("""curl http://169.254.169.254/latest/meta-data/hostname --connect-timeout 1 |egrep -wq 'ec2.internal|compute.internal'""")
        if ec2_sign.succeeded:
            return "EC2"

        xen_sign = run('ps -e | egrep -wq "xenbus|xenwatch"')
        if xen_sign.succeeded:
            return "VM"
        
        return "Server"
        
    def get_fqdn(self):
        hostname = run('hostname |cut -d. -f1')
        fqdn = run('hostname -f')
        if fqdn.failed:
            fqdn = hostname
        return fqdn

    def get_os_release(self):
        os_release = run('cat /etc/redhat-release')
        if os_release.failed:
            os_release = run('cat /etc/system-release')

        os_mode = run('uname -m')
        return os_release + ", " + os_mode

    def get_memory(self):
        output = run("""grep -w "MemTotal" /proc/meminfo |awk '{print $2}'""")
        t_mem_g = Decimal(output) / 1024 / 1024
        return round(t_mem_g,2)

    def get_swap(self):
        output = run("""grep -w "SwapTotal" /proc/meminfo |awk '{print $2}'""")
        t_swap_g = Decimal(output) / 1024 /1024
        return round(t_swap_g,2)

    def get_cpu(self):
        cpu_type = run("""grep 'model name' /proc/cpuinfo |uniq |awk -F : '{print $2}' |sed 's/^[ \t]*//g' |sed 's/ \+/ /g'""")
        cpu_cores = run("""grep 'processor' /proc/cpuinfo |sort |uniq |wc -l""")
        return {'cpu_cores':cpu_cores, 'cpu_type':cpu_type}

    def get_disk(self):
        disk = sudo("""fdisk -l 2>/dev/null |grep -v "/dev/mapper" |grep "Disk /dev" |awk '{print $2" "$3" "$4}'|grep -Ev '^$|^doesn' |xargs""")
        return disk

    def get_network(self):
        output = run("""/sbin/ifconfig |grep "Link encap" |awk '{print $1}' |grep -wv 'lo'""")
        nics = output.split('\r\n')
        t_nic_info = ""
        for i in nics:
            ipaddr = run("""/sbin/ifconfig %s |grep -w "inet addr" |cut -d: -f2 | awk '{print $1}'""" % (i))
            if ipaddr:
                t_nic_info = t_nic_info + i + ":" + ipaddr + ", "
        return t_nic_info

    def get_vm_list(self):
        output = sudo("""xl list-vm |awk '{print $3}' |grep -vw name |sort -n""")
        vm_list = ','.join(output.split('\r\n'))
        return vm_list

    def get_rst_on(self):
        vm_uuid = sudo("""xe vm-list |grep -B1 -w %s |awk '{if ($1 == "uuid") print $NF}'""" % (opts['hostname']))
        rst_uuid = sudo("""xe vm-param-get uuid={0} param-name=resident-on""".format(vm_uuid))
        rst_name = sudo("""xe vm-list params |egrep 'name-label|resident-on' |grep -B1 %s |grep -w "Control domain" |awk -F ": " '{print $NF}' |cut -d. -f1""" % (rst_uuid))
        return rst_name

    def get_rst_name(self):
        colo_prefix = run("""hostname -s |egrep 'sc2-|iad2-' |cut -d- -f1""")
        if colo_prefix.succeeded:
            xs = colo_prefix + '-vm1001'
            rst_name = fab_execute(xs,'get_rst_on')
        return rst_name

    def get_xs_memory(self):
        t_mem_m = sudo('xl info |grep total_memory |cut -d : -f 2')
        t_mem_g = int(t_mem_m) / 1024
        return t_mem_g

    def get_xs_cpu(self):
        cpu_cores = sudo("""xe host-cpu-info |grep -w cpu_count |awk -F ': ' '{print $2}'""")
        cpu_type = run("""grep 'model name' /proc/cpuinfo |uniq |awk -F : '{print $2}' |sed 's/^[ \t]*//g' |sed 's/ \+/ /g'""")
        return {'cpu_cores':cpu_cores, 'cpu_type':cpu_type}

    def get_ec2_pubname(self):
        ec2_pubname = sudo("""curl http://169.254.169.254/latest/meta-data/public-hostname --connect-timeout 1""")
        return ec2_pubname

def sum_info():
    """Get & Print all informations"""

    server_type = fab_execute(opts['hostname'],"get_server_type")
    print "TYPE:        " + server_type

    fqdn = fab_execute(opts['hostname'],"get_fqdn")
    print "FQDN:        " + fqdn

    os_release = fab_execute(opts['hostname'],"get_os_release")
    print "OS:          " + os_release

    if server_type == "XenServer":
        memory = fab_execute(opts['hostname'],'get_xs_memory')
    else:
        memory = fab_execute(opts['hostname'],'get_memory')
    print "MEMORY:      " + str(memory) + " GB"

    swap = fab_execute(opts['hostname'],'get_swap')
    print "SWAP:        " + str(swap) + " GB"

    if server_type == "XenServer":
        cpu_info = fab_execute(opts['hostname'],'get_xs_cpu')
    else:
        cpu_info = fab_execute(opts['hostname'],'get_cpu')
    print "CPU:         " + cpu_info['cpu_cores'] + " Cores, " + cpu_info['cpu_type']

    disk = fab_execute(opts['hostname'],'get_disk')
    print "DISK:        " + disk

    network = fab_execute(opts['hostname'],"get_network")
    print "NETWORK:     " + network

    vm_list = ""
    if server_type == "XenServer":
        vm_list = fab_execute(opts['hostname'],"get_vm_list")
        print "VMLIST:      " + vm_list

    xs_name = ""
    if server_type == "VM":
        xs_name = fab_execute(opts['hostname'],"get_rst_name")
        print "RESIDENT-ON: " + xs_name 

    ec2_pubname = ""
    if server_type == "EC2":
        ec2_pubname = fab_execute(opts['hostname'],"get_ec2_pubname")
        print "PUBNAME:     " + ec2_pubname
    
    return {'server_type':server_type, 'fqdn':fqdn, 'hostname':opts['hostname'],'os_release':os_release,
            'memory':memory,'swap':swap, 'cpu_cores':cpu_info['cpu_cores'], 'cpu_type':cpu_info['cpu_type'],
            'disk':disk,'network':network, 'vm_list':vm_list, 'resident_on':xs_name, 'ec2_pubname':ec2_pubname}

def update_db(info):
    """Automate server audit into Racktables"""
    
    # import time to use spleep function 
    from time import sleep 
    # import urllib to encode the data for POST
    from urllib import quote_plus
    # torndb is a lightweight wrapper around MySQLdb
    try:
        from torndb import Connection
    except ImportError:
        sys.stderr.write("ERROR: Requires torndb, try 'yum install MySQL-python' then 'pip install torndb'.\n")
        sys.exit(1)
    
    # racktables server address, username, password with curl command
    rt_server = "sc2-rackmonkey"
    curl = "curl -s -u admin:racktables"

    # connect to racktables db
    db = Connection(rt_server,"racktables_db","racktables_user","racktables")

    # get object_type_id
    for item in db.query("select * from Dictionary where dict_value='{0}'".format(info['server_type'])):
        object_type_id = item.dict_key

    # check if object_id already exists, then create object if not
    object_id = ""
    for item in db.query("select * from Object where name='{0}'".format(info['hostname'])):
        object_id = item.id
    if not object_id:
        # create object
        if info['server_type'] in ["Server","XenServer"]:
            url = """'http://{0}/racktables/index.php?module=redirect&page=depot&tab=addmore&op=addObjects' \
--data '0_object_type_id={1}&0_object_name={2}&0_object_label=&0_object_asset_no={2}&got_fast_data=Go%21'"""\
                   .format(rt_server,object_type_id,info['hostname'])
        if info['server_type'] in ["VM","EC2"]:
            url = """'http://{0}/racktables/index.php?module=redirect&page=depot&tab=addmore&op=addObjects' \
--data 'virtual_objects=&0_object_type_id={1}&0_object_name={2}&got_fast_data=Go%21'"""\
                   .format(rt_server,object_type_id,info['hostname'])

        cmd = "{0} {1}".format(curl,url)
        status, output = commands.getstatusoutput(cmd)
        if status != 0:
            print "Failed to created object: {0}".format(info['hostname'])
            return False
        else:
            print "OK - Created object: {0}".format(info['hostname'])

        # get object_id
        for item in db.query("select * from Object where name='{0}'".format(info['hostname'])):
            object_id = item.id
        if not object_id:
            print "Faild to get object_id"
            return False
    else:
        print "Object:'{0}' already exists".format(info['hostname'])

    # get os_release_id
    os_release_key = ""
    for item in db.query("select * from Dictionary where dict_value='{0}'".format(info['os_release'])):
        os_release_key = item.dict_key
    if not os_release_key:
        print "Faild to get object_type_id, please add '{0}' to 'Configuration - Dictionary - Server OS type'.".format(info['os_release'])
        return False

    # update the informations of object, all post data formats were got by firebug on firefox
    if info['server_type'] == "Server":
        url = """'http://{0}/racktables/index.php?module=redirect&page=object&tab=edit&op=update' \
--data 'object_id={1}&object_type_id={2}&object_name={3}&object_label=&object_asset_no={3}&0_attr_id=14&0_value=&1_attr_id=10000&1_value={4}\
&2_attr_id=10004&2_value={5}&3_attr_id=3&3_value={6}&4_attr_id=2&4_value=0&5_attr_id=26&5_value=0&6_attr_id=10006&6_value={7}\
&7_attr_id=10003&7_value={8}&8_attr_id=1&8_value=&9_attr_id=28&9_value=&10_attr_id=21&10_value=&11_attr_id=4&11_value={9}\
&12_attr_id=24&12_value=&13_attr_id=10005&13_value={10}&14_attr_id=25&14_value=&num_attrs=15&object_comment=&submit.x=15&submit.y=13'"""\
                .format(rt_server,object_id,object_type_id,info['hostname'],info['cpu_cores'],quote_plus(info['disk']),info['fqdn'],
                        info['memory'],quote_plus(info['network']),os_release_key,info['swap'])
    if info['server_type'] == "XenServer":
        url = """'http://{0}/racktables/index.php?module=redirect&page=object&tab=edit&op=update' \
--data 'object_id={1}&object_type_id={2}&object_name={3}&object_label=&object_asset_no={3}&0_attr_id=14&0_value=&1_attr_id=10000&1_value={4}\
&2_attr_id=10004&2_value={5}&3_attr_id=3&3_value={6}&4_attr_id=26&4_value=0&5_attr_id=10006&5_value={7}&6_attr_id=10003&6_value={8}\
&7_attr_id=1&7_value=&8_attr_id=28&8_value=&9_attr_id=4&9_value={9}&10_attr_id=24&10_value=&11_attr_id=10005&11_value={10}\
&12_attr_id=25&12_value=&13_attr_id=10008&13_value={11}&num_attrs=14&object_comment=&submit.x=18&submit.y=21'"""\
                .format(rt_server,object_id,object_type_id,info['hostname'],info['cpu_cores'],quote_plus(info['disk']),info['fqdn'],
                        info['memory'],quote_plus(info['network']),os_release_key,info['swap'],quote_plus(info['vm_list']))
    if info['server_type'] == "EC2":
        url = """'http://{0}/racktables/index.php?module=redirect&page=object&tab=edit&op=update' \
--data 'object_id={1}&object_type_id={2}&object_name={3}&object_label=&object_asset_no=&0_attr_id=14&0_value=&1_attr_id=10000&1_value={4}\
&2_attr_id=10004&2_value={5}&3_attr_id=3&3_value={6}&4_attr_id=26&4_value=0&5_attr_id=10006&5_value={7}&6_attr_id=10003&6_value={8}\
&7_attr_id=10010&7_value={9}&8_attr_id=4&8_value={10}&9_attr_id=24&9_value=&10_attr_id=10005&10_value={11}&num_attrs=11&object_comment=&submit.x=19&submit.y=27'"""\
                .format(rt_server,object_id,object_type_id,info['hostname'],info['cpu_cores'],quote_plus(info['disk']),info['fqdn'],
                        info['memory'],quote_plus(info['network']),info['ec2_pubname'],os_release_key,info['swap'])
    if info['server_type'] == "VM":
        url = """'http://{0}/racktables/index.php?module=redirect&page=object&tab=edit&op=update' \
--data 'object_id={1}&object_type_id={2}&object_name={3}&object_label=&object_asset_no=&0_attr_id=14&0_value=&1_attr_id=10000&1_value={4}\
&2_attr_id=10004&2_value={5}&3_attr_id=3&3_value={6}&4_attr_id=26&4_value=0&5_attr_id=10006&5_value={7}&6_attr_id=10003&6_value={8}\
&7_attr_id=10007&7_value={9}&8_attr_id=4&8_value={10}&9_attr_id=24&9_value=&10_attr_id=10005&10_value={11}&num_attrs=11&object_comment=&submit.x=25&submit.y=14'"""\
                .format(rt_server,object_id,object_type_id,info['hostname'],info['cpu_cores'],quote_plus(info['disk']),info['fqdn'],
                        info['memory'],quote_plus(info['network']),info['resident_on'],os_release_key,info['swap'])

    cmd = "{0} {1}".format(curl,url)
    status, output = commands.getstatusoutput(cmd)
    if status != 0:
        print "Failed to update attributes"
        return False
    print "OK - Updated attributes"

    # ec2 servers don't need to update the ip pool
    if info['server_type'] in ["EC2"]:
        return True

    # update the ip pool
    nics = ("".join(info['network'].split())).split(',')
    for i in nics:
        nic_info = i.split(':')
        nic_name = "".join(nic_info[0:1])
        nic_addr = "".join(nic_info[1:2])
        # check if nic_name is not correct
        if nic_name.isalnum():
            # create nic
            url = """'http://{0}/racktables/index.php?module=redirect&page=object&tab=ip&op=add' \
--data 'object_id={1}&bond_name={2}&ip={3}&bond_type=regular&submit.x=11&submit.y=6'"""\
                .format(rt_server,object_id,nic_name,nic_addr)
            cmd = "{0} {1}".format(curl,url)
            status, output = commands.getstatusoutput(cmd)
            if status != 0:
                print "Failed to update ip pool for {0}:{1}".format(nic_name,nic_addr)
                return False
            print "OK - Updated ip pool for {0}:{1}".format(nic_name,nic_addr)
           
    # close db
    db.close()

    # end
    return True

if __name__=='__main__':
    # show help messages if no parameter
    argv_len = len(sys.argv)
    if argv_len < 2:
        os.system(__file__ + " -h")
        sys.exit(1)
    opts = parse_opts()
    
    # check if host is up
    isup(opts['hostname'])
     
    # get info
    print "========================================"
    print "Getting information from '{0}'...".format(opts['hostname'])
    print "========================================"
    info = sum_info()

    # update racktables
    if opts['write']:
        print "========================================"
        print "Updating racktables..." 
        print "========================================"
        update_db(info)
