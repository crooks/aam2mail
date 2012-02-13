#!/usr/bin/python
#
# vim: tabstop=4 expandtab shiftwidth=4 autoindent
#
# Copyright (C) 2012 Steve Crook <steve@mixmin.net>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 3, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTIBILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.

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
        crypt1 = Blowfish.new(keyhash, Blowfish.MODE_OFB,iv).encrypt(texthash)[:8]
        crypt2 = Blowfish.new(keyhash, Blowfish.MODE_OFB,crypt1).encrypt(texthash[8:])
        return (iv + crypt1 + crypt2).encode('hex')

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

def main():
    """Only used for testing purposes.  We Generate an eSub and then check it
    using the same input text."""
    e = esub()
    key = "key"
    text = "text"
    esubs = []
    esubs.append(e.bf(text, key))
    esubs.append("14857375e7174ae1dd83b80612f8a148e2777c7ae78c4c7d")
    esubs.append("fb56b638106688702dfed01fb763e3c9c29de2f46611eabe")
    esubs.append("7f338d465085b8912d15a857c0726c270655bad5e8859f2f")
    esubs.append("ac2ad32d9f603a3b1deaa57ee970a7ecfbd42717b5256328")
    esubs.append("1c5e5d8ff9ef51fe082b96a2db196d7d0e9b9933e51a4bd1")
    for sub in esubs:
        print "%s: %s" % (sub, e.check(text, key, sub))

# Call main function.
if (__name__ == "__main__"):
    main()
