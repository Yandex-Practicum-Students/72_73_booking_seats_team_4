import json
import os
import sys

from fastapi.openapi.utils import get_openapi

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC_DIR = os.path.join(BASE_DIR, 'src')
for folder in (BASE_DIR, SRC_DIR):
    sys.path.insert(0, folder)

os.environ.setdefault('POSTGRES_USER', 'stub_user')
os.environ.setdefault('POSTGRES_PASSWORD', 'stub_pass')
os.environ.setdefault('POSTGRES_DB', 'stub_db')
os.environ.setdefault('JWT_SECRET', 'stub_jwt_secret_value_with_more_than_32_chars')
os.environ.setdefault('REDIS_PASSWORD', 'stub_redis_pass')

from src.main import app  # noqa: E402, I001


def build_docs() -> None:
    """Генерирует страницу с ддокументацией для Github Pages."""
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )

    current_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(current_dir, 'template.html')
    output_path = os.path.join(current_dir, 'index.html')

    with open(template_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    html_content = html_content.replace('{{ openapi_spec }}', json.dumps(openapi_schema))

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)


if __name__ == '__main__':
    build_docs()
