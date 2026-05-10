.PHONY: smoke up down

up:
	docker compose up -d

down:
	docker compose down

smoke:
	pytest tests/smoke/test_upload_pipeline.py -v
