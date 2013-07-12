#!/usr/bin/env python
#-*- coding:utf-8 -*-

# FileName: no_elif.py
# Date: Sat 13 Apr 2013 03:22:41 AM CST
# Author: Dong Guo

class A(object):
    def __init__(self):
        self._funcs = {
                'apple': self._show_apple,
                'lemon': self._show_lemon,
                'mango': self._show_mango
                }

    def _show_apple(self, person):
        print '{0} eat apple'.format(person)

    def _show_lemon(self, person):
        print '{0} eat lemon'.format(person)

    def _show_mango(self, person):
        print '{0} eat mango'.format(person)


    def eat1(self, person, fruit):
        if not self._funcs.has_key(fruit):
            return
        self._funcs[fruit](person)

    def eat2(self, person, fruit):
        if fruit == 'apple':
            self._show_apple(person)
        elif fruit == 'lemon':
            self._show_lemon(person)
        elif fruit == 'mango':
            self._show_mango(person)

def main():
    a = A()
    a.eat1('Guodong', 'mango')
    a.eat2('Luoshanjie', 'apple')

if __name__=='__main__':
    main()
