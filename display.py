# The bulk of this code was copy-pasted as is from:
# https://github.com/benoitc/gunicorn/tree/master/examples/websocket

import os
import os.path
import json
import hashlib
import time

import math
import collections
import errno
from hashlib import md5
import re
import socket
import struct

from gunicorn.workers.async import ALREADY_HANDLED
from eventlet import pools

import eventlet
import redis

import logging

logger = logging.getLogger("display")
formatter = logging.Formatter("%(asctime)s (%(levelname)s) %(message)s")
handler = logging.handlers.RotatingFileHandler('/var/log/flickr/display.log', maxBytes=10485760, backupCount=3)

logger.setLevel(logging.DEBUG)
logger.addHandler(handler)

# This is all plumbing that handles WebSocket details. You don't really
# need to worry about any of this (except maybe the 'index' method below).
# All the stuff for handling which images get sent down the pipe happens
# 'def handle' at the bottom of this file.

class WebSocketWSGI(object):
    def __init__(self, handler):
        self.handler = handler

    def verify_client(self, ws):
        pass

    def _get_key_value(self, key_value):

        if not key_value:
            return

        key_number = int(re.sub("\\D", "", key_value))
        spaces = re.subn(" ", "", key_value)[1]
        if key_number % spaces != 0:
            return
        part = key_number / spaces
        return part

    def __call__(self, environ, start_response):

        if environ.get('HTTP_CONNECTION', False) != 'Upgrade' or environ.get('HTTP_UPGRADE', False) != 'WebSocket':
            return self.index(environ, start_response)

        sock = environ['gunicorn.socket']

        ws = WebSocket(sock,
            environ.get('HTTP_ORIGIN'),
            environ.get('HTTP_WEBSOCKET_PROTOCOL'),
            environ.get('PATH_INFO'))

        handshake_reply = ("HTTP/1.1 101 Web Socket Protocol Handshake\r\n"
                   "Upgrade: WebSocket\r\n"
                   "Connection: Upgrade\r\n")

        self.verify_client(ws)

        key1 = self._get_key_value(environ.get('HTTP_SEC_WEBSOCKET_KEY1'))
        key2 = self._get_key_value(environ.get('HTTP_SEC_WEBSOCKET_KEY2'))

        if key1 and key2:
            challenge = ""
            challenge += struct.pack("!I", key1)  # network byteorder int
            challenge += struct.pack("!I", key2)  # network byteorder int
            challenge += environ['wsgi.input'].read()
            handshake_reply +=  (
                       "Sec-WebSocket-Origin: %s\r\n"
                       "Sec-WebSocket-Location: ws://%s%s\r\n"
                       "Sec-WebSocket-Protocol: %s\r\n"
                       "\r\n%s" % (
                            environ.get('HTTP_ORIGIN'),
                            environ.get('HTTP_HOST'),
                            ws.path,
                            environ.get('HTTP_SEC_WEBSOCKET_PROTOCOL'),
                            md5(challenge).digest()))
        else:
            handshake_reply += (
                       "WebSocket-Origin: %s\r\n"
                       "WebSocket-Location: ws://%s%s\r\n\r\n" % (
                            environ.get('HTTP_ORIGIN'), 
                            environ.get('HTTP_HOST'), 
                            ws.path))

        sock.sendall(handshake_reply)
        try:
            self.handler(ws, environ)
        except socket.error, e:
            if e[0] != errno.EPIPE:
                raise
        except Exception, e:
            logger.error("unable to start handler: %s" % e)
            raise

        return ALREADY_HANDLED

    # This is where you pretend to be Apache and suddenly realize
    # how much of the HTTP request/response stack you never have
    # to think about (or want to)

    def index(self, environ, start_response):

        path = environ.get('PATH_INFO')

        path = os.path.basename(path)

        if path == '':
            path = 'display.html'

        stuff_i_care_about = ('display.html', 'display.css', 'display.js',
                              'jquery-1.4.3.min.js', 'jquery-textfill-0.1.js')

        if not path in stuff_i_care_about:
            start_response('404 NOT FOUND',
                           [('Content-Type', 'text/plain'),
                            ('Content-Length', 0)])
            return []

        data = open(os.path.join(
                os.path.dirname(__file__),
                path)).read()

        data = data % environ

        if path.endswith(".js"):
            type = "text/javascript"
        elif path.endswith(".css"):
            type = "text/css"
        else:
            type = "text/html"

        start_response('200 OK', [('Content-Type', type),
                                  ('Content-Length', len(data))])
        return [data]

