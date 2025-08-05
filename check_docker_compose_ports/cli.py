#!/usr/bin/env python3
"""
CLI tool to check which ports defined in a docker-compose file are already in use.
"""

import argparse
import json
import socket
import subprocess
import sys
import random
import shutil
import re
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional

import psutil
import yaml


def load_env_file(env_file_path: str) -> Dict[str, str]:
    """Load environment variables from a .env file."""
    env_vars = {}
    if not os.path.exists(env_file_path):
        return env_vars

    try:
        with open(env_file_path, 'r') as file:
            for line_num, line in enumerate(file, 1):
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue

                # Handle KEY=VALUE format
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()

                    # Remove quotes if present
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]

                    env_vars[key] = value
    except Exception as e:
        print(f"Warning: Error reading .env file '{env_file_path}': {e}")

    return env_vars


def save_env_file(env_vars: Dict[str, str], env_file_path: str) -> None:
    """Save environment variables to a .env file while preserving format."""
    if not os.path.exists(env_file_path):
        # Create new .env file
        with open(env_file_path, 'w') as file:
            for key, value in env_vars.items():
                file.write(f"{key}={value}\n")
        return

    # Read original file to preserve comments and formatting
    try:
        with open(env_file_path, 'r') as file:
            lines = file.readlines()

        # Update existing variables and track what we've updated
        updated_vars = set()

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and '=' in stripped:
                key = stripped.split('=', 1)[0].strip()
                if key in env_vars:
                    # Update the line with new value
                    lines[i] = f"{key}={env_vars[key]}\n"
                    updated_vars.add(key)

        # Add any new variables that weren't in the original file
        for key, value in env_vars.items():
            if key not in updated_vars:
                lines.append(f"{key}={value}\n")

        # Write back to file
        with open(env_file_path, 'w') as file:
            file.writelines(lines)

    except Exception as e:
        print(f"Error updating .env file '{env_file_path}': {e}")
        sys.exit(1)


def resolve_env_variables(value: str, env_vars: Dict[str, str]) -> str:
    """Resolve environment variable substitutions in a string."""
    if not isinstance(value, str):
        return value

    # Handle ${VAR} and ${VAR:-default} patterns
    def replace_var(match):
        var_expr = match.group(1)

        # Handle default values: ${VAR:-default}
        if ':-' in var_expr:
            var_name, default_value = var_expr.split(':-', 1)
            return env_vars.get(var_name, default_value)
        else:
            return env_vars.get(var_expr, '')

    # Replace ${VAR} and ${VAR:-default} patterns
    result = re.sub(r'\$\{([^}]+)\}', replace_var, value)

    # Handle $VAR patterns (without braces)
    def replace_simple_var(match):
        var_name = match.group(1)
        return env_vars.get(var_name, '')

    result = re.sub(r'\$([A-Z_][A-Z0-9_]*)', replace_simple_var, result)

    return result


def extract_env_port_variables(compose_data: dict) -> Set[str]:
    """Extract environment variable names that are used for port configuration."""
    port_env_vars = set()

    def find_port_vars_recursive(obj, path=""):
        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = f"{path}.{key}" if path else key

                # Check if this is a ports configuration
                if key == 'ports' and isinstance(value, list):
                    for port_mapping in value:
                        if isinstance(port_mapping, str):
                            # Extract environment variables from port strings
                            env_vars_in_string = re.findall(r'\$\{([^}]+)\}', port_mapping)
                            for env_var in env_vars_in_string:
                                # Handle default values: ${VAR:-default}
                                if ':-' in env_var:
                                    var_name = env_var.split(':-', 1)[0]
                                else:
                                    var_name = env_var
                                port_env_vars.add(var_name)

                            # Also check for simple $VAR patterns
                            simple_vars = re.findall(r'\$([A-Z_][A-Z0-9_]*)', port_mapping)
                            port_env_vars.update(simple_vars)

                find_port_vars_recursive(value, current_path)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                find_port_vars_recursive(item, f"{path}[{i}]")

    find_port_vars_recursive(compose_data)
    return port_env_vars


