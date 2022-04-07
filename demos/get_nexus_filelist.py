#!/bin/env python
#
# Get list of all artifacts from a Nexus raw repository and write into file_list.txt
# Author: Damon Guo

import requests
import json

def get_list(api_url,repo_name,file_list,continuation_token):
    headers = {"content-type":"application/json"}

    if continuation_token:
        res = requests.get(api_url,headers=headers,stream=True,params={'repository':repo_name,'continuationToken':continuation_token},timeout=5)
    else:
        res = requests.get(api_url,headers=headers,stream=True,params={'repository':repo_name},timeout=5)

    data = res.json()
    for item in data["items"]:
        url_subpath = item["path"]
        file_list.append(url_subpath)

    continuation_token = data["continuationToken"]

    return {"file_list":file_list,"continuation_token":continuation_token}

if __name__ == '__main__':

    api_url = "http://nexus.heylinux.com:8081/service/rest/v1/search/assets"
    repo_name = "heylinux-repo-raw"

    init_file_list = []
    init_res_data = get_list(api_url,repo_name,init_file_list,continuation_token=False)

    file_list = init_res_data["file_list"]
    continuation_token = init_res_data["continuation_token"]

    while continuation_token:
        res_data = get_list(api_url,repo_name,file_list,continuation_token)
        file_list = res_data["file_list"]
        continuation_token = res_data["continuation_token"]

    with open('file_list.txt', 'w') as f:
        for item in file_list:
            f.write("%s\n" % item)
