# -*- coding: utf-8 -*-


import os
import glob
import json
import shutil
import subprocess
from jinja2 import Environment, PackageLoader



env = Environment(loader=PackageLoader('coursera', 'templates'))


def get_forum_dir(class_name, stage, verbose_dirs=False):
    parts = ['forum', stage]
    if verbose_dirs:
        parts.insert(0, class_name.upper())
    return os.path.join(*parts)


def get_json_dir(class_name, verbose_dirs=False):
    return get_forum_dir(class_name, 'json', verbose_dirs)


def get_rst_dir(class_name, verbose_dirs=False):
    return get_forum_dir(class_name, 'rst', verbose_dirs)


def generate_forum(class_name, verbose_dirs=False):
    def secure_filename(s):
        return "".join([c for c in s if c.isalpha() or c.isdigit() or c==' ']).rstrip()

    def format_thread_fn(thread_id, title, crumbs):
        filename = '%d_%s.rst' % (thread_id, secure_filename(title))
        return os.path.join(rst_dir, *crumbs[1:]), filename

    # render threads
    json_dir = get_json_dir(class_name, verbose_dirs)
    rst_dir = get_rst_dir(class_name, verbose_dirs)
    template = env.get_template('forum/thread.rst')
    for json_fn in glob.glob(os.path.join(json_dir, '*.json')):
        try:
            with open(json_fn) as f:
                thread = json.load(f)
        except ValueError:
            continue
        crumbs = [crumb['title'] for crumb in thread['crumbs']]
        base_dir, filename = format_thread_fn(
            thread['id'],
            thread['title'],
            crumbs)
        if not os.path.isdir(base_dir):
            os.makedirs(base_dir)
        thread_fn = os.path.join(base_dir, filename)
        
        with open(thread_fn, 'w') as f:
            f.write(template.render(**thread))

    # copy conf
    shutil.copyfile(
        os.path.join(os.path.dirname(__file__), 'assets', 'conf.py'),
        os.path.join('forum', 'conf.py'),
    )

    # run sphinx-build
    subprocess.call(['sphinx-build', '-b', 'rst', 'html'], cwd='forum')
