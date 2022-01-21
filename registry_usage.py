#!/bin/env python3

from __future__ import print_function
from collections import Counter

import os.path
import subprocess
import json


def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def get_items(item_type, namespace=None, refresh=False):
    cache_file = '/tmp/%s-%s.json' % (namespace, item_type)

    if refresh or not os.path.exists(cache_file):
        cmd = ['oc']
        if namespace:
            cmd.extend(['-n', namespace])
        cmd.extend(['get', item_type, '-o', 'json'])

        output = subprocess.check_output(cmd)
        open(cache_file, 'w').write(output)

    with open(cache_file) as fd:
        return json.load(fd)['items']


def get_item(item_type, item_name, namespace):
    cmd = ['oc', '-n', namespace, 'get', item_type, item_name, '-o', 'json']
    output = subprocess.check_output(cmd)
    return json.loads(output)


def get_registry_ip():
    # service = get_item('service', 'docker-registry', 'default')
    # ip = service['spec']['clusterIP']
    # port = service['spec']['ports'][0]['port']
    # return '%s:%s' % (ip, port)
    # Above no longer returns correct value :/
    return '0.0.0'


def main(refresh):
    print(subprocess.check_output(['oc', 'whoami', '-c']))

    registry_ip = get_registry_ip()

    print('Fetching all projects...')
    projects = get_items('projects', refresh=refresh)
    print('\t%d projects found' % len(projects))

    print('Fetching all images...')
    all_images = get_items(
        'images', 'default',
        refresh=refresh)  # Actually, gets from all namespaces
    all_images = {image['metadata']['name']: image for image in all_images}
    print('\t%d projects found' % len(projects))

    usages = dict()

    for project in projects:
        project_name = project['metadata']['name']
        print('Processing %s...' % project_name)
        image_streams = get_items('imagestreams', project_name, refresh=refresh)

        images = [
            all_images.get(tag_gen.get('image')) or {}
            for image_stream in image_streams
            for tag in image_stream['status'].get('tags') or []
            for tag_gen in tag.get('items') or []
        ]

        layers = {
            layer['name']: layer['size'] for image in images
            if image.get('dockerImageReference', '').startswith(registry_ip)
            for layer in image.get('dockerImageLayers') or []
        }

        usage = sum(size for name, size in layers.items())
        print('\tUsage: %s' % sizeof_fmt(usage))
        print('\tImages : %d' % len(images))

        usages[project_name] = usage

    print()
    print('Projects by usage:')
    for project_name, usage in sorted(usages.items(),
                                      key=lambda x: x[1],
                                      reverse=True):
        if not usage:
            continue
        print('\t%s\t%s' % (sizeof_fmt(usage), project_name))

    print()
    print('Total usage: %s' % sizeof_fmt(sum(usages.values())))


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description=
        'Compute image storage usage for container registry in an OpenShift cluster. '
        'Current "oc" session used.')

    parser.add_argument('--refresh',
                        default=False,
                        action='store_true',
                        help='Do not use cached OpenShift data')
    args = parser.parse_args()
    main(args.refresh)
