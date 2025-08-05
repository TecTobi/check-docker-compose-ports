# check-docker-compose-ports

# 🔍 check-docker-compose-ports
A Python CLI tool to check and resolve port conflicts in docker-compose files

A robust CLI tool to **inspect**, **audit**, and optionally **fix** ports defined in your `docker-compose.yml` file. Detect conflicts with system processes or running Docker containers, resolve them interactively or automatically, and keep your `.env` files and Compose files clean and conflict-free.

---

## 🚀 Features

- 🧠 Parses `docker-compose.yml` and resolves environment variables from `.env`
- 🔎 Detects which ports are:
    - Defined in Compose services
    - In use by system processes or Docker containers
- 🐳 Identifies the process or container using a port
- 🛠 Fixes conflicts automatically or interactively
- 💾 Updates `.env` and Compose files with new available ports
- 🧪 Outputs results in JSON or pretty human-readable format

---

## 📦 Installation

### 🔸 Clone & Install in a Virtual Environment

```bash
git clone https://github.com/yourusername/check-docker-compose-ports.git
cd check-docker-compose-ports
python3 -m venv venv
source venv/bin/activate
pip install -e .

### 🔸 (Optional) Global Installation with pipx
pipx install git+https://github.com/tectobi/check-docker-compose-ports.git

