#!/usr/bin/python
#
# vim: tabstop=4 expandtab shiftwidth=4 autoindent
#
# Copyright (C) 2009 Steve Crook <steve@mixmin.net>
# $Id: n2m.py 36 2010-05-27 10:03:01Z crooks $
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

import os.path
import mailbox
import sys
import nntplib

HOMEDIR = os.path.expanduser('~')
APPDIR = os.path.join(HOMEDIR, 'aam2mail')
ETCDIR = os.path.join(APPDIR, 'etc')
TMPDIR = os.path.join(APPDIR, 'tmp')
MAILDIR = os.path.join(APPDIR, 'maildir')
MBOXFILE = os.path.join(APPDIR, 'mbox', 'mbox')

# Store retrieved messages in Maildir format
do_maildir = False
# Store retrieved message in mbox format
do_mbox = True
# If True, all messages will be retreived instead of just those required.
# Bad for performance, very good for anonymity.
fetch_all = False

# ----- Don't go beyond here unless you know what you're doing! -----

class FileFunc():
    def file2list(self, filename):
        """Read a file and return each line as a list item."""
        items = []
        if os.path.isfile(filename):
            readlist = open(filename, 'r')
            for line in readlist:
                if not line.startswith('#') and len(line) > 1:
                    items.append(line.rstrip())
            readlist.close()
        return items

    def file2dict(self, filename):
        """Read a file, split each line by spaces and return a dictionary,
        keyed by the first item and with the remaining items as a list."""
        dictionary = {}
        for line in self.file2list(filename):
            fields = line.split(" ")
            key = fields.pop(0)
            dictionary[key] = fields
        return dictionary

    def dict2file(self, filename, dictionary):
        "Write a dictionary to a text file"
        textdb = open(filename, 'w')
        for key in dictionary:
            string = key
            for field in dictionary[key]:
                string += " "
                string += field
            textdb.write(string + "\n")
        textdb.close()

def GetRange(server, first, last):
    """Return a range of article numbers we should process.  We determine this
    by comparing the articles available on the server with those (if known)
    from our previous use of this server."""
    # If we've processed this server before, it should already have a
    # formatted record.
    if len(servers[server]) == 2:
        # firstdb and lastdb are set to the record numbers we last accessed
        # from this server.
        firstdb, lastdb = servers[server]
        # lastdb must be within the range the server has available.
        if lastdb >= first and lastdb <= last:
            # Our stored last number is within bounds, so believe it and return
            # it as the pointer from which to start reading articles.  We want
            # everything from that point to the last record on the server.
            return lastdb, last
        else:
            # Something is wrong, our lastread is outside the server's
            # retention.  Ignore our previous lastread and take everything the
            # server has to offer.
            art_range = int(last) - int(first)
            long_string = list2string([
              'Warn: Last read article from %s is no longer ' % server,
              'retained.  Retrieving all %s articles ' % art_range,
              'available.\n'])
            sys.stdout.write(long_string)
            return first, last
    else:
        # We have no record of reading this server so range needs to be all
        # the server has to offer.
        long_string = list2string([
          'Info: Processing server %s for the first time. ' % server,
          'All available articles %s to %s will be read.\n' % (first, last)])
        sys.stdout.write(long_string)
        return first, last

def ProcessTmp(filename):
    """Process a temporary file of xover data.  Return a dictionary keyed
    by Message-ID's for processing."""
    msgids = {}
    tmpfile = open(filename, "r")
    for line in tmpfile:
        line = line.rstrip()
        items = line.split("\t")
        subject = items[1]
        sender = items[2]
        date = items[3]
        mid = items[4]
        msgids[mid] = [subject, sender, date]
    tmpfile.close
    return msgids

def list2string(list):
    """Take a list and return it as a long string.  Useful (amongst other
    things) for writing long messages to stdout."""
    string = ""
    for line in list:
        string += line
    return string

def list2multi_line_string(list):
    """Take a list and return it as a multi-line string."""
    string = ""
    for line in list:
        string += line + "\n"
    return string

def MailPrep(msgid, sender, date, body, server):
    """Add some basic headers to our message body so it can be processed in
    Maildir format."""
    payload = "Date: %s\n" % date
    payload += "From: %s\n" % sender
    payload += "Subject: Nym message from %s\n" % server
    payload += "Message-ID: %s\n\n" % msgid
    payload += body
    return payload

filefunc = FileFunc()

if not os.path.exists(ETCDIR):
    sys.stdout.write("Error: Config Path %s does not exist\n" % ETCDIR)
    sys.exit(1)
