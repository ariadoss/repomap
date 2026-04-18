"""Tests for dbmap.detector — database config detection."""

import json
from pathlib import Path

import pytest

from dbmap.detector import (
    DbConfig,
    _detect_db_type,
    _extract_db_name,
    _parse_env_file,
    detect_all,
    detect_django,
    detect_docker_compose,
    detect_env_file,
    detect_frappe,
    detect_generic_config,
    detect_go_config,
    detect_knex,
    detect_prisma,
    detect_rails,
    detect_sequelize,
    detect_sqlalchemy,
    detect_typeorm,
    mask_password,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestDbType:
    def test_postgres(self):
        assert _detect_db_type("postgres://localhost/db") == "postgres"
        assert _detect_db_type("postgresql://localhost/db") == "postgres"

    def test_mysql(self):
        assert _detect_db_type("mysql://localhost/db") == "mysql"
        assert _detect_db_type("mariadb://localhost/db") == "mysql"

    def test_sqlite(self):
        assert _detect_db_type("sqlite:///path/db.sqlite3") == "sqlite"

    def test_mssql(self):
        assert _detect_db_type("sqlserver://localhost/db") == "mssql"

    def test_unknown(self):
        assert _detect_db_type("some://thing") == "unknown"


class TestExtractDbName:
    def test_url_style(self):
        assert _extract_db_name("postgres://user:pass@host:5432/mydb") == "mydb"

    def test_with_params(self):
        assert _extract_db_name("mysql://u:p@h/db?ssl=true") == "db"

    def test_no_db(self):
        assert _extract_db_name("nope") == ""


class TestMaskPassword:
    def test_masks_password(self):
        assert mask_password("mysql://user:secret@host/db") == "mysql://user:****@host/db"

    def test_no_password(self):
        assert mask_password("sqlite:///db.sqlite3") == "sqlite:///db.sqlite3"


class TestParseEnvFile:
    def test_basic(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text('DATABASE_URL=postgres://u:p@h/db\nDEBUG=true\n')
        result = _parse_env_file(f)
        assert result["DATABASE_URL"] == "postgres://u:p@h/db"
        assert result["DEBUG"] == "true"

    def test_quoted_values(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text('DB_URL="mysql://u:p@h/db"\n')
        result = _parse_env_file(f)
        assert result["DB_URL"] == "mysql://u:p@h/db"

    def test_comments_and_blanks(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text('# comment\n\nKEY=val\n')
        result = _parse_env_file(f)
        assert result == {"KEY": "val"}

    def test_missing_file(self, tmp_path):
        result = _parse_env_file(tmp_path / "nope")
        assert result == {}


# ---------------------------------------------------------------------------
# Individual detectors
# ---------------------------------------------------------------------------


class TestDetectEnvFile:
    def test_database_url(self, tmp_path):
        (tmp_path / ".env").write_text("DATABASE_URL=postgres://u:p@h:5432/db\n")
        configs = detect_env_file(tmp_path)
        assert len(configs) >= 1
        assert configs[0].dsn == "postgres://u:p@h:5432/db"

    def test_laravel_style(self, tmp_path):
        (tmp_path / ".env").write_text(
            "DB_CONNECTION=mysql\nDB_HOST=127.0.0.1\nDB_PORT=3306\n"
            "DB_DATABASE=laravel\nDB_USERNAME=root\nDB_PASSWORD=secret\n"
        )
        configs = detect_env_file(tmp_path)
        assert len(configs) >= 1
        assert "laravel" in configs[0].dsn
        assert "mysql" in configs[0].dsn

    def test_subdirectory_env(self, tmp_path):
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        (app_dir / ".env").write_text("DATABASE_URL=mysql://u:p@h/db\n")
        configs = detect_env_file(tmp_path)
        assert len(configs) >= 1

    def test_no_env_file(self, tmp_path):
        configs = detect_env_file(tmp_path)
        assert configs == []


class TestDetectPrisma:
    def test_env_reference(self, tmp_path):
        prisma_dir = tmp_path / "prisma"
        prisma_dir.mkdir()
        (prisma_dir / "schema.prisma").write_text(
            'datasource db {\n  provider = "mysql"\n  url = env("DATABASE_URL")\n}\n'
        )
        (tmp_path / ".env").write_text("DATABASE_URL=mysql://u:p@h:3306/db\n")
        configs = detect_prisma(tmp_path)
        assert len(configs) >= 1
        assert configs[0].dsn == "mysql://u:p@h:3306/db"
        assert "Prisma" in configs[0].source

    def test_direct_url(self, tmp_path):
        prisma_dir = tmp_path / "prisma"
        prisma_dir.mkdir()
        (prisma_dir / "schema.prisma").write_text(
            'datasource db {\n  url = "postgres://u:p@h/db"\n}\n'
        )
        configs = detect_prisma(tmp_path)
        assert len(configs) >= 1
        assert "postgres" in configs[0].dsn

    def test_no_schema(self, tmp_path):
        configs = detect_prisma(tmp_path)
        assert configs == []


class TestDetectDjango:
    def test_basic_settings(self, tmp_path):
        (tmp_path / "settings.py").write_text(
            "DATABASES = {\n"
            "    'default': {\n"
            "        'ENGINE': 'django.db.backends.postgresql',\n"
            "        'NAME': 'mydb',\n"
            "        'HOST': 'localhost',\n"
            "        'PORT': '5432',\n"
            "        'USER': 'admin',\n"
            "        'PASSWORD': 'secret',\n"
            "    }\n"
            "}\n"
        )
        configs = detect_django(tmp_path)
        assert len(configs) == 1
        assert "postgres" in configs[0].dsn
        assert "mydb" in configs[0].dsn

    def test_sqlite(self, tmp_path):
        (tmp_path / "settings.py").write_text(
            "DATABASES = {\n"
            "    'default': {\n"
            "        'ENGINE': 'django.db.backends.sqlite3',\n"
            "        'NAME': 'db.sqlite3',\n"
            "    }\n"
            "}\n"
        )
        configs = detect_django(tmp_path)
        assert len(configs) == 1
        assert "sqlite" in configs[0].dsn

    def test_no_settings(self, tmp_path):
        configs = detect_django(tmp_path)
        assert configs == []


class TestDetectRails:
    def test_development_config(self, tmp_path):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "database.yml").write_text(
            "development:\n"
            "  adapter: postgresql\n"
            "  host: localhost\n"
            "  port: 5432\n"
            "  database: myapp_dev\n"
            "  username: dev\n"
            "  password: devpass\n"
        )
        configs = detect_rails(tmp_path)
        assert len(configs) == 1
        assert "myapp_dev" in configs[0].dsn

    def test_no_database_yml(self, tmp_path):
        configs = detect_rails(tmp_path)
        assert configs == []


class TestDetectKnex:
    def test_connection_string(self, tmp_path):
        (tmp_path / "knexfile.js").write_text(
            "module.exports = {\n"
            "  client: 'pg',\n"
            "  connection: 'postgres://u:p@h:5432/db'\n"
            "};\n"
        )
        configs = detect_knex(tmp_path)
        assert len(configs) == 1
        assert "postgres" in configs[0].dsn

    def test_connection_object(self, tmp_path):
        (tmp_path / "knexfile.js").write_text(
            "module.exports = {\n"
            "  client: 'mysql',\n"
            "  connection: {\n"
            "    host: '127.0.0.1',\n"
            "    database: 'mydb',\n"
            "    user: 'root',\n"
            "    password: 'pass'\n"
            "  }\n"
            "};\n"
        )
        configs = detect_knex(tmp_path)
        assert len(configs) == 1
        assert "mydb" in configs[0].dsn


class TestDetectSequelize:
    def test_config_json(self, tmp_path):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "config.json").write_text(json.dumps({
            "development": {
                "username": "root",
                "password": "pass",
                "database": "app_dev",
                "host": "127.0.0.1",
                "dialect": "mysql",
            }
        }))
        configs = detect_sequelize(tmp_path)
        assert len(configs) == 1
        assert "app_dev" in configs[0].dsn

    def test_no_config(self, tmp_path):
        configs = detect_sequelize(tmp_path)
        assert configs == []


class TestDetectTypeORM:
    def test_json_with_url(self, tmp_path):
        (tmp_path / "ormconfig.json").write_text(json.dumps({
            "type": "postgres",
            "url": "postgres://u:p@h:5432/db",
        }))
        configs = detect_typeorm(tmp_path)
        assert len(configs) == 1
        assert configs[0].dsn == "postgres://u:p@h:5432/db"

    def test_json_with_host(self, tmp_path):
        (tmp_path / "ormconfig.json").write_text(json.dumps({
            "type": "mysql",
            "host": "localhost",
            "port": 3306,
            "database": "mydb",
            "username": "root",
            "password": "pass",
        }))
        configs = detect_typeorm(tmp_path)
        assert len(configs) == 1
        assert "mydb" in configs[0].dsn

    def test_ts_with_url(self, tmp_path):
        (tmp_path / "ormconfig.ts").write_text(
            "export default {\n  url: 'postgres://u:p@h/db'\n};\n"
        )
        configs = detect_typeorm(tmp_path)
        assert len(configs) == 1


class TestDetectSQLAlchemy:
    def test_create_engine(self, tmp_path):
        (tmp_path / "app.py").write_text(
            "from sqlalchemy import create_engine\n"
            "engine = create_engine('postgresql://u:p@h:5432/db')\n"
        )
        configs = detect_sqlalchemy(tmp_path)
        assert len(configs) == 1
        assert "postgres" in configs[0].db_type

    def test_flask_config(self, tmp_path):
        (tmp_path / "config.py").write_text(
            "SQLALCHEMY_DATABASE_URI = 'mysql://u:p@h/db'\n"
        )
        configs = detect_sqlalchemy(tmp_path)
        assert len(configs) == 1


class TestDetectFrappe:
    def test_site_config(self, tmp_path):
        site_dir = tmp_path / "sites" / "mysite"
        site_dir.mkdir(parents=True)
        (site_dir / "site_config.json").write_text(json.dumps({
            "db_host": "localhost",
            "db_port": 3306,
            "db_name": "mysite_db",
            "db_password": "secret",
            "db_type": "mariadb",
        }))
        configs = detect_frappe(tmp_path)
        assert len(configs) == 1
        assert "mysite_db" in configs[0].dsn


class TestDetectDockerCompose:
    def test_mysql(self, tmp_path):
        (tmp_path / "docker-compose.yml").write_text(
            "services:\n"
            "  db:\n"
            "    image: mysql:8\n"
            "    environment:\n"
            "      MYSQL_DATABASE: app_db\n"
            "      MYSQL_USER: app\n"
            "      MYSQL_PASSWORD: secret\n"
            "    ports:\n"
            '      - "3307:3306"\n'
        )
        configs = detect_docker_compose(tmp_path)
        assert len(configs) >= 1
        assert "app_db" in configs[0].dsn
        assert "3307" in configs[0].dsn

    def test_mariadb(self, tmp_path):
        (tmp_path / "docker-compose.yml").write_text(
            "services:\n"
            "  db:\n"
            "    image: mariadb:11\n"
            "    environment:\n"
            "      MARIADB_DATABASE: my_db\n"
            "      MARIADB_USER: dbuser\n"
            "      MARIADB_PASSWORD: dbpass\n"
            "    ports:\n"
            '      - "3307:3306"\n'
        )
        configs = detect_docker_compose(tmp_path)
        assert len(configs) >= 1
        assert "my_db" in configs[0].dsn

    def test_postgres(self, tmp_path):
        (tmp_path / "docker-compose.yml").write_text(
            "services:\n"
            "  pg:\n"
            "    image: postgres:15\n"
            "    environment:\n"
            "      POSTGRES_DB: mydb\n"
            "      POSTGRES_USER: pguser\n"
            "      POSTGRES_PASSWORD: pgpass\n"
            "    ports:\n"
            '      - "5433:5432"\n'
        )
        configs = detect_docker_compose(tmp_path)
        assert len(configs) >= 1
        assert "mydb" in configs[0].dsn
        assert "postgres" in configs[0].db_type


class TestDetectGoConfig:
    def test_yaml_database_block(self, tmp_path):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "database:\n"
            '  user: "root"\n'
            '  password: "secret"\n'
            '  name: "mydb"\n'
            '  host: "localhost"\n'
            '  port: "3306"\n'
        )
        configs = detect_go_config(tmp_path)
        assert len(configs) == 1
        assert "mydb" in configs[0].dsn

    def test_dsn_in_go_file(self, tmp_path):
        (tmp_path / "main.go").write_text(
            'var dsn = "postgres://u:p@h:5432/db"\n'
        )
        configs = detect_go_config(tmp_path)
        assert len(configs) == 1


class TestDetectGenericConfig:
    def test_cfg_file(self, tmp_path):
        private_dir = tmp_path / "private"
        private_dir.mkdir()
        (private_dir / "db_config.cfg").write_text(
            'MUSER="root"\n'
            'MPASS="secret"\n'
            'MHOST="localhost"\n'
        )
        configs = detect_generic_config(tmp_path)
        assert len(configs) >= 1
        assert "root" in configs[0].dsn

    def test_wordpress(self, tmp_path):
        (tmp_path / "wp-config.php").write_text(
            "<?php\n"
            "define('DB_NAME', 'wordpress');\n"
            "define('DB_USER', 'wp_user');\n"
            "define('DB_PASSWORD', 'wp_pass');\n"
            "define('DB_HOST', 'localhost');\n"
        )
        configs = detect_generic_config(tmp_path)
        assert len(configs) >= 1
        assert "wordpress" in configs[0].dsn


# ---------------------------------------------------------------------------
# detect_all
# ---------------------------------------------------------------------------


class TestDetectAll:
    def test_deduplicates(self, tmp_path):
        # Same DSN from .env and prisma
        prisma_dir = tmp_path / "prisma"
        prisma_dir.mkdir()
        (prisma_dir / "schema.prisma").write_text(
            'datasource db {\n  url = env("DATABASE_URL")\n}\n'
        )
        (tmp_path / ".env").write_text("DATABASE_URL=mysql://u:p@h/db\n")
        configs = detect_all(tmp_path)
        dsns = [c.dsn for c in configs]
        assert dsns.count("mysql://u:p@h/db") == 1

    def test_empty_directory(self, tmp_path):
        configs = detect_all(tmp_path)
        assert configs == []

    def test_multiple_sources(self, tmp_path):
        (tmp_path / ".env").write_text("DATABASE_URL=postgres://u:p@h/db1\n")
        (tmp_path / "docker-compose.yml").write_text(
            "services:\n"
            "  db:\n"
            "    environment:\n"
            "      MYSQL_DATABASE: db2\n"
            "    ports:\n"
            '      - "3306:3306"\n'
        )
        configs = detect_all(tmp_path)
        assert len(configs) == 2
