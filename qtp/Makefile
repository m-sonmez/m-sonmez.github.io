.PHONY: build all test docs clean

PYTHON ?= $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; elif [ -x .venv/Scripts/python.exe ]; then echo .venv/Scripts/python.exe; else echo python3; fi)
UNAME_S := $(shell uname -s 2>/dev/null || echo Windows)

build:
ifeq ($(OS),Windows_NT)
	$(PYTHON) -m qtp_app.build.build_windows
else
	$(PYTHON) -m qtp_app.build.build_unix
endif

all:
ifeq ($(OS),Windows_NT)
	$(PYTHON) -m qtp_app.build.build_windows
	@echo "[UYARI] Windows üzerinde Linux/macOS qtp.bin derlemesi atlandi (Wine capraz derlemesi kullanilmaz; qtp.bin yalnizca Linux/macOS uzerinde derlenir)."
else
	$(PYTHON) -m qtp_app.build.build_unix
	@echo "[UYARI] Unix üzerinde Windows qtp.exe derlemesi atlandi (qtp.exe yalnizca Windows uzerinde derlenir)."
endif

test:
	$(PYTHON) -m pytest -q

docs:
	@echo "docs/ dizini tek kaynakli Turkce Markdown belgelerinden olusur (ek uretim gerektirmez)."

clean:
	rm -rf build/ dist/ .pytest_cache/ .coverage htmlcov/
