.PHONY: install backend frontend dev

install:
	pip install -r requirements.txt
	cd web && npm install

backend:
	python3 -m uvicorn api.server:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd web && npm run dev -- --host

dev:
	$(MAKE) -j2 backend frontend
