#!/bin/env python

# Description: Low-level Discovery script for zcron
# Author: Dong Guo

import os
import sys
import yaml
import glob

if len(sys.argv) < 3:
    sys.stderr.write("Usage: {0} jobname [return_code|exec_time]\n".format(__file__))
    sys.exit(1)

ymldata = "/var/tmp/zcron.yml"
read_files = glob.glob("/var/tmp/zcron_*.yml")

with open(ymldata, "wb") as outfile:
    for f in read_files:
        with open(f, "rb") as infile:
            outfile.write(infile.read())

jobname = sys.argv[1]
keytype = sys.argv[2]

if not os.path.isfile(ymldata) or os.stat(ymldata).st_size == 0:
    sys.stderr.write("Cannot read data from YAML data file: {0}\n".format(ymldata))
    sys.exit(1)

os.chmod(ymldata, 0666)
with open(ymldata) as f:
    data_dict = yaml.load(f)

print data_dict[jobname][keytype]