def load_docker_compose(file_path: str) -> dict:
    """Load and parse a docker-compose.yml file."""
    try:
        with open(file_path, 'r') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file '{file_path}': {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading '{file_path}': {e}")
        sys.exit(1)


def save_docker_compose(compose_data: dict, file_path: str) -> None:
    """Save docker-compose data to a YAML file."""
    try:
        with open(file_path, 'w') as file:
            yaml.dump(compose_data, file, default_flow_style=False, sort_keys=False)
    except Exception as e:
        print(f"Error writing to '{file_path}': {e}")
        sys.exit(1)


def find_available_port(start_port: int = 8000, end_port: int = 65535, exclude_ports: Set[int] = None) -> int:
    """Find an available port in the specified range."""
    if exclude_ports is None:
        exclude_ports = set()

    # Get currently used ports
    used_ports = {conn.laddr.port for conn in psutil.net_connections(kind='inet') if conn.status == psutil.CONN_LISTEN}
    used_ports.update(exclude_ports)

    # Try random ports first to avoid sequential allocation
    attempts = 0
    max_attempts = 1000

    while attempts < max_attempts:
        port = random.randint(start_port, end_port)
        if port not in used_ports and not is_port_in_use(port):
            return port
        attempts += 1

    # Fallback to sequential search
    for port in range(start_port, end_port + 1):
        if port not in used_ports and not is_port_in_use(port):
            return port

    raise RuntimeError(f"No available ports found in range {start_port}-{end_port}")


def extract_service_ports(compose_data: dict, env_vars: Dict[str, str] = None) -> Dict[str, Dict]:
    """Extract port information for each service in the docker-compose file."""
    if env_vars is None:
        env_vars = {}

    services_info = {}
    services = compose_data.get('services', {})

    for service_name, config in services.items():
        service_info = {
            'name': service_name,
            'image': config.get('image', 'N/A'),
            'ports': []
        }

        port_mappings = config.get('ports', [])

        for i, port_mapping in enumerate(port_mappings):
            port_info = {
                'host_port': None,
                'container_port': None,
                'protocol': 'tcp',
                'original_mapping': port_mapping,
                'mapping_index': i,
                'env_var': None,  # Track if this port comes from an env var
                'resolved_mapping': port_mapping  # Store the resolved version
            }

            # Resolve environment variables in the port mapping
            if isinstance(port_mapping, str):
                resolved_mapping = resolve_env_variables(port_mapping, env_vars)
                port_info['resolved_mapping'] = resolved_mapping

                # Check if this mapping uses environment variables
                if re.search(r'\$\{[^}]+\}|\$[A-Z_][A-Z0-9_]*', port_mapping):
                    # Extract the environment variable name
                    env_match = re.search(r'\$\{([^}:-]+)', port_mapping) or re.search(r'\$([A-Z_][A-Z0-9_]*)', port_mapping)
                    if env_match:
                        port_info['env_var'] = env_match.group(1)

                port_mapping = resolved_mapping

            if isinstance(port_mapping, str):
                # Handle "host:container" format
                if ':' in port_mapping:
                    parts = port_mapping.split(':')
                    if len(parts) >= 2:
                        host_part = parts[0]
                        container_part = parts[1]
                        if host_part.isdigit():
                            port_info['host_port'] = int(host_part)
                        if container_part.isdigit():
                            port_info['container_port'] = int(container_part)
                        else:
                            # Handle container_port/protocol format
                            if '/' in container_part:
                                container_port, protocol = container_part.split('/')
                                if container_port.isdigit():
                                    port_info['container_port'] = int(container_port)
                                port_info['protocol'] = protocol
                            elif container_part.isdigit():
                                port_info['container_port'] = int(container_part)
                else:
                    # Handle single port format
                    if port_mapping.isdigit():
                        port_info['host_port'] = int(port_mapping)
                        port_info['container_port'] = int(port_mapping)
                    elif '/' in port_mapping:
                        port_part, protocol = port_mapping.split('/')
                        if port_part.isdigit():
                            port_info['host_port'] = int(port_part)
                            port_info['container_port'] = int(port_part)
                        port_info['protocol'] = protocol
            elif isinstance(port_mapping, int):
                # Handle numeric port
                port_info['host_port'] = port_mapping
                port_info['container_port'] = port_mapping
            elif isinstance(port_mapping, dict):
                # Handle long format with published/target keys
                published = port_mapping.get('published')
                target = port_mapping.get('target')
                protocol = port_mapping.get('protocol', 'tcp')

                if published and isinstance(published, (int, str)):
                    if isinstance(published, str):
                        published = resolve_env_variables(published, env_vars)
                        if published.isdigit():
                            port_info['host_port'] = int(published)
                    elif isinstance(published, int):
                        port_info['host_port'] = published

                if target and isinstance(target, (int, str)):
                    if isinstance(target, str):
                        target = resolve_env_variables(target, env_vars)
                        if target.isdigit():
                            port_info['container_port'] = int(target)
                    elif isinstance(target, int):
                        port_info['container_port'] = target

                port_info['protocol'] = protocol

            if port_info['host_port'] is not None:
                service_info['ports'].append(port_info)

        services_info[service_name] = service_info

    return services_info


def get_process_using_port(port: int) -> Optional[Tuple[int, str]]:
    """Get the PID and process name using a specific port."""
    try:
        for conn in psutil.net_connections(kind='inet'):
            if conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
                if conn.pid:
                    try:
                        process = psutil.Process(conn.pid)
                        return conn.pid, process.name()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        return conn.pid, "unknown"
                return None, "unknown"
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        pass
    return None


def is_port_in_use(port: int) -> bool:
    """Check if a port is in use by trying to bind to it."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("0.0.0.0", port))
            return False
    except OSError:
        return True


def get_docker_container_info(port: int) -> Optional[Dict[str, str]]:
    """Get Docker container information for a port if it's used by Docker."""
    try:
        # Get all running containers
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.ID}}\t{{.Names}}\t{{.Image}}"],
            capture_output=True, text=True, check=True
        )

        for line in result.stdout.strip().split('\n'):
            if not line.strip():
                continue

            parts = line.strip().split('\t')
            if len(parts) >= 3:
                container_id, name, image = parts[0], parts[1], parts[2]

                # Check port mappings for this container
                port_result = subprocess.run(
                    ["docker", "port", container_id],
                    capture_output=True, text=True, check=True
                )

                for port_line in port_result.stdout.strip().split('\n'):
                    if not port_line.strip():
                        continue

                    # Parse port mapping like "80/tcp -> 0.0.0.0:8080"
                    if '->' in port_line and f":{port}" in port_line:
                        return {
                            "container_id": container_id,
                            "container_name": name,
                            "image": image
                        }
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Docker not available or command failed
        pass

    return None


