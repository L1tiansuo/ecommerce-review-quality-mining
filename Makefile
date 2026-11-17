up:
	docker compose up --build -d
down:
	docker compose down
test:
	python -m pytest tests -q
build:
	cd backend && mvn package
	cd web && npm ci && npm run build
