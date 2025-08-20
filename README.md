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
