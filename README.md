Fancy Idling
--

This is a proof-of-concept implementation of a pair of WSGI servers to accept,
store and rebroadcast updates from Flickr using WebSockets.

It looks something like this:

	"flickr" --> listen.py --> redis <-- display.py <-- websockets <-- web browser

It looks that way not necessarily because it's the right way to do it but
because I was exploring some avenues and then wrote a blog post about it. That's
why this shouldn't be considered anything more than a proof of concept. The blog
post is over here and is probably worth reading before you go any further:

http://www.aaronland.info/weblog/2011/05/07/fancy/#likeadog

You can use the listen.sh and display.sh scripts to start up the servers like
you might run anything else from init.d or you can spin them up on their own
with a WSGI server tool like gunicorn:

	$> gunicorn listen:application

Patches, suggestions and gentle cluebats are both welcome and encouraged.

You will need to install a few things to make any of this work:

* Redis

* The Python bindings for Redis

* The Python eventlet libraries

* The gunicorn WSGI application/libraries
