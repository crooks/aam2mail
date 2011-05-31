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

class aam():
    def __init__(self):
        # Do some basic checks that our required directories exist.
        if not os.path.isdir(ETCDIR):
            errmsg = "Error: Config Path %s does not exist\n" % ETCDIR
            sys.stderr.write(errmsg)
            sys.exit(1)
        if not os.path.isdir(SPOOLDIR):
            errmsg = "Error: Config Path %s does not exist\n" % SPOOLDIR
            sys.stderr.write(errmsg)
            sys.exit(1)

        cfg = self.get_config()

        # This section defines what type of Subjects we're interested in.  The
        # choices are plain text, hsub and esub.  These are marked for
        # processing if the corresponding config file exists and contains
        # entries.
        do_text = False
        do_hsub = False
        do_esub = False
        subj_list = self.file2list(os.path.join(ETCDIR, "subject_text"))
        if subj_list:
            do_text = True
            self.subj_list = subj_list
            logmsg = "Checking %s plain text Subjects\n" % len(subj_list)
            sys.stdout.write(logmsg)
        hsub_list = self.file2list(os.path.join(ETCDIR, "subject_hsub"))
        if hsub_list:
            do_hsub = True
            import hsub
            self.hsub = hsub.hsub()
            self.hsub_list = hsub_list
            sys.stdout.write("Checking %s hSub Subjects\n" % len(hsub_list))
        esub_list = self.file2list(os.path.join(ETCDIR, "subject_esub"))
        if esub_list:
            do_esub = True
            import esub
            self.esub = esub.esub()
            self.esub_list = esub_list
            sys.stdout.write("Checking %s eSub Subjects\n" % len(esub_list))
        if not do_text and not do_hsub and not do_esub:
            errmsg = "Error: No text, hsub or esub Subjects defined.\n"
            sys.stderr.write(errmsg)
            sys.exit(1)

        # Populate the himarks dict and sync it with our etc/servers text file.
        server_file = os.path.join(ETCDIR, "servers")
        himark_file = os.path.join(SPOOLDIR, "servers")
        servers = self.file2list(server_file)
        himarks = self.file2dict(himark_file, numeric = True)
        # Add missing servers
        for server in servers:
            if server not in himarks:
                himarks[server] = 0
        # Delete unwanted servers
        for server in himarks:
            if server not in servers:
                del himarks[server]
        # Set the scope on our variables
        self.cfg = cfg
        self.do_text = do_text
        self.do_hsub = do_hsub
        self.do_esub = do_esub
        self.himarks = himarks
        self.himark_file = himark_file

    def get_config(self):
        """Read the configuration from a file and write it to a dictionary."""
        cfgfile = os.path.join(ETCDIR, 'config')
        if not os.path.isfile(cfgfile):
            errmsg = "Error: Config file %s does not exist\n" % cfgfile
            sys.stdout.write(errmsg)
            sys.exit(1)
        cfg = self.file2dict(cfgfile)
        opts = 'do_maildir do_mbox maildir mboxfile fetch_all fetch_limit'
        optlist = opts.split(" ")
        for opt in optlist:
            if not opt in cfg: cfg[opt] = False
        # These options depend on others.
        if not cfg['maildir']: cfg['do_maildir'] = False
        if not cfg['mboxfile']: cfg['do_mbox'] = False
        if not cfg['do_maildir'] and not cfg['do_mbox']:
            errmsg = "Error: We're not configured to write Maildir or Mbox "
            errmsg += "type output."
            sys.stderr.write(errmsg)
            sys.exit(1)
        return cfg

    def file2list(self, filename):
        """Read a file and return each line as a list item. Note, if the file
        doesn't exist, this function will return an empty list."""
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

    def file2dict(self, filename, numeric = False):
        """Read a file and split each line at the first space encountered. The
        first element is the key, the rest is the content. If numeric is True
        then only integer values will be acccepted."""
        d = {}
        for line in self.file2list(filename):
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

    def dict2file(self, filename, d):
        "Write a dictionary to a text file"
        f = open(filename, 'w')
        for k in d:
            # In theory we shouldn't need to strip this, but in practice,
            # theory and practice are frequently different.
            f.write("%s %s\n" % (k.strip(), d[k]))
        f.close()

    def list2multi_line_string(self, list):
        """Take a list and return it as a multi-line string."""
        string = ""
        for line in list:
            string += line + "\n"
        return string

    def mail_headers(self, msgid, sender, date):
        """Add some basic headers to our message body so it can be processed in
        Maildir format."""
        payload = "Date: %s\n" % date
        payload += "From: %s\n" % sender
        payload += "Subject: Nym message from %s\n" % sender
        payload += "Message-ID: %s\n" % msgid
        return payload

    def get_range(self, server, sfirst, slast, himark):
        """Return a range of article numbers we should process.  We determine
        this by comparing the articles available on the server with those (if
        known) from our previous use of this server."""
        first = int(sfirst)
        last = int(slast)

        if himark >= first and himark <= last:
            # This is the normal state of affairs. Our himark lies between the
            # server's high and low. We update first with our last himark plus
            # one (We don't want our last himark message, hence the +1).
            first = himark + 1

        # If more than 500 articles to read, prompt for how many.
        howmany = last - first
        if howmany > self.cfg['fetch_limit']:
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
            # We got an acceptable answer from our prompt.  Now set first to
            # the number of articles we want to read.
            first = last - n
        return str(first), slast

    def xover(self, server, spool_file, news):
        # group returns: response, count, first, last, name
        resp, grpcount, \
        grpfirst, grplast, grpname = news.group('alt.anonymous.messages')
        first, last = self.get_range(server,
                                     grpfirst,
                                     grplast,
                                     self.himarks[server])
        msgcnt = (int(last) - int(first)) + 1
        logmes = "Processing %d messages from %s\n" % (msgcnt, server)
        sys.stdout.write(logmes)
        if msgcnt <= 0:
            return int(last)
        # The following xover line is often remarked out during testing as
        # this preserves a constant tmpfile.
        news.xover(first, last, spool_file)
        return int(last)

    def retrieve(self, spool_file, news):
        isopen_maildir = False
        isopen_mbox = False
        received = 0
        s = open(spool_file, "r")
        for ov in s:
            ov2 = ov.rstrip()
            items = ov2.split("\t")
            subject = items[1]
            sender = items[2]
            date = items[3]
            msgid = items[4]

            # Skip checking messages if we already have this Message-ID
            if msgid in self.dedupe:
                continue

            # Retreive the actual payload.  This is amazingly inefficient as we
            # could just get the ones we want but that's bad for anonymity.
            if self.cfg['fetch_all']:
                # The tuple returned by nntp.body includes the actual body as a
                # list object as the fourth element, hence [3].
                body = self.list2multi_line_string(news.body(msgid)[3])
            wanted = False
            if self.do_text and subject in self.subj_list:
                wanted = True
            if not wanted and self.do_hsub:
                for subj in self.hsub_list:
                    if self.hsub.check(subj, subject):
                        wanted = True
                        break
            if not wanted and self.do_esub:
                for subj in self.esub_list:
                    # In our esub file, we assume Subject and Key are separated
                    # by a tab.
                    encsub, key = subj.split("\t", 1)
                    if self.esub.check(encsub, key, subject):
                        wanted = True
                        break
            if wanted:
                if not self.cfg['fetch_all']:
                    body = self.list2multi_line_string(news.body(msgid)[3])
                headers = self.mail_headers(msgid, sender, date)
                msg = "%s\n%s" % (headers, body)
                # Create the message in the Maildir
                if self.cfg['do_maildir']:
                    if not isopen_maildir:
                        mdir = os.path.join(HOMEDIR, 'Maildir',
                                            self.cfg['maildir'])
                        maildir = mailbox.Maildir(mdir, create = True)
                        isopen_maildir = True
                    maildir.add(msg)
                 # If required, configure mbox processing
                if self.cfg['do_mbox']:
                    if not isopen_mbox:
                        mboxfile = os.path.join(HOMEDIR, self.cfg['mboxfile'])
                        mbox = mailbox.mbox(mboxfile, create = True)
                        isopen_mbox = True
                    mbox.add(msg)
                # Increment the received message count
                received += 1
            # Add the Message-ID to the dedupe list.  We won't need to examine
            # it again, whether we wanted it or not.
            self.dedupe.append(msgid)
        # If we opened maildir or mbox objects, we close them now.
        if isopen_maildir:
            maildir.close()
        if isopen_mbox:
            mbox.close()
        return received

    def main(self):
    # Dedupe maintains a list of Message-IDs so that duplicate messages aren't
    # created when we have multiple news servers defined.
        self.dedupe = []
        received = 0
        # Main loop of servers to process starts here.
        for server in self.himarks:
            # Assign a temporary file name for storing xover data.  The name is
            # based on <tempdir>/<server>.tmp
            spool = os.path.join(SPOOLDIR, server + '.tmp')

            # Establish a connection with the newsserver.
            news = nntplib.NNTP(server, readermode = True)
            himark = self.xover(server, spool, news)
            #If the himark we get back from xover is the same as we supplied
            #it then there are no new messages to process.
            if himark == self.himarks[server]:
                # we didn't fetch any messages so move on to the next server
                sys.stdout.write("Nothing to be read.\n")
                news.quit()
                continue
            # Now we retrieve messages from the servers and test them.
            received += self.retrieve(spool, news)
            self.himarks[server] = himark
            news.quit()
        msg = "Received %d messages.\n" % received
        msg += "From %d servers, " % len(self.himarks)
        msg += "%d unique messages were processed.\n" % len(self.dedupe)
        sys.stdout.write(msg)
        # Write the revised server db
        self.dict2file(self.himark_file, self.himarks)

test = aam()
test.main()
