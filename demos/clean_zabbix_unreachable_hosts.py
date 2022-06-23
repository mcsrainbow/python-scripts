#!/usr/bin/env python
#-*- coding:utf-8 -*-

# Description: Clean Zabbix unreachable hosts
# Author: Damon Guo

import os
import sys
import requests
import json

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def parse_opts():
    """Help messages(-h, --help)."""

    import textwrap
    import argparse

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
        '''
        examples:
          {0} -u https://zabbix.heylinux.com -a username:password -g hostgroup1,hostgroup2
        '''.format(__file__)
        ))

    parser.add_argument('-u', metavar='url', type=str, required=True, help='Zabbix URL')
    parser.add_argument('-a', metavar='auth', type=str, required=True, help='username:password for authentication token')
    parser.add_argument('-g', metavar='hostgroup', type=str, required=True, help='hostgroup1,hostgroup2,...')

    args = parser.parse_args()
    return {'url':args.u, 'auth':args.a, 'hostgroup':args.g}

def cleanup(opts):
    """Clean unreachable hosts with given parameters."""

    url = "{0}/api_jsonrpc.php".format(opts['url'])

    username = opts['auth'].split(':')[0]
    password = opts['auth'].split(':')[1]

    hostgroup_list = opts['hostgroup'].split(',')
    headers = {"Content-Type": "application/json-rpc"}

    json_data_1 = {
                    "jsonrpc":"2.0",
                    "method":"user.login",
                    "params":{
                      "user":username,
                      "password":password},
                    "id":1
                  }
    try:
        res_1 = requests.post(url, headers=headers, json=json_data_1, verify=False, timeout=5)
        if res_1.status_code == requests.codes.ok:
            res_1_dict = res_1.json()

            # get authentication token
            auth_token = res_1_dict["result"]

            # get hostgroup ids
            json_data_2 = {
                            "jsonrpc": "2.0",
                            "method": "hostgroup.get",
                            "params": {
                              "output": "extend",
                              "filter": {
                                "name": hostgroup_list
                              }
                            },
                            "auth": auth_token,
                            "id": 2
                          }

            res_2 = requests.post(url, headers=headers, json=json_data_2, verify=False, timeout=5)
            if res_2.status_code == requests.codes.ok:
                res_2_dict = res_2.json()

                hostgroup_ids = []
                for item in res_2_dict["result"]:
                    hostgroup_ids.append(item["groupid"])

            # get hosts by hostgroup ids
            """
                "type"      : "1" -> Agent
                "available" : "0" -> Unknown
                "available" : "1" -> Successfully connected
                "available" : "2" -> Error in connecting
            """
            json_data_3 = {
                            "jsonrpc": "2.0",
                            "method": "host.get",
                            "params": {
                              "output": ["host","interfaces"],
                              "groupids": hostgroup_ids,
                              "selectInterfaces": ["available"],
                              "selectGroups": ["name"],
                              "filter": {
                                "type": 1
                              }
                              },
                            "auth": auth_token,
                            "id": 3
                          }

            res_3 = requests.post(url, headers=headers, json=json_data_3, verify=False, timeout=5)
            if res_3.status_code == requests.codes.ok:
                res_3_dict = res_3.json()
                #print(json.dumps(res_3_dict,indent=2))

                unreachable_hosts_list = []
                for item in res_3_dict["result"]:
                    if item["interfaces"][0]["available"] == "2":
                        unreachable_hosts_list.append(item["hostid"])
                        group_names = []
                        for group in item["groups"]:
                            if group["name"] != "Discovered hosts":
                                group_names.append(group["name"])
                        print("INFO: Found unreachable host: '{0}' from hostgroup: '{1}'".format(item["host"],",".join(group_names)))

            # delete unreachable host
            json_data_4 = {
                            "jsonrpc": "2.0",
                            "method": "host.delete",
                            "params": unreachable_hosts_list,
                            "auth": auth_token,
                            "id": 4
                          }

            if len(unreachable_hosts_list) > 0:
                res_4 = requests.post(url, headers=headers, json=json_data_4, verify=False, timeout=5)
                if res_4.status_code == requests.codes.ok:
                    res_4_dict = res_4.json()
                    print("INFO: Deleted above {0} unreachable hosts".format(len(unreachable_hosts_list)))
            else:
                print("INFO: No such unreachable host")

        else:
            print("StatusCode: {0}, Error: {1}".format(res_1.status_code,res_1.content))

    except KeyError:
        print("Exception: KeyError")

    except IndexError:
        print("Exception: IndexError")

    except requests.exceptions.Timeout:
        print("Exception: Timeout")

    except requests.exceptions.ConnectionError:
        print("Exception: ConnectionError")

    return True

def main():
    if len(sys.argv) < 2:
        os.system(__file__ + " -h")
        return 2

    opts = parse_opts()
    cleanup(opts)

    return 0

if __name__=='__main__':
    sys.exit(main())
