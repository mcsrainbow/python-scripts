#!/usr/bin/env python
#-*- coding:utf-8 -*-

# Seek specific string from a log file incrementally and
# count the number of the lines including the string

import os
import re
import sys
import yaml

YAML_DATA = '/var/tmp/logs_seek_pos.yml'

def parse_opts():
    """Help messages(-h, --help)."""

    import textwrap
    import argparse

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
        '''
        examples:
          {0} --file_path /var/log/messages --seek_str "HANDLING MCE MEMORY ERROR"
          {0} --file_path /var/log/messages --seek_str "kernel:\s\[[\d\.]+\]\svw\[\d+\]:\ssegfault"
          {0} --file_path /var/log/messages --seek_str "mdadm.*: Rebuild.*event detected"
          {0} --file_path /var/log/nginx/error.log --seek_str "style.css" --ignore_str "No such file or directory"
        '''.format(__file__)
        ))

    parser.add_argument('--file_path', type=str, required=True, help='the file path')
    parser.add_argument('--seek_str', type=str, required=True, help='the string to seek')
    parser.add_argument('--ignore_str', type=str, help='the string to ignore')

    if len(sys.argv) < 2:
        parser.print_help()
        sys.exit(2)

    args = parser.parse_args()

    return {'file_path':args.file_path, 'seek_str':args.seek_str, 'ignore_str':args.ignore_str}

def get_last_seek_pos(file_path,seek_str):
    with open(YAML_DATA) as f:
        data_dict = yaml.load(f)
        if not data_dict['logs'].has_key(file_path):
            last_seek_pos = 0
        else:
            if not data_dict['logs'][file_path].has_key(seek_str):
                last_seek_pos = 0
            else:
                last_seek_pos = data_dict['logs'][file_path][seek_str]

    return last_seek_pos

def save_last_seek_pos(file_path,last_seek_pos,seek_str):

    seek_f = open(file_path,'r')
    seek_f.seek(0,2)
    last_seek_pos = seek_f.tell()
    seek_f.close()

    with open(YAML_DATA) as f:
        data_dict = yaml.load(f)
        if not data_dict['logs'].has_key(file_path):
            data_dict['logs'][file_path] = {}

        data_dict['logs'][file_path][seek_str] = last_seek_pos

    with open(YAML_DATA, 'w') as f:
        yaml.dump(data_dict, f, default_flow_style=False)

    return True

def get_seek_count(file_path,seek_str,ignore_str=None):
    last_seek_pos = get_last_seek_pos(file_path,seek_str)

    seek_f = open(file_path,'r')
    seek_f.seek(last_seek_pos,0)
    seek_count = 0
    lines = seek_f.readlines()
    for line in lines:
        if ignore_str is not None:
            if re.search(seek_str,line) and not re.search(ignore_str,line):
                seek_count = seek_count + 1
        else:
            if re.search(seek_str,line):
                seek_count = seek_count + 1
    seek_f.close()

    save_last_seek_pos(file_path,last_seek_pos,seek_str)

    return seek_count

def main():
    if not os.path.exists(YAML_DATA):
        with open(YAML_DATA, "w") as seek_f:
            seek_f.write("logs: {}")

    opts = parse_opts()
    seek_count = get_seek_count(opts['file_path'],opts['seek_str'],opts['ignore_str'])

    print(seek_count)
    return 0

if __name__ == '__main__':
    sys.exit(main())
