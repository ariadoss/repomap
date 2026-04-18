"""Detect database connection configurations from project files."""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DbConfig:
    """A detected database connection configuration."""

    dsn: str
    source: str  # Human-readable description of where it was found
    file_path: str  # Path to the file it was found in
    db_type: str = ""  # mysql, postgres, sqlite, etc.
    name: str = ""  # Database name if detectable
    extras: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.db_type:
            self.db_type = _detect_db_type(self.dsn)
        if not self.name:
            self.name = _extract_db_name(self.dsn)


def _detect_db_type(dsn):
    """Detect database type from DSN string."""
    dsn_lower = dsn.lower()
    if "postgres" in dsn_lower or dsn_lower.startswith("pg:"):
        return "postgres"
    if "mysql" in dsn_lower or "mariadb" in dsn_lower:
        return "mysql"
    if "sqlite" in dsn_lower:
        return "sqlite"
    if "sqlserver" in dsn_lower or "mssql" in dsn_lower:
        return "mssql"
    if "oracle" in dsn_lower:
        return "oracle"
    return "unknown"


def _extract_db_name(dsn):
    """Extract database name from DSN."""
    # URL-style: scheme://user:pass@host:port/dbname
    match = re.search(r"://[^/]*/([^?]+)", dsn)
    if match:
        return match.group(1)
    return ""


def _read_file_safe(path):
    """Read a file, returning empty string on failure."""
    try:
        return Path(path).read_text(errors="replace")
    except (OSError, PermissionError):
        return ""


def _parse_env_file(path):
    """Parse a .env file into a dict of key=value pairs."""
    env = {}
    content = _read_file_safe(path)
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        env[key] = value
    return env


# ---------------------------------------------------------------------------
# Individual detectors — each returns a list of DbConfig
# ---------------------------------------------------------------------------


def detect_env_file(repo_root):
    """Detect DATABASE_URL and DB_* vars from .env files."""
    configs = []
    env_names = [".env", ".env.local", ".env.development", ".env.dev", ".env.example"]

    # Search root and immediate subdirectories
    search_dirs = [repo_root] + [
        d for d in repo_root.iterdir()
        if d.is_dir() and d.name not in ("node_modules", ".git", "vendor", "venv")
    ]

    env_files = []
    for d in search_dirs:
        for name in env_names:
            env_files.append((d / name, name if d == repo_root else f"{d.name}/{name}"))

    for path, display_name in env_files:
        if not path.is_file():
            continue
        env = _parse_env_file(path)
        name = display_name
        env = _parse_env_file(path)

        # DATABASE_URL (Prisma, Rails, generic)
        for key in ("DATABASE_URL", "DB_URL", "DATABASE_URI"):
            if key in env and env[key]:
                configs.append(DbConfig(
                    dsn=env[key],
                    source=f"{name} → {key}",
                    file_path=str(path),
                ))

        # Laravel-style DB_HOST + DB_DATABASE
        if "DB_HOST" in env and "DB_DATABASE" in env:
            driver = env.get("DB_CONNECTION", env.get("DB_DRIVER", "mysql"))
            host = env["DB_HOST"]
            port = env.get("DB_PORT", "3306")
            db = env["DB_DATABASE"]
            user = env.get("DB_USERNAME", env.get("DB_USER", "root"))
            password = env.get("DB_PASSWORD", "")

            dsn = f"{driver}://{user}:{password}@{host}:{port}/{db}"
            configs.append(DbConfig(
                dsn=dsn,
                source=f"{name} → DB_HOST/DB_DATABASE",
                file_path=str(path),
            ))

    return configs


