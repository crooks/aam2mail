#!/usr/bin/python
#
# vim: tabstop=4 expandtab shiftwidth=4 noautoindent
#
# nymserv.py - A Basic Nymserver for delivering messages to a shared mailbox
# such as alt.anonymous.messages.
#
# Copyright (C) 2012 Steve Crook <steve@mixmin.net>
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

import ConfigParser
from optparse import OptionParser
import os.path
from os import mkdir
import sys

def make_config():
    # Configure the Config Parser.
    config = ConfigParser.RawConfigParser()

    # By default, all the paths are subdirectories of the homedir.
    homedir = os.path.expanduser('~')

    config.add_section('mailboxes')
    config.set('mailboxes', 'do_maildir', False)
    config.set('mailboxes', 'do_mbox', False)
    config.set('mailboxes', 'maildir', os.path.join(homedir, 'Maildir'))
    config.set('mailboxes', 'mbox', os.path.join(homedir, 'mbox'))

    config.add_section('usenet')
    config.set('usenet', 'fetch_all', True)
    config.set('usenet', 'fetch_limit', 500)
    config.set('usenet', 'fetch_interval', 1 * 60 * 60)

    # All sections need to be defined before we read the config file.
    config.add_section('paths')

    # Try and process the .aam2mailrc file.  If it doesn't exist, we bailout
    # as some options are compulsory.
    if not options.rc:
        #configfile = os.path.join(homedir, '.nymservrc')
        configfile = os.path.join(homedir, '.aam2mailrc')
    else:
        configfile = options.rc
    if os.path.isfile(configfile):
        config.read(configfile)
    else:
        sys.stdout.write("%s: Config file does not exist\n" % configfile)
        sys.exit(1)

    # We have to set basedir _after_ reading the config file because
    # other paths need to default to subpaths of it.
    if config.has_option('paths', 'basedir'):
        basedir = config.get('paths', 'basedir')
    else:
        basedir = os.path.join(homedir, 'aam2mail')
        config.set('paths', 'basedir', basedir)
    if not os.path.isdir(basedir):
        mkdir(basedir)
        sys.stdout.write("%s: Created\n" % basedir)

    if not config.has_option('paths', 'etc'):
        config.set('paths', 'etc', os.path.join(basedir, 'etc'))
    p = config.get('paths', 'etc')
    if not os.path.isdir(p):
        mkdir(p)
        sys.stdout.write("%s: Created\n" % p)

    if not config.has_option('paths', 'log'):
        config.set('paths', 'log', os.path.join(basedir, 'log'))
    p = config.get('paths', 'log')
    if not os.path.isdir(p):
        mkdir(p)
        sys.stdout.write("%s: Created\n" % p)

    if not config.has_option('paths', 'run'):
        config.set('paths', 'run', os.path.join(basedir, 'run'))
    p = config.get('paths', 'run')
    if not os.path.isdir(p):
        mkdir(p)
        sys.stdout.write("%s: Created\n" % p)

    if not config.has_option('paths', 'spool'):
        config.set('paths', 'spool', os.path.join(basedir, 'spool'))
    p = config.get('paths', 'spool')
    if not os.path.isdir(p):
        mkdir(p)
        sys.stdout.write("%s: Created\n" % p)
    return config


# OptParse comes first as ConfigParser depends on it to override the path to
# the config file.
parser = OptionParser()

parser.add_option("--config", dest = "rc",
                      help = "Override .aam2mailrc location")
parser.add_option("--start", dest = "start", action = "store_true",
                      help = "Start the aam2mail daemon")
parser.add_option("--stop", dest = "stop", action = "store_true",
                      help = "Stop the aam2mail daemon")
parser.add_option("--restart", dest = "restart", action = "store_true",
                      help = "Restart the aam2mail daemon")

(options, args) = parser.parse_args()
config = make_config()
