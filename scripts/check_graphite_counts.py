#!/usr/bin/env python
#-*- coding:utf-8 -*-

# Date: Wed 30 Oct 2013
# Author: Dong Guo

import sys
import commands
from decimal import Decimal

# torndb is a lightweight wrapper around MySQLdb
try:
    from torndb import Connection
except ImportError:
    sys.stderr.write("ERROR: Requires MySQLdb and torndb.")

def count_avg(**kwargs):
    """Get the average value of counts in given period."""
    
    # get values from the given tuple
    partner_id = kwargs['partner_id']
    period = kwargs['period']

    url = """http://server/counts?partner_id={0}&period={1}""".format(partner_id,period)
    command = """/usr/bin/curl -s -u username:passwd '%s' | awk -F "|" '{print $2}'""" % (url)
    status, output = commands.getstatusoutput(command)
    command_grep = """echo %s | grep [0-9]""" % (output)
    status_grep, output_grep = commands.getstatusoutput(command_grep)
    if status_grep == 0:
        counts = output.split(',')
        sum = 0
        num = 0
        for count in counts:
            if count != "None":
                sum = Decimal(sum) + Decimal(count)
                num = num + 1
                avg = Decimal(sum) / num
                return round(avg,2)
    return False

# connect the database
db = Connection("server", "database", "username", "passwd")

# partner_list
partner_list = [
21012,21022,21054,21061,21133,
21223,21242,21292,21353,
]

# get the partner_id from database
"""
for item in db.query("SELECT * FROM partners"):
    partner_id = item.partner_id
    partner_name = item.name

avg_prev = count_avg(partner_id=partner_id,period=15)
avg_next = count_avg(partner_id=partner_id,period=60)

if avg_next != False and avg_prev != False:
"""

failed_partner_num = 0
failed_partner_name = ""

# get the partner_id from partner_list
for partner_id in partner_list:
    for item in db.query("SELECT * FROM partners where partner_id={0}".format(partner_id)):
        partner_name = item.name
    
    avg_prev = count_avg(partner_id=partner_id,period=15)
    avg_next = count_avg(partner_id=partner_id,period=60)
    
    if avg_next != False and avg_prev != False:
        avg_prev_cmp = avg_prev * 4
        avg_next_cmp = avg_prev * 0.5
        if avg_prev_cmp < avg_next_cmp:
            failed_partner_num = failed_partner_num + 1
            failed_partner_name = failed_partner_name + partner_name + ","
    
if failed_partner_num > 0:
    print """CRIT. {0} partners failed: {1} """.format(failed_partner_num,failed_partner_name)
    sys.exit(2)

print """OK. No partner failed."""
sys.exit(0)
