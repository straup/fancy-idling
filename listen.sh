#!/bin/sh

ADDRESS='localhost:3333'
GUNICORN="/usr/local/bin/gunicorn"
PIDFILE="/var/run/flickr-listen.pid"
LOGFILE="/var/log/flickr-listen.log"
WORKERS=1

COMMAND="$GUNICORN --daemon --user www-data --workers $WORKERS --worker-class egg:gunicorn#gevent_wsgi --bind $ADDRESS -n flickr-listen"

start_server () {
  if [ -f $PIDFILE ]; then
    #pid exists, check if running
    if [ "$(ps -p `cat $PIDFILE` | wc -l)" -gt 1 ]; then
       echo "Server already running on ${ADDRESS}"
       return
    fi
  fi
  echo "starting ${ADDRESS}"
  $COMMAND --pid $PIDFILE listen:application
}

stop_server () {
  if [ -f $PIDFILE ] && [ "$(ps -p `cat $PIDFILE` | wc -l)" -gt 1 ]; then
    echo "stopping server ${ADDRESS}"
    kill -9 `cat $PIDFILE`
    rm $PIDFILE
  else 
    if [ -f $PIDFILE ]; then
      echo "server ${ADDRESS} not running"
    else
      echo "No pid file found for server ${ADDRESS}"
    fi
  fi
}

restart_server () {
  if [ -f $PIDFILE ] && [ "$(ps -p `cat $PIDFILE` | wc -l)" -gt 1 ]; then
    echo "gracefully restarting server ${ADDRESS}"
    kill -HUP `cat $PIDFILE`
  else 
    if [ -f $PIDFILE ]; then
      echo "server ${ADDRESS} not running"
    else
      echo "No pid file found for server ${ADDRESS}"
    fi
  fi
}

case "$1" in
'start')
  start_server
  ;;
'stop')
  stop_server
  ;;
'restart')
  restart_server
  ;;
*)
  echo "Usage: $0 { start | stop | restart }"
  ;;
esac

exit 0
