# mimir-api

## Install & Run (Linux)

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

3. Install dependencies:
	```bash
	pip install -r requirements.txt
	```

4. Run the API service:
	```bash
	python main.py
	```

# mimir-api

## Install & Run (Linux)

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

3. Install dependencies:
	```bash
	pip install -r requirements.txt
	```

4. Run the API service:
	```bash
	python main.py
	```

The service will start on port 5000 by default.

## Run as a Service (Autostart on Linux)

1. Create a systemd service file (e.g. `/etc/systemd/system/mimir-api.service`):
	```ini
	[Unit]
	Description=Mimir API Service
	After=network.target

	[Service]
	Type=simple
	User=YOUR_USERNAME
	WorkingDirectory=/path/to/mimir-api/api-service
	ExecStart=/path/to/mimir-api/api-service/.venv/bin/python main.py
	Restart=always

	[Install]
	WantedBy=multi-user.target
	```

2. Reload systemd and enable the service:
	```bash
	sudo systemctl daemon-reload
	sudo systemctl enable mimir-api
	sudo systemctl start mimir-api
	```

The API service will now start automatically on boot.

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