def detect_prisma(repo_root):
    """Detect database URL from Prisma schema."""
    configs = []
    schema_paths = [
        repo_root / "prisma" / "schema.prisma",
        repo_root / "schema.prisma",
    ]
    # Also check in subdirectories
    for p in repo_root.glob("**/schema.prisma"):
        if "node_modules" not in str(p):
            schema_paths.append(p)

    for schema_path in schema_paths:
        if not schema_path.is_file():
            continue
        content = _read_file_safe(schema_path)

        # Look for url = env("DATABASE_URL") or direct URL
        url_match = re.search(
            r'url\s*=\s*env\(\s*"([^"]+)"\s*\)', content
        )
        if url_match:
            env_var = url_match.group(1)
            # Try to resolve from .env
            env_file = schema_path.parent.parent / ".env"
            if not env_file.is_file():
                env_file = repo_root / ".env"
            if env_file.is_file():
                env = _parse_env_file(env_file)
                if env_var in env:
                    configs.append(DbConfig(
                        dsn=env[env_var],
                        source=f"Prisma schema → env({env_var})",
                        file_path=str(schema_path),
                    ))
            continue

        # Direct URL in schema
        direct_match = re.search(r'url\s*=\s*"([^"]+)"', content)
        if direct_match:
            configs.append(DbConfig(
                dsn=direct_match.group(1),
                source="Prisma schema → direct URL",
                file_path=str(schema_path),
            ))

    return configs


def detect_django(repo_root):
    """Detect database config from Django settings."""
    configs = []
    candidates = list(repo_root.glob("**/settings.py"))
    candidates += list(repo_root.glob("**/settings/*.py"))

    for path in candidates:
        if "node_modules" in str(path) or "venv" in str(path):
            continue
        content = _read_file_safe(path)

        if "DATABASES" not in content:
            continue

        # Try to extract ENGINE + NAME from DATABASES default
        engine_match = re.search(
            r"['\"]ENGINE['\"]\s*:\s*['\"]([^'\"]+)['\"]", content
        )
        name_match = re.search(
            r"['\"]NAME['\"]\s*:\s*['\"]([^'\"]+)['\"]", content
        )
        host_match = re.search(
            r"['\"]HOST['\"]\s*:\s*['\"]([^'\"]+)['\"]", content
        )
        port_match = re.search(
            r"['\"]PORT['\"]\s*:\s*['\"]([^'\"]+)['\"]", content
        )
        user_match = re.search(
            r"['\"]USER['\"]\s*:\s*['\"]([^'\"]+)['\"]", content
        )
        pass_match = re.search(
            r"['\"]PASSWORD['\"]\s*:\s*['\"]([^'\"]*)['\"]", content
        )

        if engine_match and name_match:
            engine = engine_match.group(1)
            db_name = name_match.group(1)
            host = host_match.group(1) if host_match else "localhost"
            port = port_match.group(1) if port_match else ""
            user = user_match.group(1) if user_match else ""
            password = pass_match.group(1) if pass_match else ""

            # Map Django engine to scheme
            scheme = "postgres"
            if "mysql" in engine:
                scheme = "mysql"
            elif "sqlite" in engine:
                configs.append(DbConfig(
                    dsn=f"sqlite://{db_name}",
                    source=f"Django settings → {path.name}",
                    file_path=str(path),
                ))
                continue
            elif "postgres" in engine:
                scheme = "postgres"

            port_str = f":{port}" if port else ""
            auth = f"{user}:{password}@" if user else ""
            dsn = f"{scheme}://{auth}{host}{port_str}/{db_name}"
            configs.append(DbConfig(
                dsn=dsn,
                source=f"Django settings → {path.name}",
                file_path=str(path),
            ))

    return configs


def detect_rails(repo_root):
    """Detect database config from Rails database.yml."""
    configs = []
    db_yml = repo_root / "config" / "database.yml"
    if not db_yml.is_file():
        return configs

    content = _read_file_safe(db_yml)

    # Simple YAML parsing — look for development/default sections
    current_env = None
    adapter = host = port = database = username = password = ""

    for line in content.splitlines():
        stripped = line.strip()
        # Top-level key (no indent)
        if not line.startswith(" ") and not line.startswith("\t") and stripped.endswith(":"):
            env_name = stripped[:-1].strip()
            if current_env in ("development", "default") and adapter and database:
                dsn = _build_rails_dsn(
                    adapter, host, port, database, username, password
                )
                configs.append(DbConfig(
                    dsn=dsn,
                    source=f"Rails database.yml → {current_env}",
                    file_path=str(db_yml),
                ))
            current_env = env_name
            adapter = host = port = database = username = password = ""
        elif current_env:
            key_match = re.match(r"\s+(\w+):\s*(.+)", line)
            if key_match:
                k, v = key_match.group(1), key_match.group(2).strip().strip("'\"")
                if "<%=" in v:
                    continue  # ERB template, skip
                if k == "adapter":
                    adapter = v
                elif k == "host":
                    host = v
                elif k == "port":
                    port = v
                elif k == "database":
                    database = v
                elif k == "username":
                    username = v
                elif k == "password":
                    password = v

    # Capture last section
    if current_env in ("development", "default") and adapter and database:
        dsn = _build_rails_dsn(adapter, host, port, database, username, password)
        configs.append(DbConfig(
            dsn=dsn,
            source=f"Rails database.yml → {current_env}",
            file_path=str(db_yml),
        ))

    return configs


