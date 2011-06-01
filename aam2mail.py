#!/usr/bin/python
#
# vim: tabstop=4 expandtab shiftwidth=4 autoindent
#
# Copyright (C) 2011 Steve Crook <steve@mixmin.net>
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

import os.path
import mailbox
import sys
import nntplib
import socket
import logging
from time import sleep
from daemon import Daemon


# Can change loglevel here.
LOGLEVEL = 'debug'

HOMEDIR = os.path.expanduser('~')
APPDIR = os.path.join(HOMEDIR, 'aam2mail')
ETCDIR = os.path.join(APPDIR, 'etc')
LOGDIR = os.path.join(APPDIR, 'log')
PIDDIR = os.path.join(APPDIR, 'run')
SPOOLDIR = os.path.join(APPDIR, 'spool')
PIDFILE = os.path.join(PIDDIR, 'aam2mail.pid')
ERRFILE = os.path.join(LOGDIR, 'err')

# ----- Don't go beyond here unless you know what you're doing! -----

class MyDaemon(Daemon):
    def run(self):
        logging.info('Daemon started')
        while True:
            aam.main()
            sleep(aam.cfg['fetch_interval'])

class aam():
    def __init__(self):
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
            logmsg = "Checking %s plain text Subjects" % len(subj_list)
            logging.info(logmsg)
        hsub_list = self.file2list(os.path.join(ETCDIR, "subject_hsub"))
        if hsub_list:
            do_hsub = True
            import hsub
            self.hsub = hsub.hsub()
            self.hsub_list = hsub_list
            logging.info("Checking %s hSub Subjects" % len(hsub_list))
        esub_list = self.file2list(os.path.join(ETCDIR, "subject_esub"))
        if esub_list:
            do_esub = True
            import esub
            self.esub = esub.esub()
            self.esub_list = esub_list
            logging.info("Checking %s eSub Subjects" % len(esub_list))
        if not do_text and not do_hsub and not do_esub:
            errmsg = "No text, hsub or esub Subjects defined. Aborting."
            logging.error(errmsg)
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
            errmsg = "Error: Config file %s does not exist." % cfgfile
            logging.error(errmsg)
            sys.exit(1)
        cfg = self.file2dict(cfgfile)
        # Configure some defaults (and some sanity)
        if not 'fetch_all' in cfg: cfg['fetch_all'] = True
        if not 'fetch_limit' in cfg: cfg['fetch_limit'] = 500
        if not 'fetch_interval' in cfg: cfg['fetch_interval'] = 3600
        if cfg['fetch_interval'] <= 900: cfg['fetch_interval'] = 900
        # All these parameters will be defaulted to False.
        opts = 'do_maildir do_mbox maildir mboxfile'
        optlist = opts.split(" ")
        for opt in optlist:
            if not opt in cfg: cfg[opt] = False
        # These options depend on others.
        if not cfg['maildir']: cfg['do_maildir'] = False
        if not cfg['mboxfile']: cfg['do_mbox'] = False
        # We need to do one type of mailbox, otherwise, what's the point.
        if not cfg['do_maildir'] and not cfg['do_mbox']:
            errmsg = "No output: We're not configured to write Maildir or Mbox "
            errmsg += "type files. Aborting."
            logging.error(errmsg)
            sys.exit(1)
        logmes = "We are configured to process up to %s " % cfg['fetch_limit']
        logmes += "messages, every %s seconds." % cfg['fetch_interval']
        logging.info(logmes)
        if cfg['fetch_all']:
            logmes = "All messages will be retrieved prior to processing"
            logging.info(logmes)
        else:
            logmes = "Only retrieving our own messages. Bad for anonymity!"
            logging.warn(logmes)
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

        # Check we aren't receiving more messages than the configured limit.
        howmany = last - first
        if howmany > self.cfg['fetch_limit']:
            logmes = "%s: There are %s unread messages. " % (server, howmany)
            logmes += "Only processing %s, due to " % self.cfg['fetch_limit']
            logmes += "configured fetch_limit."
            logging.warn(logmes)
            last = first + self.cfg['fetch_limit']
        return str(first), str(last)

    def xover(self, server, spool_file, news):
        # group returns: response, count, first, last, name
        try:
            resp, grpcount, grpfirst, \
            grplast, grpname = news.group('alt.anonymous.messages')
        except nntplib.NNTPTemporaryError, e:
            logging.warn("%s: %s" % (server, e))
            return 0
        first, last = self.get_range(server,
                                     grpfirst,
                                     grplast,
                                     self.himarks[server])
        msgcnt = (int(last) - int(first)) + 1
        logmes = "%s: Processing %d messages" % (server, msgcnt)
        logging.debug(logmes)
        if msgcnt <= 0:
            return int(last)
        # The following xover line is often remarked out during testing as
        # this preserves a constant tmpfile.
        try:
            resp, foo = news.xover(first, last, spool_file)
        except nntplib.NNTPTemporaryError, e:
            logging.warn("%s: %s" % (server, e))
            return 0
        logging.debug("Xover responded with: %s" % resp)
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
        srv_count = 0
        # Main loop of servers to process starts here.
        for server in self.himarks:
            # Assign a temporary file name for storing xover data.  The name is
            # based on <tempdir>/<server>.tmp
            spool = os.path.join(SPOOLDIR, server + '.tmp')

            # Establish a connection with the newsserver.
            logging.debug("%s: Establishing connection." % server)
            try:
                news = nntplib.NNTP(server, readermode = True)
            except socket.gaierror, e:
                logging.warn('%s: Connection error: %s' % (server, e))
                continue
            himark = self.xover(server, spool, news)
            # Zero isn't a valid himark so our xover routine can return it
            # to indicate something went wrong.  Hopefully the something is
            # logged.
            if himark == 0:
                continue
            # If we get here, the assumption is that the server accepted our
            # connection and provided any messages we asked for.
            srv_count += 1
            #If the himark we get back from xover is the same as we supplied
            #it then there are no new messages to process.
            if himark == self.himarks[server]:
                # we didn't fetch any messages so move on to the next server
                logging.debug("%s: No new messages." % server)
                news.quit()
                continue
            # Now we retrieve messages from the servers and test them.
            received += self.retrieve(spool, news)
            self.himarks[server] = himark
            news.quit()
        logging.info("Received %d messages." % received)
        msg = "We processed %d unique messages " % len(self.dedupe)
        msg += "from %d servers " % srv_count
        msg += "(%d attempted)." % len(self.himarks)
        logging.debug(msg)
        # Write the revised server db
        logging.debug("Writing himarks to file.")
        self.dict2file(self.himark_file, self.himarks)

