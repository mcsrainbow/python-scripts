#!/usr/bin/env python
#-*- coding:utf-8 -*-

# Description: Run playbooks with Ansible API
# Author: Dong Guo
# Last modified: 2016-11-15

import os
import sys

from ansible.executor import playbook_executor
from ansible.inventory import Inventory
from ansible.parsing.dataloader import DataLoader
from ansible.vars import VariableManager

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()

WORKHOME='/opt/ansible'

def parse_opts():
    """Help messages(-h, --help)."""

    import textwrap
    import argparse

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
        '''
        examples:
          {0} heydevops.cloud.yml -i heydevops.cloud.hosts --tags common --limit devops-01.heylinux.com
        '''.format(__file__)
        ))

    parser.add_argument('playbook', action="store", type=str)
    parser.add_argument('-i', metavar='inventory', type=str, required=True, help='the inventory hosts file')
    parser.add_argument('--tags', metavar='tag', type=str, help='the tag name')
    parser.add_argument('--limit', metavar='subset', type=str, help='the subset host or group')
    args = parser.parse_args()

    return {'playbook':args.playbook, 'inventory_file':args.i, 'tags':args.tags, 'subset':args.limit}


class Options(object):
    """
    Options class to replace Ansible OptParser
    """
    def __init__(self, **kwargs):
        props = (
            'ask_pass', 'ask_sudo_pass', 'ask_su_pass', 'ask_vault_pass',
            'become_ask_pass', 'become_method', 'become', 'become_user',
            'check', 'connection', 'diff', 'extra_vars', 'flush_cache',
            'force_handlers', 'forks', 'inventory', 'listhosts', 'listtags',
            'listtasks', 'module_path', 'module_paths',
            'new_vault_password_file', 'one_line', 'output_file',
            'poll_interval', 'private_key_file', 'python_interpreter',
            'remote_user', 'scp_extra_args', 'seconds', 'sftp_extra_args',
            'skip_tags', 'ssh_common_args', 'ssh_extra_args', 'subset', 'sudo',
            'sudo_user', 'syntax', 'tags', 'timeout', 'tree',
            'vault_password_files', 'verbosity')

        for p in props:
            if p in kwargs:
                setattr(self, p, kwargs[p])
            else:
                setattr(self, p, None)


class Runner(object):
    def __init__(self, playbook, display, hosts=None, options={}, passwords={}, vault_pass=None):

        self.options = Options()
        for k, v in options.iteritems():
            setattr(self.options, k, v)

        self.display = display
        self.display.verbosity = self.options.verbosity
        # executor has its own verbosity setting
        playbook_executor.verbosity = self.options.verbosity

        # gets data from YAML/JSON files
        self.loader = DataLoader()
        if vault_pass is not None:
            self.loader.set_vault_password(vault_pass)
        elif 'VAULT_PASS' in os.environ:
            self.loader.set_vault_password(os.environ['VAULT_PASS'])

        # all the variables from all the various places
        self.variable_manager = VariableManager()
        if self.options.python_interpreter is not None:
            self.variable_manager.extra_vars = {
                'ansible_python_interpreter': self.options.python_interpreter
            }

        # set inventory, using most of above objects
        self.inventory = Inventory(
            loader=self.loader, variable_manager=self.variable_manager,
            host_list=hosts)

        if len(self.inventory.list_hosts()) == 0:
            self.display.error("Provided hosts list is empty.")
            sys.exit(1)

        self.inventory.subset(self.options.subset)

        if len(self.inventory.list_hosts()) == 0:
            self.display.error("Specified limit does not match any hosts.")
            sys.exit(1)

        self.variable_manager.set_inventory(self.inventory)

        # setup playbook executor, but don't run until run() called
        self.pbex = playbook_executor.PlaybookExecutor(
            playbooks=[playbook],
            inventory=self.inventory,
            variable_manager=self.variable_manager,
            loader=self.loader,
            options=self.options,
            passwords=passwords)

    def run(self):
        # run playbook and get stats
        self.pbex.run()
        stats = self.pbex._tqm._stats

        return stats


def main():
    if len(sys.argv) < 2:
        os.system(__file__ + ' -h')
        return 2

    # locate ansible workhome
    os.chdir(WORKHOME)

    # get parameters
    opts = parse_opts()
    
    # run ansible playbook
    runner = Runner(
        playbook=opts['playbook'],
        hosts=opts['inventory_file'],
        display=display,
        options={
            'connection': 'ssh',
            'private_key_file': 'sshkeys/heydevops_root',
            'subset': opts['subset'],
            'tags': opts['tags'],
            'remote_user': 'root',
            'verbosity': 0,
        },
        vault_pass='vault_password',
    )

    stats = runner.run()

    return 0

if __name__ == '__main__':
    main()