def _build_rails_dsn(adapter, host, port, database, username, password):
    scheme = adapter.replace("2", "")  # postgresql2 → postgresql
    if "sqlite" in scheme:
        return f"sqlite://{database}"
    host = host or "localhost"
    port_str = f":{port}" if port else ""
    auth = f"{username}:{password}@" if username else ""
    return f"{scheme}://{auth}{host}{port_str}/{database}"


def detect_knex(repo_root):
    """Detect database config from knexfile.js/ts."""
    configs = []
    candidates = ["knexfile.js", "knexfile.ts", "knexfile.mjs"]

    for name in candidates:
        path = repo_root / name
        if not path.is_file():
            continue
        content = _read_file_safe(path)

        # Look for connection string
        conn_match = re.search(
            r"connection\s*:\s*['\"]([^'\"]+)['\"]", content
        )
        if conn_match:
            configs.append(DbConfig(
                dsn=conn_match.group(1),
                source=f"Knex → {name}",
                file_path=str(path),
            ))
            continue

        # Look for connection object with host/database
        conn_block = re.search(
            r"connection\s*:\s*\{([^}]+)\}", content, re.DOTALL
        )
        if conn_block:
            block = conn_block.group(1)
            host = _extract_js_prop(block, "host") or "localhost"
            port = _extract_js_prop(block, "port") or ""
            db = _extract_js_prop(block, "database") or ""
            user = _extract_js_prop(block, "user") or ""
            pw = _extract_js_prop(block, "password") or ""
            client_match = re.search(
                r"client\s*:\s*['\"]([^'\"]+)['\"]", content
            )
            scheme = client_match.group(1) if client_match else "postgres"
            if db:
                port_str = f":{port}" if port else ""
                auth = f"{user}:{pw}@" if user else ""
                dsn = f"{scheme}://{auth}{host}{port_str}/{db}"
                configs.append(DbConfig(
                    dsn=dsn,
                    source=f"Knex → {name}",
                    file_path=str(path),
                ))

    return configs


def detect_sequelize(repo_root):
    """Detect database config from Sequelize config."""
    configs = []
    candidates = [
        repo_root / "config" / "config.json",
        repo_root / ".sequelizerc",
    ]

    for path in candidates:
        if not path.is_file():
            continue

        if path.name == "config.json":
            try:
                data = json.loads(_read_file_safe(path))
                for env_name in ("development", "default", "test"):
                    if env_name in data:
                        cfg = data[env_name]
                        if "use_env_variable" in cfg:
                            env_val = os.environ.get(cfg["use_env_variable"], "")
                            if env_val:
                                configs.append(DbConfig(
                                    dsn=env_val,
                                    source=f"Sequelize config.json → {env_name}",
                                    file_path=str(path),
                                ))
                        elif "host" in cfg and "database" in cfg:
                            dialect = cfg.get("dialect", "postgres")
                            host = cfg.get("host", "localhost")
                            port = cfg.get("port", "")
                            db = cfg["database"]
                            user = cfg.get("username", "")
                            pw = cfg.get("password", "")
                            port_str = f":{port}" if port else ""
                            auth = f"{user}:{pw}@" if user else ""
                            dsn = f"{dialect}://{auth}{host}{port_str}/{db}"
                            configs.append(DbConfig(
                                dsn=dsn,
                                source=f"Sequelize config.json → {env_name}",
                                file_path=str(path),
                            ))
                        break
            except (json.JSONDecodeError, KeyError):
                pass

    return configs