def check_service_ports(services_info: Dict[str, Dict]) -> Dict[str, Dict]:
    """Check port usage for all services and add availability information."""
    for service_name, service_info in services_info.items():
        for port_info in service_info['ports']:
            host_port = port_info['host_port']

            if host_port:
                port_info['available'] = not is_port_in_use(host_port)
                port_info['process'] = None
                port_info['docker_container'] = None

                if not port_info['available']:
                    # Get process information
                    process_info = get_process_using_port(host_port)
                    if process_info and process_info[0] is not None:
                        port_info['process'] = {
                            "pid": process_info[0],
                            "name": process_info[1]
                        }

                    # Check if it's a Docker container
                    docker_info = get_docker_container_info(host_port)
                    if docker_info:
                        port_info['docker_container'] = docker_info

    return services_info


def resolve_port_conflicts(compose_data: dict, services_info: Dict[str, Dict],
                         interactive: bool = False, port_range: Tuple[int, int] = (8000, 65535),
                         env_vars: Dict[str, str] = None, env_file_path: str = None) -> Tuple[Dict, Dict[str, str]]:
    """Resolve port conflicts by changing ports in the docker-compose data and/or .env file."""
    if env_vars is None:
        env_vars = {}

    changes_made = {}
    env_changes = {}
    used_ports = set()  # Track ports we've already assigned

    # Collect all currently used ports
    for conn in psutil.net_connections(kind='inet'):
        if conn.status == psutil.CONN_LISTEN:
            used_ports.add(conn.laddr.port)

    for service_name, service_info in services_info.items():
        service_changes = []

        for port_info in service_info['ports']:
            if not port_info.get('available', True):
                old_port = port_info['host_port']

                if interactive:
                    # Interactive mode: ask user for new port
                    while True:
                        try:
                            print(f"\n🔧 Service '{service_name}' port {old_port} is in use")
                            if port_info.get('process'):
                                pid = port_info['process']['pid']
                                name = port_info['process']['name']
                                print(f"   Used by: {name} (PID: {pid})")

                            new_port_input = input(f"   Enter new port for {old_port} (or 'auto' for automatic): ").strip()

                            if new_port_input.lower() == 'auto':
                                new_port = find_available_port(port_range[0], port_range[1], used_ports)
                                break
                            else:
                                new_port = int(new_port_input)
                                if new_port in used_ports or is_port_in_use(new_port):
                                    print(f"   ❌ Port {new_port} is already in use. Please choose another.")
                                    continue
                                break
                        except ValueError:
                            print("   ❌ Please enter a valid port number or 'auto'")
                            continue
                        except KeyboardInterrupt:
                            print("\n\n❌ Operation cancelled by user")
                            sys.exit(1)
                else:
                    # Automatic mode: find available port
                    new_port = find_available_port(port_range[0], port_range[1], used_ports)

                # Track the new port to avoid conflicts
                used_ports.add(new_port)

                # Check if this port comes from an environment variable
                if port_info.get('env_var') and env_file_path:
                    # Update the environment variable instead of the docker-compose file
                    env_var_name = port_info['env_var']
                    env_changes[env_var_name] = str(new_port)
                    env_vars[env_var_name] = str(new_port)  # Update for immediate use
                else:
                    # Update the docker-compose data directly
                    service_config = compose_data['services'][service_name]
                    mapping_index = port_info['mapping_index']
                    original_mapping = port_info['original_mapping']

                    # Create new mapping based on original format
                    if isinstance(original_mapping, str):
                        if ':' in original_mapping:
                            # "host:container" format
                            parts = original_mapping.split(':')
                            new_mapping = f"{new_port}:{parts[1]}"
                        else:
                            # Single port format
                            if port_info['protocol'] != 'tcp':
                                new_mapping = f"{new_port}/{port_info['protocol']}"
                            else:
                                new_mapping = str(new_port)
                    elif isinstance(original_mapping, int):
                        new_mapping = new_port
                    elif isinstance(original_mapping, dict):
                        new_mapping = original_mapping.copy()
                        new_mapping['published'] = new_port
                    else:
                        new_mapping = str(new_port)

                    # Update the ports list
                    service_config['ports'][mapping_index] = new_mapping

                service_changes.append({
                    'old_port': old_port,
                    'new_port': new_port,
                    'container_port': port_info['container_port'],
                    'protocol': port_info['protocol'],
                    'env_var': port_info.get('env_var'),
                    'updated_via_env': port_info.get('env_var') is not None
                })

        if service_changes:
            changes_made[service_name] = service_changes

    return changes_made, env_changes


