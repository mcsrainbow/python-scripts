#!/usr/bin/env python
#-*- coding:utf-8 -*-

# Description: To receive alerts from Cloudera Manager Alert Publisher then send to Slack "cm-alerts" channel
# Author: Dong Guo
# Last modified: 2016-09-18

import sys
import json
import requests
import textwrap

if len(sys.argv) < 2 or '-h' in sys.argv:
    print "Usage: {0} [/path/to/json_alert_file]".format(sys.argv[0])
    sys.exit(1)

slack_webhook_url = 'https://hooks.slack.com/services/YOUR/WEBHOOK/URLSTRING'
slack_bot_name = 'Alert Publisher'
slack_bot_icon_url = 'http://www.cloudera.com/content/dam/www/static/images/logos/cloudera-card.jpg'
slack_channel = 'cm-alerts'

json_alert_file = sys.argv[1]

with open(json_alert_file) as data_file:
    json_data = json.load(data_file)

    for alert_item in json_data:
        alert_content = alert_item['body']['alert']['content']
        alert_url = alert_item['body']['alert']['source']
        alert_severity = ','.join(alert_item['body']['alert']['attributes']['SEVERITY'])
        alert_summary = ','.join(alert_item['body']['alert']['attributes']['ALERT_SUMMARY'])
        cluster_name = ','.join(alert_item['body']['alert']['attributes']['CLUSTER_DISPLAY_NAME'])
        
        slack_severity_color = '#FF9999'
        
        slack_noti_msg = textwrap.dedent('''
                         *Cluster*: {0}
                         *Summary*: {1}
                         *Severity*: {2}
                         *URL*: {3}
                         *Content*: _ {4} _'''.format(cluster_name,alert_summary,alert_severity,alert_url,alert_content))
    
        payload = {
            'channel': slack_channel,
            'username': slack_bot_name,
            'icon_url': slack_bot_icon_url,
            'attachments': [{
              'color': slack_severity_color,
              'text': slack_noti_msg,
              'mrkdwn_in': [ 'text' ]
            }]
        }
        
        try:
            req = requests.post(slack_webhook_url,
                                data=json.dumps(payload),
                                headers={'content-type':'application/json'},
                                timeout=10)
        except Exception as error:
            print "Error occured while posting data to Slack: {0}".format(str(error))
            sys.exit(1)
        
        print "Respone code is {0}".format(req.status_code)
