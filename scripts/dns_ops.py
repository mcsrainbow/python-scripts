#!/usr/bin/env python

# Description: Interface with nsupdate to operate on A/PTR/CNAME
# at the master DNS server 

import argparse
import subprocess
import sys
import os
import re

opt = argparse.ArgumentParser("dns_ops")
opt.add_argument("-u", "--update", help="update_action", choices=['add', 'delete'], required=True)
opt.add_argument("-n", "--name", help="hostname", required=True)
opt.add_argument("-t", "--type", help="record type such A, CNAME, PTR", choices=['A', 'CNAME', 'PTR'], required=True)
opt.add_argument("-p", "--point", help="points_to", required=True)

args = opt.parse_args()

path = "/var/named/"
tmp_path = "/tmp/"
dns_file = "dnsadd"
dns_master = "server 10.100.1.2\n"
zone = "heylinux.com"

bind_lan = "heylinux.com.lan"

bind_ptr_100 = "1.100.10.in-addr.arpa"
bind_ptr_101 = "1.101.10.in-addr.arpa"
bind_ptr_102 = "1.102.10.in-addr.arpa"

dict = { "10.100.1": bind_ptr_100,
    "10.101.1": bind_ptr_101,
    "10.102.1": bind_ptr_102,
}

input_file = tmp_path + dns_file
 
def whichReverseZone(ipaddr):
    if "10.102.1." in ipaddr:
        return dict["10.102.1"] 

    if "10.101.1." in ipaddr:
        return dict["10.101.1"]

    if "10.100.1." in ipaddr:
        return dict["10.100.1"]

    else:
        return None

def comtLastNumber(ipaddr):
    tup = ipaddr.rpartition('.')
    
    return tup[2] if tup else -1

def isFQDNGood(fqdn):
    m = re.match("([a-z0-9\.\-]+)\.([a-z]{2,4}\.?$)", fqdn)

    if not m:
        return False

    return True
    

def isIPGood(ipaddress):
    m = re.match("([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})$", ipaddress)

    if not m:
        return False
    
    if 255 >= int(m.group(1)) >= 0:
        if 255 >= int(m.group(2)) >= 0:
            if 255 >= int(m.group(3)) >= 0:
                if 255 >= int(m.group(4)) >= 0:
                    return True
    return False 

def update_cname(args, f):
    if args.update == "add":
        m = re.match("([\w\.\-]+)\.([a-z]{2,4}\.?$)", 
                args.point)
        if m:
            f.write(dns_master)
            f.write("zone ")
            f.write(zone)
            f.write("\n")

            s = re.search(".*\.heylinux\.com\.?$", 
                    args.point)
            if s:
                #args.point must already exists
                check="prereq yxdomain " + args.point + "\n"
                f.write(check)

            n = re.search("\.$", args.point)
            if not n:
                args.point +=  "."
        else:
            print "%s is malformed. Please correct" % args.point
            sys.exit(1)



        print "Adding %s.%s %s %s\n" % (args.name, zone, 
                    args.type, args.point)

        #no previous record of args.name of any type
        check = "prereq nxdomain " +  args.name + "." + zone + "\n"
        f.write(check)


        cmd = "update add " + args.name + "." + zone + " 86400 " + args.type + " " + args.point + "\n" 
    else:
        print "Deleting %s.%s %s %s\n" % (args.name, zone,
                     args.type, args.point)

        #args.name of specific type
        check = "prereq yxrrset " +  args.name + "." + zone + " " + args.type + " " + args.point + "\n"
        f.write(check)
        
        cmd = "update delete " + args.name + "." + zone + " 86400 " + args.type + " " + args.point + "\n" 

    f.write(cmd)
    f.write("send\n") 


def update_a(args, f):
    if isFQDNGood(args.name):
        print "%s is malformed. Name should be just like idc1-server1 without the heylinux.com. Exit" % args.name
        sys.exit(1)

    if isIPGood(args.point):
        f.write(dns_master)
        f.write("zone ")
        f.write(zone)
        f.write("\n")
        
        #An fqdn can be pointed to only 1 IP address
        if args.update == "add":
            print "Adding %s %s %s\n" % (args.name, 
                args.type, args.point)
            check = "prereq nxdomain " + args.name + "." +  zone + "\n"
            f.write(check)

            cmd = "update add " + args.name + "." + zone + " 86400 " + args.type + " " + args.point + "\n"
        else:
            print "Deleting %s %s %s\n" % (args.name, 
                args.type, args.point)
            #args.name of specific type must exist
            check = "prereq yxrrset " +  args.name + "." + zone + " " + args.type + " " + args.point + "\n"
            f.write(check)

            cmd = "update delete " + args.name + "." + zone + " 86400 " + args.type + " " + args.point + "\n" 

        f.write(cmd)
        f.write("send\n") 
    else:
        print "%s is malformed. Please correct" % args.point
        sys.exit(1)

def update_ptr(args, f): 
    if isIPGood(args.name):
        rev_zone = whichReverseZone(args.name)
        if not rev_zone:
            print "Could not find zone for %s" % args.name  
            sys.exit(1)
    
        last = comtLastNumber(args.name)

        if int(last) >= 0 and int(last) <= 255: 
            entry = last + "." + rev_zone + "."
        else:
            print "Error with %s. Exit" % args.name 
            sys.exit(1)
    

        if isFQDNGood(args.point):
            n = re.search("\.$", args.point)
            if not n:
                args.point +=  "."
        else:
            print "%s is malformed. Exit" % args.point
            sys.exit(1)

        f.write(dns_master)
        f.write("zone ")
        f.write(rev_zone)
        f.write("\n")

        #if a PTR already exist, adding will be aborted b/c 
        #we need absolutely sure of the action
        if args.update == "add":
            print "Adding %s %s %s\n" % (entry, 
                            args.type, 
                            args.point)

            cmd = "update add " + entry  + " 86400 " + args.type + " " + args.point + "\n"

        else:
            print "Deleting %s %s %s\n" % (entry, 
                            args.type, 
                            args.point)

            cmd = "update delete " + entry + " " + args.type + " " + args.point + "\n" 
    
        f.write(cmd)
        f.write("send\n") 
        f.write("answer\n")
    else:
        print "%s is malformed. Please correct" % args.name
        sys.exit(1)

if not os.path.isdir(tmp_path):
    print "%s missing" % tmp_path
    sys.exit(1)


with open(tmp_path + dns_file, "w") as f:
    if args.type == "CNAME":
        private = "Kidc1-server1.+157+01802.private"
        key = "Kidc1-server1.+157+01802.key"

        update_cname(args, f)
    elif args.type == "A":
        private = "Kidc1-server1.+157+01802.private"
        key = "Kidc1-server1.+157+01802.key"

        update_a(args, f)
    elif args.type == "PTR":
        private = "Kheylinux.com.+157+61482.private"
        key = "Kheylinux.com.+157+61482.key"
        
        update_ptr(args, f)


priv_key = path + private
if not os.path.isfile(priv_key):
    print "%s%s is missing" % (path, private)
    sys.exit(1)

if not os.path.isfile(path + key):
    print "%s%s is missing" % (path, key)
    sys.exit(1)

exec_cmd = "/usr/bin/nsupdate -k " + priv_key + " " + input_file

ret = subprocess.call(exec_cmd, shell=True)


if ret == 0:
    print "Successful"
    sys.exit(0)
else:
    print "Failed because duplicate/nonexistent record"
    sys.exit(1) 
