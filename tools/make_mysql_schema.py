"""Convert app/schema.sql (SQLite dialect) to MySQL/MariaDB: python tools/make_mysql_schema.py > mysql/schema_mysql.sql"""
import re
from pathlib import Path

src = (Path(__file__).resolve().parent.parent / "app" / "schema.sql").read_text(encoding="utf-8")
out = src.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "INT NOT NULL AUTO_INCREMENT PRIMARY KEY")
out = re.sub(r"\bINTEGER\b", "INT", out)
out = re.sub(r"\bREAL\b", "DOUBLE", out)
out = re.sub(r"\n\);", "\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;", out)
header = ("-- MySQL / MariaDB schema generated from app/schema.sql\n-- NOTE: generated mechanically and NOT executed against a MySQL server by the original author.\n"
          "-- Review, load into a test database first and run the checks in docs/DEPLOYMENT.md.\nSET FOREIGN_KEY_CHECKS=1;\n\n")
print(header + out)