def format_beautiful_output(services_info: Dict[str, Dict], env_file_path: str = None, uses_env_vars: bool = False) -> str:
    """Format the output in a beautiful, structured way."""
    output_lines = []

    # Header
    output_lines.append("🐳 Docker Compose Port Analysis")
    output_lines.append("=" * 50)
    output_lines.append("")

    # Show environment variable info if applicable
    if uses_env_vars and env_file_path:
        output_lines.append(f"🌍 Using environment file: {env_file_path}")
        output_lines.append("")

    if not services_info:
        output_lines.append("❌ No services found in docker-compose file")
        return "\n".join(output_lines)

    total_ports = sum(len(service['ports']) for service in services_info.values())
    used_ports = sum(
        1 for service in services_info.values()
        for port in service['ports']
        if not port.get('available', True)
    )

    # Summary
    output_lines.append(f"📊 Summary: {len(services_info)} services, {total_ports} ports configured")
    if used_ports == 0:
        output_lines.append("✅ All ports are available!")
    else:
        output_lines.append(f"⚠️  {used_ports} port(s) in use")
    output_lines.append("")

    # Service details
    for service_name, service_info in services_info.items():
        output_lines.append(f"🔧 Service: {service_name}")
        output_lines.append(f"   📦 Image: {service_info['image']}")

        if not service_info['ports']:
            output_lines.append("   🔌 Ports: None configured")
        else:
            output_lines.append("   🔌 Ports:")

            for port_info in service_info['ports']:
                host_port = port_info['host_port']
                container_port = port_info['container_port']
                protocol = port_info['protocol']
                available = port_info.get('available', True)
                env_var = port_info.get('env_var')

                # Format port mapping
                if host_port == container_port:
                    port_display = f"{host_port}/{protocol}"
                else:
                    port_display = f"{host_port}:{container_port}/{protocol}"

                # Add environment variable info if applicable
                if env_var:
                    port_display += f" (${{{env_var}}})"

                # Status indicator
                status = "✅ Available" if available else "❌ In Use"

                output_lines.append(f"      └─ {port_display} - {status}")

                # Additional details for ports in use
                if not available:
                    if port_info.get('process'):
                        pid = port_info['process']['pid']
                        name = port_info['process']['name']
                        output_lines.append(f"         └─ Process: {name} (PID: {pid})")

                    if port_info.get('docker_container'):
                        container = port_info['docker_container']
                        output_lines.append(f"         └─ Docker: {container['container_name']}")
                        output_lines.append(f"            Image: {container['image']}")

        output_lines.append("")

    return "\n".join(output_lines)