def init_logging():
    loglevels = {'debug': logging.DEBUG, 'info': logging.INFO,
                 'warn': logging.WARN, 'error': logging.ERROR}
    # No dynamic logfile name as we're running as a daemon
    logfile = os.path.join(LOGDIR, 'aam2mail')
    logging.basicConfig(
        filename=logfile,
        level = loglevels[LOGLEVEL],
        format = '%(asctime)s %(process)d %(levelname)s %(message)s',
        datefmt = '%Y-%m-%d %H:%M:%S')

if __name__ == "__main__":
    # Do some basic checks that our required directories exist.
    if not os.path.isdir(HOMEDIR):
        errmsg = "Error: Home Directory %s does not exist\n" % HOMEDIR
        sys.stderr.write(errmsg)
        sys.exit(1)
    for dirs in 'APPDIR ETCDIR LOGDIR PIDDIR SPOOLDIR'.split(" "):
        d = eval(dirs)
        if not os.path.isdir(d):
            from os import mkdir
            mkdir(d, 0700)
    init_logging()
    aam = aam()
    daemon = MyDaemon(PIDFILE, '/dev/null', '/dev/null', ERRFILE)
    # Process the start/stop args
    if len(sys.argv) == 2:
        if 'start' == sys.argv[1]:
            logging.info('aam2mail started in Daemon mode')
            daemon.start()
        elif 'stop' == sys.argv[1]:
            daemon.stop()
            sys.stdout.write('aam2mail stopped\n')
        elif 'restart' == sys.argv[1]:
            daemon.restart()
        elif 'dryrun' == sys.argv[1]:
            # Run in console for testing
            daemon.run()
        else:
            print "Unknown command"
            sys.exit(2)
        sys.exit(0)
    else:
        print "usage: %s start|stop|restart" % sys.argv[0]
        sys.exit(2)
