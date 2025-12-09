.PHONY: start stop logs restart build

start:
	python -m src.main

stop:
	pkill -f "python -m src.main"

logs:
	tail -f logs/app.log

restart: stop start

build:
	pip install -r requirements.txt 