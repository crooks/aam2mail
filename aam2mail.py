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
SPOOLDIR = os.path.join(APPDIR, 'spool')

# ----- Don't go beyond here unless you know what you're doing! -----

def file2list(filename):
    """Read a file and return each line as a list item."""
    items = []
    if os.path.isfile(filename):
        readlist = open(filename, 'r')
        for line in readlist:
            # This beast just strips comments from read lines.
            content = line.split('#', 1)[0].rstrip()
            # If a line starts with a #, content will be length zero
            if len(content) > 0:
                items.append(content)
        readlist.close()
    return items

def file2dict(filename, numeric = False):
    """Read a file and split each line at the first space encountered. The
    first element is the key, the rest is the content. If numeric is True
    then only integer values will be excepted."""
    d = {}
    for line in file2list(filename):
        fields = line.split(" ", 1)
        k = fields[0]
        c = fields[1]
        if numeric:
            try:
                c = int(c)
            except ValueError:
                c = 0
            d[k] = c
        else:
            d[k] = c.strip()
    return d

def dict2file(filename, d):
    "Write a dictionary to a text file"
    f = open(filename, 'w')
    for k in d:
        # In theory we shouldn't need to strip this, but in practice, theory
        # and practice are frequently different.
        f.write("%s %s\n" % (k.strip(), d[k]))
    f.close()

def get_range(server, maxart, sfirst, slast, himark):
    """Return a range of article numbers we should process.  We determine this
    by comparing the articles available on the server with those (if known)
    from our previous use of this server."""
    first = int(sfirst)
    last = int(slast)

    if himark >= first and himark <= last:
        # This is the normal state of affairs. Our himark lies between the
        # server's high and low. We update first with our last himark.
        first = himark

    # If more than 500 articles to read, prompt for how many.
    howmany = last - first
    if howmany > maxart:
        prompt = "%s: " % server
        prompt += "How many articles to read? (0 - %s): " % howmany
        n = -1
        while n < 0 or n > howmany:
            s = raw_input(prompt)
            # The raw_input function takes a string so we need to check it.
            try:
                n = int(s)
            except ValueError:
                n = -1
        # We got an acceptable answer from our prompt.  Now set first to the
        # number of articles we want to read.
        first = last - n
    return str(first), slast

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

def isopt(cfg, opt):
    if opt in cfg and opt[cfg]:
        return True
    return False

# Do some basic checks that our required directories exist.
if not os.path.isdir(ETCDIR):
    sys.stdout.write("Error: Config Path %s does not exist\n" % ETCDIR)
    sys.exit(1)
if not os.path.isdir(SPOOLDIR):
    sys.stdout.write("Error: Config Path %s does not exist\n" % SPOOLDIR)
    sys.exit(1)

cfgfile = os.path.join(ETCDIR, 'config')
if not os.path.isfile(cfgfile):
    sys.stdout.write("Error: Config file %s does not exist\n" % cfgfile)
    sys.exit(1)
cfg = file2dict(cfgfile)
opts = 'do_maildir do_mbox maildir mboxfile fetch_all fetch_limit'
optlist = opts.split(" ")
for opt in optlist:
    if not opt in cfg: cfg[opt] = False
# These options depend on others.
if not cfg['maildir']: cfg['do_maildir'] = False
if not cfg['mboxfile']: cfg['do_mbox'] = False

# If required, configured Maildir processing
if cfg['do_maildir']:
    maildir = os.path.join(HOMEDIR, 'Maildir', cfg['maildir'])
    mail_path = os.path.split(maildir)[0]
    if not os.path.exists(mail_path):
        sys.stdout.write("Error: Maildir path %s does not exist\n" % mail_path)
        sys.exit(1)
    maildir = mailbox.Maildir(maildir, create = True)
# If required, configure mbox processing
if cfg['do_mbox']:
    mboxfile = os.path.join(HOMEDIR, cfg['mboxfile'])
    mail_path = os.path.split(mboxfile)[0]
    if not os.path.exists(mail_path):
        sys.stdout.write("Error: Mbox path %s does not exist\n" % mail_path)
        sys.exit(1)
    mbox = mailbox.mbox(mboxfile, create = True)