def detect_typeorm(repo_root):
    """Detect database config from TypeORM ormconfig."""
    configs = []
    candidates = [
        "ormconfig.json",
        "ormconfig.js",
        "ormconfig.ts",
    ]

    for name in candidates:
        path = repo_root / name
        if not path.is_file():
            continue

        if name.endswith(".json"):
            try:
                data = json.loads(_read_file_safe(path))
                if isinstance(data, list):
                    data = data[0]
                if "url" in data:
                    configs.append(DbConfig(
                        dsn=data["url"],
                        source=f"TypeORM → {name}",
                        file_path=str(path),
                    ))
                elif "host" in data and "database" in data:
                    t = data.get("type", "postgres")
                    h = data.get("host", "localhost")
                    p = data.get("port", "")
                    d = data["database"]
                    u = data.get("username", "")
                    pw = data.get("password", "")
                    port_str = f":{p}" if p else ""
                    auth = f"{u}:{pw}@" if u else ""
                    dsn = f"{t}://{auth}{h}{port_str}/{d}"
                    configs.append(DbConfig(
                        dsn=dsn,
                        source=f"TypeORM → {name}",
                        file_path=str(path),
                    ))
            except (json.JSONDecodeError, KeyError):
                pass
        else:
            content = _read_file_safe(path)
            url_match = re.search(r"url\s*:\s*['\"]([^'\"]+)['\"]", content)
            if url_match:
                configs.append(DbConfig(
                    dsn=url_match.group(1),
                    source=f"TypeORM → {name}",
                    file_path=str(path),
                ))

    return configs


def detect_sqlalchemy(repo_root):
    """Detect SQLAlchemy database URLs."""
    configs = []
    candidates = list(repo_root.glob("**/*.py"))

    for path in candidates:
        if "node_modules" in str(path) or "venv" in str(path) or ".tox" in str(path):
            continue
        content = _read_file_safe(path)

        # Look for create_engine("dsn") or SQLALCHEMY_DATABASE_URI
        for pattern in [
            r'create_engine\(\s*["\']([^"\']+)["\']',
            r'SQLALCHEMY_DATABASE_URI\s*=\s*["\']([^"\']+)["\']',
        ]:
            match = re.search(pattern, content)
            if match:
                dsn = match.group(1)
                if "://" in dsn:
                    configs.append(DbConfig(
                        dsn=dsn,
                        source=f"SQLAlchemy → {path.name}",
                        file_path=str(path),
                    ))
                break  # One per file

    return configs


def detect_frappe(repo_root):
    """Detect database config from Frappe site_config.json."""
    configs = []
    candidates = list(repo_root.glob("**/site_config.json"))

    for path in candidates:
        if "node_modules" in str(path):
            continue
        try:
            data = json.loads(_read_file_safe(path))
            host = data.get("db_host", "localhost")
            port = data.get("db_port", "3306")
            name = data.get("db_name", "")
            user = data.get("db_user", data.get("db_name", ""))
            password = data.get("db_password", "")
            db_type = data.get("db_type", "mariadb")

            if name:
                scheme = "mysql" if "maria" in db_type or "mysql" in db_type else db_type
                dsn = f"{scheme}://{user}:{password}@{host}:{port}/{name}"
                configs.append(DbConfig(
                    dsn=dsn,
                    source=f"Frappe site_config.json",
                    file_path=str(path),
                ))
        except (json.JSONDecodeError, KeyError):
            pass

    return configs


