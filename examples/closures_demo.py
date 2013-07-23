#!/usr/bin/env python
#-*- coding:utf-8 -*-

def test1(a, b):
    def test2(a):
        return 2*a
    return test2(a) + b

def test3(a, b):
    return test4(a) + b

def test4(a):
    return 2*a


def main():
    print test1(1, 1)
    print test3(1, 1)

if __name__=='__main__':
    main()