if not os.path.exists(SPOOLDIR):
    sys.stdout.write("Error: Spool Path %s does not exist\n" % SPOOLDIR)
    sys.exit(1)

# This section defines what type of Subjects we're interested in.  The choices
# are plain text, hsub and esub.  These are marked for processing if the
# corresponding config file exists and contains entries.
do_text = False
do_hsub = False
do_esub = False
subj_list = file2list(os.path.join(ETCDIR, "subject_text"))
if subj_list:
    do_text = True
    sys.stdout.write("Checking %s plain text Subjects\n" % len(subj_list))
hsub_list = file2list(os.path.join(ETCDIR, "subject_hsub"))
if hsub_list:
    do_hsub = True
    import hsub
    hsub = hsub.hsub()
    sys.stdout.write("Checking %s hSub Subjects\n" % len(hsub_list))
esub_list = file2list(os.path.join(ETCDIR, "subject_esub"))
if esub_list:
    do_esub = True
    import esub
    esub = esub.esub()
    sys.stdout.write("Checking %s eSub Subjects\n" % len(esub_list))
if not do_text and not do_hsub and not do_esub:
    sys.stdout.write("Error: No text, hsub or esub Subjects defined.\n")
    sys.exit(1)

# Populate the himarks dict and sync is with our etc/servers text file.
server_file = os.path.join(ETCDIR, "servers")
himark_file = os.path.join(SPOOLDIR, "servers")
servers = file2list(server_file)
himarks = file2dict(himark_file, numeric = True)
# Add missing servers
for server in servers:
    if server not in himarks:
        himarks[server] = 0
# Delete unwanted servers
for server in himarks:
    if server not in servers:
        del himarks[server]

# Dedupe maintains a list of Message-IDs so that duplicate messages
# aren't created when we have multiple news servers defined.
dedupe = []
received = 0

for server in himarks:
    # Assign a temporary file name for storing xover data.  The name is based
    # on <tempdir>/<server>.tmp
    spool = os.path.join(SPOOLDIR, server + '.tmp')

    # Establish a connection with the newsserver.
    news = nntplib.NNTP(server, readermode = True)
    # group returns: response, count, first, last, name
    resp, grpcount, \
    grpfirst, grplast, grpname = news.group('alt.anonymous.messages')
    first, last = get_range(server, cfg['fetch_limit'], grpfirst, grplast,
                            himarks[server])
    msgcnt = int(last) - int(first)
    sys.stdout.write("Processing %d messages from %s\n" % (msgcnt, server))
    if msgcnt == 0:
        sys.stdout.write("Nothing to be read.\n")
        news.quit()
        continue
    # The following xover line is often remarked out during testing as this
    # preserves a constant tmpfile.
    news.xover(first, last, spool)

    # Create a dictionary keyed by Message-ID, containing the Subject and Date.
    #msgids = xover2dict(spool)

    s = open(spool, "r")
    for ov in s:
        ov2 = ov.rstrip()
        items = ov2.split("\t")
        subject = items[1]
        sender = items[2]
        date = items[3]
        msgid = items[4]

        # Skip checking messages if we already have this Message-ID
        if msgid in dedupe:
            continue
        else:
            # Add the Message-ID to the dedupe list.  We won't need it again.
            dedupe.append(msgid)

        # Retreive the actual payload.  This is amazingly inefficient as we
        # could just get the ones we want but that's bad for anonymity.
        if cfg['fetch_all']:
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
            if not cfg['fetch_all']:
                body = list2multi_line_string(news.body(msgid)[3])
            # Create the message in the Maildir
            if cfg['do_maildir']:
                maildir.add(MailPrep(msgid, sender, date, body, server))
            if cfg['do_mbox']:
                mbox.add(MailPrep(msgid, sender, date, body, server))
            # Increment the received message count
            received += 1
    news.quit()
    # That went well, so update our recorded himark.
    himarks[server] = int(last)
if cfg['do_maildir']:
    maildir.close()
if cfg['do_mbox']:
    mbox.close()
sys.stdout.write("Received %d messages\n" % received)
# Write the revised server db
dict2file(himark_file, himarks)

