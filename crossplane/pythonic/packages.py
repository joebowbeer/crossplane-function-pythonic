
import base64
import importlib
import pathlib
import sys

import kopf


PACKAGES_DIR = None
GRPC_RUNNER = None

def setup(packages_dir, packages_runner):
    global PACKAGES_DIR, GRPC_RUNNER
    PACKAGES_DIR = packages_dir
    GRPC_RUNNER = packages_runner


@kopf.on.create('', 'v1', 'configmaps', labels={'function-pythonic.package': kopf.PRESENT})
@kopf.on.resume('', 'v1', 'configmaps', labels={'function-pythonic.package': kopf.PRESENT})
@kopf.on.create('', 'v1', 'secrets', labels={'function-pythonic.package': kopf.PRESENT})
@kopf.on.resume('', 'v1', 'secrets', labels={'function-pythonic.package': kopf.PRESENT})
async def create(body, logger, **_):
    package_dir, package = get_package_dir(body)
    if package_dir:
        package_dir.mkdir(parents=True, exist_ok=True)
        secret = body['kind'] == 'Secret'
        invalidate = False
        for name, text in body.get('data', {}).items():
            package_file = package_dir / name
            if secret:
                package_file.write_bytes(base64.b64decode(text.encode('utf-8')))
            else:
                package_file.write_text(text)
            if package_file.suffixes == ['.py']:
                module = '.'.join(package + [package_file.stem])
                GRPC_RUNNER.invalidate_module(module)
                logger.info(f"Created module: {module}")
            else:
                logger.info(f"Created file: {'/'.join(package + [name])}")


@kopf.on.update('', 'v1', 'configmaps', labels={'function-pythonic.package': kopf.PRESENT})
@kopf.on.update('', 'v1', 'secrets', labels={'function-pythonic.package': kopf.PRESENT})
async def update(body, old, logger, **_):
    old_package_dir, old_package = get_package_dir(old)
    if old_package_dir:
        old_data = old.get('data', {})
    else:
        old_data = {}
    old_names = set(old_data.keys())
    package_dir, package = get_package_dir(body, logger)
    if package_dir:
        package_dir.mkdir(parents=True, exist_ok=True)
        secret = body['kind'] == 'Secret'
        for name, text in body.get('data', {}).items():
            package_file = package_dir / name
            if package_dir == old_package_dir and text == old_data.get(name, None):
                action = 'Unchanged'
            else:
                if secret:
                    package_file.write_bytes(base64.b64decode(text.encode('utf-8')))
                else:
                    package_file.write_text(text)
                action = 'Updated' if package_dir == old_package_dir and name in old_names else 'Created'
            if package_file.suffixes == ['.py']:
                module = '.'.join(package + [package_file.stem])
                if action != 'Unchanged':
                    GRPC_RUNNER.invalidate_module(module)
                logger.info(f"{action} module: {module}")
            else:
                logger.info(f"{action} file: {'/'.join(package + [name])}")
            if package_dir == old_package_dir:
                old_names.discard(name)
    if old_package_dir:
        for name in old_names:
            package_file = old_package_dir / name
            package_file.unlink(missing_ok=True)
            if package_file.suffixes == ['.py']:
                module = '.'.join(old_package + [package_file.stem])
                GRPC_RUNNER.invalidate_module(module)
                logger.info(f"Removed module: {module}")
            else:
                logger.info(f"Removed file: {'/'.join(old_package + [name])}")
        while old_package and old_package_dir.is_dir() and not list(old_package_dir.iterdir()):
            old_package_dir.rmdir()
            module = '.'.join(old_package)
            GRPC_RUNNER.invalidate_module(module)
            logger.info(f"Removed package: {module}")
            old_package_dir = old_package_dir.parent
            old_package.pop()


@kopf.on.delete('', 'v1', 'configmaps', labels={'function-pythonic.package': kopf.PRESENT})
@kopf.on.delete('', 'v1', 'secrets', labels={'function-pythonic.package': kopf.PRESENT})
async def delete(old, logger, **_):
    package_dir, package = get_package_dir(old)
    if package_dir:
        for name in old.get('data', {}).keys():
            package_file = package_dir / name
            package_file.unlink(missing_ok=True)
            if package_file.suffixes == ['.py']:
                module = '.'.join(package + [package_file.stem])
                GRPC_RUNNER.invalidate_module(module)
                logger.info(f"Deleted module: {module}")
            else:
                logger.info(f"Deleted file: {'/'.join(package + [name])}")
        while package and package_dir.is_dir() and not list(package_dir.iterdir()):
            package_dir.rmdir()
            module = '.'.join(package)
            GRPC_RUNNER.invalidate_module(module)
            logger.info(f"Deleted package: {module}")
            package_dir = package_dir.parent
            package.pop()


def get_package_dir(body, logger=None):
    package = body.get('metadata', {}).get('labels', {}).get('function-pythonic.package', None)
    if package is None:
        if logger:
            logger.error('function-pythonic.package label is missing')
        return None, None
    package_dir = PACKAGES_DIR
    if package == '':
        package = []
    else:
        package = package.split('.')
        for segment in package:
            if not segment.isidentifier():
                if logger:
                    logger.error('Package has invalid package name: %s', package)
                return None, None
            package_dir = package_dir / segment
    return package_dir, package
