import feedparser
import logging
import pprint
import redis
import json
import re
import time

logger = logging.getLogger("listen")
formatter = logging.Formatter("%(asctime)s (%(levelname)s) %(message)s")
handler = logging.handlers.RotatingFileHandler('/var/log/flickr/listen.log', maxBytes=10485760, backupCount=3)

logger.setLevel(logging.DEBUG)
logger.addHandler(handler)

def application(environ, start_response):

    status = '200 OK'
    content_type = 'text/plain'
    rsp = 'OK FOR DEPLOY'

    try:
        feed = feedparser.parse(environ['wsgi.input'].read())

        # http://www.feedparser.org/docs/bozo.html

        if feed.bozo:
            raise feed.bozo_exception

        # https://github.com/andymccurdy/redis-py

        r = redis.Redis()

        # http://www.feedparser.org/docs/reference.html
        # logging.debug(pprint.pformat(feed))

        if feed.get('at_deleted-entry', False):

            uid = feed['at_deleted-entry']['ref']
            when = feed['at_deleted-entry']['when']
            logger.debug("%s deleted %s" % (uid, when))

            r.hset('deletes', uid, when)

        else:

            for e in feed['entries']:

                uid = e['id']
                who = e['author']
                nsid = e['flickr_nsid']
                what = e['title']
                when = e['updated']
                image = e['media_content'][0]['url']
                thumb = e['media_thumbnail'][0]['url']

                image = re.sub("_x", "", image)

                r.lpush('updates', json.dumps({
                            'photo_id' : uid,
                            'owner': nsid,
                            'ownername' : who,
                            'title' : what,
                            'updated': when,
                            'photo_url' : image,
                            'thumb_url' : thumb,
                            }))

                r.hincrby('owners', nsid)

                logger.debug("%s's photo \"%s\" (%s) was updated at %s" % (who, what, uid, when))

                r.hset('flickr', 'newstuff', int(time.time()))

            count = r.llen('updates')

            if count > 500:
                r.ltrim('updates', 500, count)

    except Exception, e:
        logger.error("failed to parse atom feed: %s" % e)

        status = "500 SERVER ERROR"
        rsp = "NO DEPLOY PLEASE: %s" % e

    response_headers = [
        ('Content-Type', str(content_type)),
        ('Content-Length', str(len(rsp)))
        ]

    start_response(status, response_headers)
    return iter([ rsp ])
