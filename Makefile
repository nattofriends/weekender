# Makefile for uwsgi, because uwsgi sux

# App-specific config

include Makefile.appconfig

APP_MODULE = "app:create()"
PIDFILE = app.pid
VENV3_NAME = runtime
UWSGI_LOG = uwsgi.log

# None of your business

BASEDIR = $(shell readlink -f .)
PIDPATH = $(BASEDIR)/$(PIDFILE)
VENV3 = $(BASEDIR)/$(VENV3_NAME)
BIN = $(VENV3)/bin/uwsgi

RM = rm -f

PYTEST = $(VENV3)/bin/py.test

.PHONY: clean tests start-dev


start: css ensure-stopped
	$(BIN) \
		--daemonize $(UWSGI_LOG) \
		--pidfile $(PIDFILE) \
		--http-socket $(BIND) \
		-H $(VENV3) \
		-w $(APP_MODULE)

stop:
	$(BIN) --stop $(PIDFILE)
	while [ ! -z "`pgrep -F $(PIDFILE)`" ]; do sleep .1; done

ensure-stopped:
	@if [ -z "`pgrep -F $(PIDFILE)`" ]; then \
		exit 0; \
	else \
		echo "Cowardly refusing to run when another instance is already running."; \
		exit 1; \
	fi

restart: stop start

start-dev: css
	$(VENV3)/bin/python app.py

clean:
	$(RM) static/style.css
	$(RM) messages.pot
	$(RM) *.stamp

last-exception:
	@sed -nE '/^Traceback/,/^\[pid: /p' $(UWSGI_LOG) | tac | sed '/^Traceback/q' | tac

css: static/style.css

static/style.css: static/style.scss
	$(VENV3)/bin/pyscss < static/style.scss > static/style.css

init-env:
	ln -s ../bower_components static/vendor

init-pythons:
	virtualenv --python=python3 --no-site-packages $(VENV3_NAME)
	$(VENV3)/bin/pip install -r requirements.txt

tests:
	PYTHONPATH=. $(PYTEST) -vvv tests