def format_changes_output(changes_made: Dict, env_changes: Dict[str, str] = None) -> str:
    """Format the changes made during conflict resolution."""
    if not changes_made and not env_changes:
        return "✅ No changes needed - all ports were available!"

    output_lines = []
    output_lines.append("🔧 Port Conflict Resolution Summary")
    output_lines.append("=" * 50)
    output_lines.append("")

    total_changes = sum(len(changes) for changes in changes_made.values())
    files_updated = []

    if changes_made:
        files_updated.append("docker-compose.yml")
    if env_changes:
        files_updated.append(".env")

    output_lines.append(f"📊 Changed {total_changes} port(s) across {len(changes_made)} service(s)")
    if files_updated:
        output_lines.append(f"📝 Updated files: {', '.join(files_updated)}")
    output_lines.append("")

    # Show environment variable changes first
    if env_changes:
        output_lines.append("🌍 Environment Variable Changes:")
        for env_var, new_value in env_changes.items():
            output_lines.append(f"   └─ {env_var} = {new_value}")
        output_lines.append("")

    # Show service-specific changes
    for service_name, changes in changes_made.items():
        output_lines.append(f"🔧 Service: {service_name}")
        for change in changes:
            old_port = change['old_port']
            new_port = change['new_port']
            container_port = change['container_port']
            protocol = change['protocol']
            env_var = change.get('env_var')
            updated_via_env = change.get('updated_via_env', False)

            if old_port == container_port:
                port_display = f"{old_port}/{protocol} → {new_port}/{protocol}"
            else:
                port_display = f"{old_port}:{container_port}/{protocol} → {new_port}:{container_port}/{protocol}"

            if updated_via_env and env_var:
                port_display += f" (via ${{{env_var}}})"

            output_lines.append(f"   └─ {port_display}")
        output_lines.append("")

    return "\n".join(output_lines)


