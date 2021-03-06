#!/usr/bin/env python
#
# vim: tabstop=4 expandtab shiftwidth=4 noautoindent

import sys
import os
import time
import atexit
from signal import SIGTERM


class Daemon:
    """A generic daemon class.
    Usage: subclass the Daemon class and override the run() method"""
    def __init__(self, pidfile, stdin='/dev/null',
                                stdout='/dev/null',
                                stderr='/dev/null'):
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.pidfile = pidfile

    def daemonize(self):
        """Do the UNIX double-fork magic, see Stevens' "Advanced Programming
        in the UNIX Environment" for details (ISBN 0201563177)
        http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16"""
        try:
            pid = os.fork()
            if pid > 0:
                # exit first parent
                sys.exit(0)
        except OSError, e:
            logmes = "fork #1 failed: %d (%s)\n" % (e.errno, e.strerror)
            sys.stderr.write(logmes)
            sys.exit(1)

        # decouple from parent environment
        os.chdir("/")
        os.setsid()
        os.umask(0)

        # do second fork
        try:
            pid = os.fork()
            if pid > 0:
                # exit from second parent
                sys.exit(0)
        except OSError, e:
            logmes = "fork #2 failed: %d (%s)\n" % (e.errno, e.strerror)
            sys.stderr.write(logmes)
            sys.exit(1)

        # redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()
        si = open(self.stdin, 'r')
        so = open(self.stdout, 'a+')
        se = open(self.stderr, 'a+', 0)
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())

        # write pidfile
        atexit.register(self.delpid)
        pf = open(self.pidfile, 'w+')
        pf.write("%d\n" % os.getpid())
        pf.close()

    def delpid(self):
        os.remove(self.pidfile)

    def start(self):
        """Start the daemon"""
        # Check for a pidfile to see if the daemon already runs
        try:
            pf = open(self.pidfile, 'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None

        if pid:
            message = "Pidfile %s already exists." % self.pidfile
            message += " Daemon already running?\n"
            sys.stderr.write(message)
            sys.exit(1)

        # Start the daemon
        self.daemonize()
        self.run()

    def stop(self):
        """Stop the daemon"""
        # Get the pid from the pidfile
        try:
            pf = open(self.pidfile, 'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None

        if not pid:
            message = "pidfile %s does not exist. Daemon not running?\n"
            sys.stderr.write(message % self.pidfile)
            return  # Not an error in a restart

        # Try killing the daemon process
        try:
            while 1:
                os.kill(pid, SIGTERM)
                time.sleep(0.1)
        except OSError, err:
            err = str(err)
            if err.find("No such process") > 0:
                if os.path.exists(self.pidfile):
                    os.remove(self.pidfile)
            else:
                print str(err)
                sys.exit(1)

    def restart(self):
        """Restart the daemon"""
        self.stop()
        self.start()

    def run(self):
        """You should override this method when you subclass Daemon. It will
        be called after the process has been daemonized by start() or
        restart()."""
