#!/usr/bin/env python
#-*- coding:utf-8 -*-

def test1(**kwargs):
    print kwargs['name']
    print kwargs['age']
    print kwargs['sex']

def test2(*args):
    print args[0]
    print args[1]
    print args[2]


def main():
    test1(name='GuoDong', age=18, sex='boy')
    test2('GuoDong', 18, 'boy')

if __name__=='__main__':
    main()