def format_json_output(services_info: Dict[str, Dict]) -> str:
    """Format the output as JSON."""
    # Convert to a more JSON-friendly format
    json_data = {
        "summary": {
            "total_services": len(services_info),
            "total_ports": sum(len(service['ports']) for service in services_info.values()),
            "ports_in_use": sum(
                1 for service in services_info.values()
                for port in service['ports']
                if not port.get('available', True)
            )
        },
        "services": []
    }

    for service_name, service_info in services_info.items():
        service_data = {
            "name": service_name,
            "image": service_info['image'],
            "ports": []
        }

        for port_info in service_info['ports']:
            port_data = {
                "host_port": port_info['host_port'],
                "container_port": port_info['container_port'],
                "protocol": port_info['protocol'],
                "available": port_info.get('available', True),
                "process": port_info.get('process'),
                "docker_container": port_info.get('docker_container'),
                "env_var": port_info.get('env_var'),
                "original_mapping": port_info.get('original_mapping')
            }
            service_data['ports'].append(port_data)

        json_data['services'].append(service_data)

    return json.dumps(json_data, indent=2)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Check which ports defined in a docker-compose file are already in use.",
        prog="check-docker-compose-ports"
    )

    parser.add_argument(
        "-f", "--file",
        default="docker-compose.yml",
        help="Path to the docker-compose file (default: docker-compose.yml)"
    )

    parser.add_argument(
        "--env-file",
        help="Path to the .env file (auto-detected if not specified)"
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format"
    )

    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Do not exit with error if ports are in use"
    )

    parser.add_argument(
        "--exit-on-used",
        action="store_true",
        help="Exit with code 1 if any port is in use"
    )

    parser.add_argument(
        "--fix",
        action="store_true",
        help="Automatically fix port conflicts by changing to available ports"
    )

    parser.add_argument(
        "--fix-interactive",
        action="store_true",
        help="Interactively fix port conflicts by asking for new ports"
    )

    parser.add_argument(
        "--port-range",
        default="8000-65535",
        help="Port range for automatic conflict resolution (default: 8000-65535)"
    )

    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create a backup of the original files when fixing conflicts"
    )

    args = parser.parse_args()

    # Parse port range
    try:
        if '-' in args.port_range:
            start_port, end_port = map(int, args.port_range.split('-'))
        else:
            start_port, end_port = int(args.port_range), 65535

        if start_port < 1 or end_port > 65535 or start_port >= end_port:
            raise ValueError("Invalid port range")

        port_range = (start_port, end_port)
    except ValueError:
        print("❌ Invalid port range. Use format: '8000-9000' or single port number")
        sys.exit(1)

    # Load and parse docker-compose file
    compose_data = load_docker_compose(args.file)

    # Extract environment variable names used for ports
    port_env_vars = extract_env_port_variables(compose_data)
    uses_env_vars = len(port_env_vars) > 0

    # Determine .env file path
    env_file_path = None
    env_vars = {}

    if args.env_file:
        # User specified an .env file explicitly
        env_file_path = args.env_file
        if not os.path.exists(env_file_path):
            print(f"❌ Error: Specified .env file '{env_file_path}' not found")
            sys.exit(1)
        env_vars = load_env_file(env_file_path)
    elif uses_env_vars:
        # Environment variables detected, try to auto-detect .env file
        default_env_path = ".env"
        if os.path.exists(default_env_path):
            env_file_path = default_env_path
            env_vars = load_env_file(env_file_path)
            if not args.json:
                print(f"🔍 Auto-detected .env file: {env_file_path}")
        else:
            print(f"❌ Error: Environment variables detected in docker-compose file but no .env file found")
            print(f"   Environment variables used for ports: {', '.join(sorted(port_env_vars))}")
            print(f"   Please create a .env file or specify the correct path with --env-file")
            print(f"   Example: check-docker-compose-ports --env-file path/to/your/.env")
            sys.exit(1)

    # Show environment variable detection info
    if uses_env_vars and not args.json:
        print(f"🌍 Environment variables detected: {', '.join(sorted(port_env_vars))}")
        if env_file_path:
            # Check if all required env vars are defined
            missing_vars = port_env_vars - set(env_vars.keys())
            if missing_vars:
                print(f"⚠️  Warning: Missing environment variables: {', '.join(sorted(missing_vars))}")
            else:
                print(f"✅ All required environment variables found in {env_file_path}")
        print("")

    # Extract service and port information (with env var resolution)
    services_info = extract_service_ports(compose_data, env_vars)

    # Check port usage
    services_info = check_service_ports(services_info)

    # Check if we need to fix conflicts
    has_conflicts = any(
        not port.get('available', True)
        for service in services_info.values()
        for port in service['ports']
    )

    if (args.fix or args.fix_interactive) and has_conflicts:
        if not env_file_path and uses_env_vars:
            print("❌ Error: Cannot fix conflicts without a valid .env file")
            print("   Please specify the .env file path with --env-file")
            sys.exit(1)

        # Create backups if requested
        if args.backup:
            # Backup docker-compose file
            backup_path = args.file + '.backup'
            shutil.copy2(args.file, backup_path)
            print(f"💾 Backup created: {backup_path}")

            # Backup .env file if it exists
            if env_file_path and os.path.exists(env_file_path):
                env_backup_path = env_file_path + '.backup'
                shutil.copy2(env_file_path, env_backup_path)
                print(f"💾 Backup created: {env_backup_path}")

        # Resolve conflicts
        print("🔧 Resolving port conflicts...")
        changes_made, env_changes = resolve_port_conflicts(
            compose_data,
            services_info,
            interactive=args.fix_interactive,
            port_range=port_range,
            env_vars=env_vars,
            env_file_path=env_file_path
        )

        if changes_made or env_changes:
            # Save the updated docker-compose file if needed
            if changes_made:
                save_docker_compose(compose_data, args.file)
                print(f"✅ Updated {args.file} with resolved ports")

            # Save the updated .env file if needed
            if env_changes and env_file_path:
                # Update env_vars with changes and save
                env_vars.update(env_changes)
                save_env_file(env_vars, env_file_path)
                print(f"✅ Updated {env_file_path} with resolved ports")

            # Show changes summary
            print("\n" + format_changes_output(changes_made, env_changes))

            # Re-check the ports to show the updated status
            services_info = extract_service_ports(compose_data, env_vars)
            services_info = check_service_ports(services_info)
        else:
            print("✅ No conflicts found to resolve")

    # Output results
    if not (args.fix or args.fix_interactive) or not has_conflicts:
        if args.json:
            # Add environment variable info to JSON output
            json_output = json.loads(format_json_output(services_info))
            json_output["environment"] = {
                "uses_env_vars": uses_env_vars,
                "env_file_path": env_file_path,
                "env_vars_detected": sorted(port_env_vars) if port_env_vars else [],
                "env_vars_loaded": len(env_vars) if env_vars else 0
            }
            print(json.dumps(json_output, indent=2))
        else:
            output = format_beautiful_output(services_info, env_file_path, uses_env_vars)
            print(output)

    # Handle exit codes
    used_ports = sum(
        1 for service in services_info.values()
        for port in service['ports']
        if not port.get('available', True)
    )

    if used_ports > 0 and args.exit_on_used and not (args.fix or args.fix_interactive):
        sys.exit(1)
    elif used_ports > 0 and not args.warn_only and not (args.fix or args.fix_interactive):
        sys.exit(1)
