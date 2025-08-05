# 🔍 check-docker-compose-ports (v. 1.0.0)

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
```

### 🔸 (Optional) Global Installation with pipx

```bash
pipx install git+https://github.com/yourusername/check-docker-compose-ports.git
```

---

## 🧪 Basic Usage

```bash
check-docker-compose-ports --file docker-compose.yml
```

```bash
check-docker-compose-ports --file docker-compose.yml --json
```

---

## ⚙️ CLI Options

| Option                  | Description                                                                 |
|-------------------------|-----------------------------------------------------------------------------|
| `-f`, `--file`          | Path to docker-compose file (default: `docker-compose.yml`)                 |
| `--env-file`            | Path to `.env` file (auto-detected if not provided)                         |
| `--json`                | Output in JSON format                                                       |
| `--warn-only`           | Warn about conflicts, but don't exit with error                             |
| `--exit-on-used`        | Exit with code 1 if any port is in use (useful for CI pipelines)            |
| `--fix`                 | Automatically fix port conflicts by assigning available ports               |
| `--fix-interactive`     | Interactively fix conflicts by prompting for new ports                      |
| `--port-range`          | Port range to use when assigning new ports (default: `8000-65535`)          |
| `--backup`              | Backup `.env` and Compose file before making changes                        |

---

## 🖼️ Example Output

### Pretty terminal format

```
🐳 Docker Compose Port Analysis
==================================================

🌍 Using environment file: .env

📊 Summary: 5 services, 8 ports configured
⚠️  2 port(s) in use

🔧 Service: api
   📦 Image: my-api:latest
   🔌 Ports:
      └─ 8080:80/tcp ($API_PORT) - ❌ In Use
         └─ Process: nginx (PID: 1234)
         └─ Docker: supabase-kong
            Image: kong:2.8.1

🔧 Service: db
   📦 Image: postgres:15
   🔌 Ports:
      └─ 5432/tcp - ✅ Available
```

### JSON format (`--json`)

```json
{
  "summary": {
    "total_services": 5,
    "total_ports": 8,
    "ports_in_use": 2
  },
  "services": [
    {
      "name": "api",
      "image": "my-api:latest",
      "ports": [
        {
          "host_port": 8080,
          "container_port": 80,
          "protocol": "tcp",
          "available": false,
          "env_var": "API_PORT",
          "process": {
            "pid": 1234,
            "name": "nginx"
          },
          "docker_container": {
            "container_name": "supabase-kong",
            "image": "kong:2.8.1"
          }
        }
      ]
    }
  ]
}
```

---

## 🔧 Example: Fixing Conflicts

### 🛠 Auto-fix (non-interactive)
```bash
check-docker-compose-ports --fix --backup
```

### 🧑‍💻 Interactive Fix
```bash
check-docker-compose-ports --fix-interactive --backup
```

> Automatically updates `.env` and/or `docker-compose.yml` with new available ports and creates `.backup` files.


## 🛡 License

MIT License — see [`LICENSE`](./LICENSE)

---

## 🤝 Contributing

Pull requests and issues are welcome!

If you have feature requests, bug reports, or ideas to improve this tool, feel free to open an [issue](https://github.com/TecTobi/check-docker-compose-ports/issues).

---

## 🌍 Related Tools

- [Docker Compose](https://docs.docker.com/compose/)
- [psutil](https://pypi.org/project/psutil/)
- [PyYAML](https://pypi.org/project/PyYAML/)
- [pipx](https://github.com/pypa/pipx)

---

## ✨ Star this project if it helped you!

```
⭐ GitHub: https://github.com/TecTobi/check-docker-compose-ports
```