def parse_messages(buf):
    """ Parses for messages in the buffer *buf*.  It is assumed that
    the buffer contains the start character for a message, but that it
    may contain only part of the rest of the message. NOTE: only understands
    lengthless messages for now.

    Returns an array of messages, and the buffer remainder that didn't contain
    any full messages."""

    msgs = []
    end_idx = 0
    while buf:
        assert ord(buf[0]) == 0, "Don't understand how to parse this type of message: %r" % buf
        end_idx = buf.find("\xFF")
        if end_idx == -1:
            break
        msgs.append(buf[1:end_idx].decode('utf-8', 'replace'))
        buf = buf[end_idx+1:]
    return msgs, buf

def format_message(message):
    # TODO support iterable messages
    if isinstance(message, unicode):
        message = message.encode('utf-8')
    elif not isinstance(message, str):
        message = str(message)
    packed = "\x00%s\xFF" % message
    return packed


class WebSocket(object):
    def __init__(self, sock, origin, protocol, path):
        self.sock = sock
        self.origin = origin
        self.protocol = protocol
        self.path = path
        self._buf = ""
        self._msgs = collections.deque()
        self._sendlock = pools.TokenPool(1)

    def send(self, message):
        packed = format_message(message)
        # if two greenthreads are trying to send at the same time
        # on the same socket, sendlock prevents interleaving and corruption
        t = self._sendlock.get()
        try:
            self.sock.sendall(packed)
        finally:
            self._sendlock.put(t)

    def wait(self):
        while not self._msgs:
            # no parsed messages, must mean buf needs more data
            delta = self.sock.recv(1024)
            if delta == '':
                return None
            self._buf += delta
            msgs, self._buf = parse_messages(self._buf)
            self._msgs.extend(msgs)
        return self._msgs.popleft()


# This is where all the work of pulling stuff out of Redis
# and pushing it back down the pipe happens.

def handle(ws, environ):

    if ws.path == '/data':

        # I suppose we could be setting cookies instead but who knows
        # where/how you do that in happy magic python framework land

        addr = environ['REMOTE_ADDR']
        port = environ['REMOTE_PORT']

        useragent = "user_%s" % md5(addr).hexdigest()

        logger.debug("[%s] start data stream on port %s (%s)" % (addr, port, useragent))

        r = redis.Redis()

        count = 0
        last_count = 0

        while True:

            sent = 0
            skipped = 0

            # First, check to see if there have been any updates
            # and whether it's worth cycling through the list of
            # stuff in the queue.

            count = r.llen('updates')

            logger.debug("[%s] there are %s updates in the queue" % (addr, count))

            if count == 0 or count == last_count:

                _count = count

                while count == _count:

                    err = json.dumps({"noop" : 1, "reason": "no updates"})
                    ws.send(err)

                    eventlet.sleep(60.)

                    count = r.llen('updates')
                    logger.debug("[%s] there are %s updates in the queue" % (addr, count))

            last_count = count

            # Okay, plow through the list ignorning anything we've seen. Remember how
            # the key is set by using the REMOTE_ADDR? That's pretty clunky but this is
            # only a proof-of-concept and I have no idea how/where you get a useragent
            # string in a websockets request. Oh well...

            for i in range(0, count):

                data = r.lindex('updates', i)
                key = md5(data).hexdigest()

                if r.hexists(useragent, key):
                    skipped += 1
                    continue

                try:
                    ws.send(data)
                    sent += 1
                    eventlet.sleep(30.)
                except Exception, e:
                    logger.error("[%s] failed to send data: %s" % (addr, e))
                    raise

                r.hset(useragent, key, int(time.time()))

            logger.debug("[%s] sent; %s skipped: %s" % (addr, sent, skipped))

def application(environ, start_response):
    wsapp = WebSocketWSGI(handle)
    return wsapp(environ, start_response)