server_file = os.path.join(ETCDIR, "servers")
# If required, configured Maildir processing
if do_maildir:
    mail_path = os.path.split(MAILDIR)[0]
    if not os.path.exists(mail_path):
        sys.stdout.write("Error: Maildir path %s does not exist\n" % mail_path)
        sys.exit(1)
    maildir = mailbox.Maildir(MAILDIR, create = True)
# If required, configure mbox processing
if do_mbox:
    mail_path = os.path.split(MBOXFILE)[0]
    if not os.path.exists(mail_path):
        sys.stdout.write("Error: Mbox path %s does not exist\n" % mail_path)
        sys.exit(1)
    mbox = mailbox.mbox(MBOXFILE, create = True)
if not os.path.exists(TMPDIR):
    sys.stdout.write("Error: Tmp Path %s does not exist\n" % TMPDIR)
    sys.exit(1)

# This section defines what type of Subjects we're interested in.  The choices
# are plain tex, hsub and esub.  These are marked for processing if the
# corresponding config file exists and contains entries.
do_text = False
do_hsub = False
do_esub = False
subj_list = filefunc.file2list(os.path.join(ETCDIR, "subject_text"))
if subj_list:
    do_text = True
    sys.stdout.write("Checking %s plain text Subjects\n" % len(subj_list))
hsub_list = filefunc.file2list(os.path.join(ETCDIR, "subject_hsub"))
if hsub_list:
    do_hsub = True
    import hsub
    sys.stdout.write("Checking %s hSub Subjects\n" % len(hsub_list))
esub_list = filefunc.file2list(os.path.join(ETCDIR, "subject_esub"))
if esub_list:
    do_esub = True
    import esub
    esub = esub.esub()
    sys.stdout.write("Checking %s eSub Subjects\n" % len(esub_list))
if not do_text and not do_hsub and not do_esub:
    sys.stdout.write("Error: No text, hsub or esub Subjects defined.\n")
    sys.exit(1)

# Populate a dictionary of news servers
servers = filefunc.file2dict(server_file)

# Dedupe maintains a list of Message-IDs so that duplicate messages
# aren't created when we have multiple news servers defined.
dedupe = []
received = 0

for server in servers:
    # Assign a temporary file name for storing xover data.  The name is based
    # on <tempdir>/<server>.tmp
    tmpfile = os.path.join(TMPDIR, server + '.tmp')
    news = nntplib.NNTP(server, readermode = True)
    # group returns: response, count, first, last, name
    resp, grpcount, \
    grpfirst, grplast, grpname = news.group('alt.anonymous.messages')
    first, last = GetRange(server, grpfirst, grplast)
    msgcnt = int(last) - int(first)
    sys.stdout.write("Processing %d messages from %s\n" % (msgcnt, server))
    if msgcnt == 0:
        sys.stdout.write("Nothing to be read.\n")
        news.quit()
        continue
    # The following xover line is often remarked out during testing as this
    # preserves a constant tmpfile.
    #news.xover(first, last, tmpfile)

    # Create a dictionary keyed by Message-ID, containing the Subject and Date.
    msgids = ProcessTmp(tmpfile)

    # Process our previously created dictionary of Message-ID's.
    for msgid in msgids:
        # Skip checking messages if we already have this Message-ID
        if msgid in dedupe:
            continue
        else:
            # Add the Message-ID to the dedupe list.  We won't need it again.
            dedupe.append(msgid)
        subject, sender, date = msgids[msgid]
        # Retreive the actual payload.  This is amazingly inefficient as we
        # could just get the ones we want but that's bad for anonymity.
        if fetch_all:
            # The tuple returned by nntp.body includes the actual body as a
            # list object as the fourth element, hence [3].
            body = list2multi_line_string(news.body(msgid)[3])
        wanted = False
        if do_text and subject in subj_list:
            wanted = True
        if not wanted and do_hsub:
            for subj in hsub_list:
                if hsub.check(subj, subject):
                    wanted = True
                    break
        if not wanted and do_esub:
            for subj in esub_list:
                # In our esub file, we assume Subject and Key are separated
                # by a tab.
                encsub, key = subj.split("\t", 1)
                if esub.check(encsub, key, subject):
                    wanted = True
                    break
        if wanted:
            if not fetch_all:
                body = list2multi_line_string(news.body(msgid)[3])
            # Create the message in the Maildir
            if do_maildir:
                maildir.add(MailPrep(msgid, sender, date, body, server))
            if do_mbox:
                mbox.add(MailPrep(msgid, sender, date, body, server))
            # Increment the received message count
            received += 1
    news.quit()
    # That went well, so update our recorded first/last article numbers.
    servers[server] = [first, last]
if do_maildir:
    maildir.close()
if do_mbox:
    mbox.close()
sys.stdout.write("Received %d messages\n" % received)
# Write the revised server db
filefunc.dict2file(server_file, servers)