def detect_go_config(repo_root):
    """Detect database DSN from Go config files."""
    configs = []
    # Check for common Go config patterns
    for pattern in ["*.go", "config/*.yaml", "config/*.yml", "config/*.toml",
                     "*.yaml", "*.yml"]:
        for path in repo_root.glob(pattern):
            if "vendor" in str(path) or "node_modules" in str(path):
                continue
            content = _read_file_safe(path)

            # DSN string patterns common in Go
            for regex in [
                r'dsn\s*[:=]\s*["\']([^"\']+://[^"\']+)["\']',
                r'DSN\s*[:=]\s*["\']([^"\']+://[^"\']+)["\']',
                r'connectionString\s*[:=]\s*["\']([^"\']+://[^"\']+)["\']',
            ]:
                match = re.search(regex, content, re.IGNORECASE)
                if match:
                    configs.append(DbConfig(
                        dsn=match.group(1),
                        source=f"Go config → {path.name}",
                        file_path=str(path),
                    ))
                    break
            else:
                # YAML database block: database.host, database.name, etc.
                if path.suffix in (".yaml", ".yml") and "database:" in content:
                    db_section = False
                    db_props = {}
                    for line in content.splitlines():
                        stripped = line.strip()
                        if stripped == "database:":
                            db_section = True
                            continue
                        if db_section:
                            if line and not line[0].isspace():
                                break  # Left the database section
                            kv = re.match(r'\s+(\w+)\s*:\s*"?([^"#\n]+)"?', line)
                            if kv:
                                db_props[kv.group(1)] = kv.group(2).strip().strip('"\'')

                    if "name" in db_props:
                        host = db_props.get("host", "localhost")
                        port = db_props.get("port", "3306")
                        user = db_props.get("user", db_props.get("username", "root"))
                        pw = db_props.get("password", "")
                        db = db_props["name"]
                        driver = db_props.get("driver", "mysql")
                        dsn = f"{driver}://{user}:{pw}@{host}:{port}/{db}"
                        configs.append(DbConfig(
                            dsn=dsn,
                            source=f"YAML config → {path.name}",
                            file_path=str(path),
                        ))

    return configs


def detect_docker_compose(repo_root):
    """Detect database from docker-compose.yml service definitions."""
    configs = []
    for name in ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"]:
        path = repo_root / name
        if not path.is_file():
            continue
        content = _read_file_safe(path)

        # Look for MYSQL_DATABASE, MARIADB_DATABASE, POSTGRES_DB, etc.
        mysql_db = (
            re.search(r"MYSQL_DATABASE[=:]\s*(\S+)", content)
            or re.search(r"MARIADB_DATABASE[=:]\s*(\S+)", content)
        )
        mysql_user = (
            re.search(r"MYSQL_USER[=:]\s*(\S+)", content)
            or re.search(r"MARIADB_USER[=:]\s*(\S+)", content)
        )
        mysql_pass = (
            re.search(r"MYSQL_PASSWORD[=:]\s*(\S+)", content)
            or re.search(r"MARIADB_PASSWORD[=:]\s*(\S+)", content)
        )
        mysql_port = re.search(r"(\d+):3306", content)

        if mysql_db:
            db = mysql_db.group(1).strip("'\"")
            user = mysql_user.group(1).strip("'\"") if mysql_user else "root"
            pw = mysql_pass.group(1).strip("'\"") if mysql_pass else ""
            port = mysql_port.group(1) if mysql_port else "3306"
            dsn = f"mysql://{user}:{pw}@localhost:{port}/{db}"
            configs.append(DbConfig(
                dsn=dsn,
                source=f"docker-compose → MySQL service",
                file_path=str(path),
            ))

        pg_db = re.search(r"POSTGRES_DB[=:]\s*(\S+)", content)
        pg_user = re.search(r"POSTGRES_USER[=:]\s*(\S+)", content)
        pg_pass = re.search(r"POSTGRES_PASSWORD[=:]\s*(\S+)", content)
        pg_port = re.search(r"(\d+):5432", content)

        if pg_db:
            db = pg_db.group(1).strip("'\"")
            user = pg_user.group(1).strip("'\"") if pg_user else "postgres"
            pw = pg_pass.group(1).strip("'\"") if pg_pass else ""
            port = pg_port.group(1) if pg_port else "5432"
            dsn = f"postgres://{user}:{pw}@localhost:{port}/{db}"
            configs.append(DbConfig(
                dsn=dsn,
                source=f"docker-compose → PostgreSQL service",
                file_path=str(path),
            ))

    return configs


