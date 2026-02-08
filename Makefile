.PHONY: install backend frontend dev docker-up docker-down

install:
	pip install -r requirements.txt
	cd web && npm install

backend:
	python3 -m uvicorn api.server:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd web && npm run dev -- --host

dev:
	$(MAKE) -j2 backend frontend

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down
