# mimir-api

Multi-display content management system API with modular architecture.

## Install & Run (Development)

1. Clone the repository:
	```bash
	git clone https://github.com/ryanlane/mimir-api.git
	cd mimir-api/api-service
	```

2. Create and activate a Python virtual environment:
	```bash
	python3 -m venv .venv
	source .venv/bin/activate
	```

3. Install dependencies (with development tools):
	```bash
	pip install -e ".[dev]"
	```

4. Set up environment configuration:
	```bash
	cp .env.example .env
	# Edit .env with your specific configuration
	```

5. Run the API service:
	```bash
	# Option 1: Using the application factory
	python -m app.main
	
	# Option 2: Using uvicorn directly
	uvicorn app.main:app --reload --host 0.0.0.0 --port 5000
	```

The service will start on port 5000 by default.

## Run as a Service (Production Linux)

1. Copy and configure the systemd service file:
	```bash
	sudo cp mimir-api.service.example /etc/systemd/system/mimir-api.service
	# Edit the service file with correct paths and user
	sudo systemctl daemon-reload
	```

2. Enable and start the service:
	```bash
	sudo systemctl enable mimir-api
	sudo systemctl start mimir-api
	sudo systemctl status mimir-api
	```

The API service will now start automatically on boot using the new modular architecture.

## Development Tools

This project includes comprehensive development tooling:

- **Linting**: `ruff` for fast Python linting
- **Formatting**: `black` and `isort` for code formatting  
- **Type Checking**: `mypy` for static type analysis
- **Testing**: `pytest` for unit and integration tests
- **Pre-commit**: Automated code quality checks

Install pre-commit hooks:
```bash
pre-commit install
```

Run development tools:
```bash
# Format code
black .
isort .

# Lint code
ruff check .

# Type check
mypy .

# Run tests
pytest
```

## 📖 Documentation

**Complete documentation is available at:** [github.com/ryanlane/mimir-documentation](https://github.com/ryanlane/mimir-documentation)

- **[API Documentation](https://github.com/ryanlane/mimir-documentation/blob/main/API_DOCUMENTATION.md)** - Complete REST API reference
- **[Channel Architecture](https://github.com/ryanlane/mimir-documentation/blob/main/CHANNEL_ARCHITECTURE.md)** - Channel system architecture  
- **[Multi-Display Architecture](https://github.com/ryanlane/mimir-documentation/blob/main/MULTI_DISPLAY_ARCHITECTURE.md)** - Multi-display system design
- **[Display Client Specification](https://github.com/ryanlane/mimir-documentation/blob/main/DISPLAY_CLIENT_SPECIFICATION.md)** - Display client development guide

## Features

- RESTful API with FastAPI and automatic OpenAPI documentation
- Channel plugin system v2.4 with Web Components support
- Multi-display support with independent scene assignment
- WebSocket support for real-time updates
- Administrative endpoints for channel management
- Rate limiting and comprehensive security features