def detect_generic_config(repo_root):
    """Detect database config from generic config files (.cfg, .ini, .conf, wp-config.php)."""
    configs = []

    # WordPress wp-config.php
    for path in repo_root.glob("**/wp-config.php"):
        if "node_modules" in str(path):
            continue
        content = _read_file_safe(path)
        db_name = re.search(r"define\s*\(\s*'DB_NAME'\s*,\s*'([^']+)'", content)
        db_user = re.search(r"define\s*\(\s*'DB_USER'\s*,\s*'([^']+)'", content)
        db_pass = re.search(r"define\s*\(\s*'DB_PASSWORD'\s*,\s*'([^']*)'", content)
        db_host = re.search(r"define\s*\(\s*'DB_HOST'\s*,\s*'([^']+)'", content)
        if db_name:
            host = db_host.group(1) if db_host else "localhost"
            user = db_user.group(1) if db_user else "root"
            pw = db_pass.group(1) if db_pass else ""
            db = db_name.group(1)
            dsn = f"mysql://{user}:{pw}@{host}/{db}"
            configs.append(DbConfig(
                dsn=dsn,
                source=f"WordPress → wp-config.php",
                file_path=str(path),
            ))

    # Generic .cfg/.ini files with MUSER/MPASS/MHOST or DB_USER/DB_PASS patterns
    for pattern in ["**/*.cfg", "**/*.ini", "**/db_config*", "**/database.*"]:
        for path in repo_root.glob(pattern):
            if "node_modules" in str(path) or ".example" in str(path):
                continue
            content = _read_file_safe(path)
            props = {}
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith(";"):
                    continue
                match = re.match(r'(\w+)\s*=\s*"?([^"#\n]*)"?', line)
                if match:
                    props[match.group(1).upper()] = match.group(2).strip().strip('"\'')

            # MySQL style: MUSER, MPASS, MHOST or DB_USER, DB_PASS, DB_HOST
            user = props.get("MUSER", props.get("DB_USER", props.get("DBUSER", "")))
            pw = props.get("MPASS", props.get("DB_PASS", props.get("DBPASS", "")))
            host = props.get("MHOST", props.get("DB_HOST", props.get("DBHOST", "localhost")))
            port = props.get("MPORT", props.get("DB_PORT", props.get("DBPORT", "")))
            db = props.get("MNAME", props.get("DB_NAME", props.get("DBNAME", "")))

            if user and host:
                port_str = f":{port}" if port else ""
                db_str = f"/{db}" if db else ""
                dsn = f"mysql://{user}:{pw}@{host}{port_str}{db_str}"
                configs.append(DbConfig(
                    dsn=dsn,
                    source=f"Config file → {path.name}",
                    file_path=str(path),
                ))

    return configs


def _extract_js_prop(block, prop):
    """Extract a JS property value from a block of text."""
    match = re.search(rf"{prop}\s*:\s*['\"]([^'\"]*)['\"]", block)
    return match.group(1) if match else ""


# ---------------------------------------------------------------------------
# Main detection orchestrator
# ---------------------------------------------------------------------------

ALL_DETECTORS = [
    ("Environment files", detect_env_file),
    ("Prisma", detect_prisma),
    ("Django", detect_django),
    ("Rails", detect_rails),
    ("Knex", detect_knex),
    ("Sequelize", detect_sequelize),
    ("TypeORM", detect_typeorm),
    ("SQLAlchemy", detect_sqlalchemy),
    ("Frappe", detect_frappe),
    ("Go config", detect_go_config),
    ("Docker Compose", detect_docker_compose),
    ("Generic config", detect_generic_config),
]


def detect_all(repo_root):
    """Run all detectors and return deduplicated list of DbConfig.

    Results are deduplicated by DSN — if multiple detectors find the
    same connection string, only the first is kept.
    """
    repo_root = Path(repo_root).resolve()
    all_configs = []
    seen_dsns = set()

    for _name, detector in ALL_DETECTORS:
        try:
            results = detector(repo_root)
            for cfg in results:
                if cfg.dsn not in seen_dsns:
                    seen_dsns.add(cfg.dsn)
                    all_configs.append(cfg)
        except Exception:
            continue

    return all_configs


def mask_password(dsn):
    """Mask the password in a DSN for display purposes."""
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:****@", dsn)
