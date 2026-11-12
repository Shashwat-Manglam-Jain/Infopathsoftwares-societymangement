from django.db import connection

try:
    from storages.backends.s3boto3 import S3Boto3Storage

    class TenantMediaStorage(S3Boto3Storage):
        """S3 storage that namespaces uploads under the current tenant schema.

        File structure: s3://<bucket>/media/<schema_name>/<upload_to_path>/<filename>
        e.g. s3://infosociety/media/demo_society/members/photos/M001.jpg
        """

        def _get_tenant_prefix(self):
            schema = getattr(connection, 'schema_name', 'public')
            return f'media/{schema}'

        def _save(self, name, content):
            name = f'{self._get_tenant_prefix()}/{name}'
            return super()._save(name, content)

        def url(self, name):
            if name and not name.startswith('media/'):
                name = f'{self._get_tenant_prefix()}/{name}'
            return super().url(name)

        def exists(self, name):
            if name and not name.startswith('media/'):
                name = f'{self._get_tenant_prefix()}/{name}'
            return super().exists(name)

        def delete(self, name):
            if name and not name.startswith('media/'):
                name = f'{self._get_tenant_prefix()}/{name}'
            return super().delete(name)

        def listdir(self, path):
            path = f'{self._get_tenant_prefix()}/{path}'
            return super().listdir(path)

except ImportError:
    TenantMediaStorage = None
