# Description: HTTP requests check for Zabbix
# Author: Dong Guo

import sys
import requests
import time
import argparse
import textwrap

def parse_opts():
    """Help messages(-h, --help)."""

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
        '''
        examples:
          {0} -u idc1-web1/health
          {0} -u http://idc1-web1/health
          {0} -u http://idc1-web1/health -c ok
          {0} -u http://idc1-web1/health -c ok -V
          {0} -u http://idc1-web1/health -c ok -t 2 -V
          {0} -u http://idc1-web2:3000
          {0} -u http://idc1-web3/login.php?page=redirect_string -a username:password -V
          {0} -u https://idc2-web1.yourdomain.com -V
        '''.format(__file__)
        ))

    parser.add_argument('-u', metavar='url', type=str, required=True, help='URL to GET or POST [default: http://]')
    parser.add_argument('-t', metavar='timeout', type=float, help='seconds before connection times out [default: 10]')
    parser.add_argument('-c', metavar='content', type=str, help='string to expect in the content')
    parser.add_argument('-a', metavar='auth', type=str, help='username:password on sites with basic authentication')
    parser.add_argument('-V', action="store_true", default=False, help='return actual value instead of 0 and 1')
    parser.add_argument('-p', metavar='payload', type=str, help='URL encoded http POST data')

    if len(sys.argv) < 2:
        parser.print_help()
        sys.exit(2)

    args = parser.parse_args()

    if args.a:
        if ':' not in args.a or len(args.a.split(':')) != 2:
            print("Invalid auth format. Expected username:password")
            sys.exit(2)

    return {'url': args.u, 'timeout': args.t, 'content': args.c, 'auth': args.a, 'value': args.V, 'payload': args.p}

def get_results(opts):
    """Get results with given parameters."""

    url = opts['url']
    if "http://" not in url and "https://" not in url:
        url = "http://" + url

    start_timestamp = time.time()
    if opts.get('timeout'):
        timeout = opts['timeout']
    else:
        timeout = 10
    try:
        if opts.get('auth'):
            from requests.auth import HTTPBasicAuth
            username, password = opts['auth'].split(':')
            httpauth = HTTPBasicAuth(username, password)
            if opts.get('payload'):
                payload = opts['payload']
                req = requests.post(url, data=payload, auth=httpauth, timeout=timeout)
            else:
                req = requests.get(url, auth=httpauth, timeout=timeout)
        else:
            if opts.get('payload'):
                payload = opts['payload']
                req = requests.post(url, data=payload, timeout=timeout)
            else:
                req = requests.get(url, timeout=timeout)

        end_timestamp = time.time()
        response_secs = round(end_timestamp - start_timestamp, 3)

        if opts.get('value'):
            if opts.get('content'):
                print(req.content.decode('utf-8'))
            elif opts.get('timeout'):
                print(response_secs)
            else:
                print(req.status_code)
        else:
            if req.status_code == requests.codes.ok:
                if opts.get('content'):
                    if opts['content'] in req.content.decode('utf-8'):
                        print(0)
                    else:
                        print(1)
                else:
                    print(0)
            else:
                print(1)

    except requests.exceptions.Timeout:
        print("Timeout" if opts.get('value') else 1)

    except requests.exceptions.ConnectionError:
        print("ConnectionError" if opts.get('value') else 1)

    except Exception as e:
        print(f"Unexpected error: {str(e)}" if opts.get('value') else 1)
        return 2

    return 0

def main():
    opts = parse_opts()
    return get_results(opts)

if __name__ == '__main__':
    sys.exit(main())
