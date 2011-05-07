#!/bin/sh

ADDRESS='localhost:2222'
GUNICORN="/usr/local/bin/gunicorn"
PIDFILE="/var/run/flickr/display.pid"
LOGFILE="/var/log/flickr/display.log"
WORKERS=2

COMMAND="$GUNICORN --daemon --log-file $LOGFILE --log-level DEBUG --user www-data --workers $WORKERS --worker-class egg:gunicorn#eventlet --bind $ADDRESS -n flickr-display"

start_server () {
  if [ -f $PIDFILE ]; then
    #pid exists, check if running
    if [ "$(ps -p `cat $PIDFILE` | wc -l)" -gt 1 ]; then
       echo "Server already running on ${ADDRESS}"
       return
    fi
  fi
  echo "starting ${ADDRESS}"
  $COMMAND --pid $PIDFILE display:application
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
