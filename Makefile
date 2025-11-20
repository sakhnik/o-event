VENV ?= venv

ifeq ($(wildcard $(VENV)/bin/pytest),)
    PYTEST := /usr/bin/pytest
else
    PYTEST := $(VENV)/bin/pytest
endif

all:
	$(PYTEST) -v
