#!/bin/env python

# Description: Low-level Discovery script for zcron
# Author: Dong Guo

import os
import sys
import json
import yaml
import glob

ymldata = "/var/tmp/zcron.yml"

read_files = glob.glob("/var/tmp/zcron_*.yml")
with open(ymldata, "wb") as outfile:
    for f in read_files:
        with open(f, "rb") as infile:
            outfile.write(infile.read())

if not os.path.isfile(ymldata) or os.stat(ymldata).st_size == 0:
    sys.stderr.write("Cannot read data from YAML data file: {0}\n".format(ymldata))
    sys.exit(1)

os.chmod(ymldata, 0666)
with open(ymldata) as f:
    data_dict = yaml.load(f)

cron_jobs = []
for key, value in data_dict.iteritems():
    cron_jobs +=  [{'{#JOBNAME}': key}] 

print json.dumps({'data':cron_jobs}, sort_keys=True, indent=2)
