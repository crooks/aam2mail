#!/usr/bin/python
#
# vim: tabstop=4 expandtab shiftwidth=4 autoindent
#
# Copyright (C) 2009 Steve Crook <steve@mixmin.net>
# $Id$
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTIBILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.

from Crypto.Cipher import Blowfish
from hashlib import md5
from os import urandom

class esub:
    def bf(self, text, key, iv = None):
        """Produce a 192bit Encrypted Subject. The first 64 bits are the
        Initialization vector used in the Blowfish CFB Mode.  The Subject text
        is MD5 hashed and then encrypted using an MD5 hash of the Key."""
        texthash = md5(text).digest()
        keyhash = md5(key).digest()
        if iv is None: iv = urandom(8)
        crypt = Blowfish.new(keyhash, Blowfish.MODE_CFB, iv).encrypt(texthash)
        return (iv + crypt).encode('hex')

    def check(self, text, key, esub):
        """Extract the IV from a passed eSub and generate another based on it,
        using a passed Subject and Key.  If the resulting eSub collides with
        the supplied one, return True."""
        # All eSubs should be 48 bytes long
        if len(esub) != 48: return False
        # The 64bit IV is hex encoded (16 digits) at the start of the esub.
        try:
            iv = esub[:16].decode('hex')
        except TypeError:
            return False
        return (self.bf(text, key, iv) == esub)
