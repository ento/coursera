# -*- coding: utf-8 -*-
'''
Forum archive generator.

todo:

* long threads
* hyperlink
  https://class.coursera.org/ml-004/forum/list?forum_id=10001
  https://class.coursera.org/ml-004/forum/thread?thread_id=1129
* ssl handshake error
* subforum filter
* thread tags
* forum ordering (need to fetch forum info)

'''

import os
import datetime
import glob
import itertools
import operator
import codecs
import json
import logging
import shutil
import subprocess
import calendar
from jinja2 import Environment, PackageLoader, Markup, evalcontextfilter
import markdown
from . import utils


@evalcontextfilter
def post_to_html(eval_ctx, post, comment=False):
    text = post['post_text' if not comment else 'comment_text']
    if post['text_type'] == 'markdown':
        text = markdown.markdown(text)
    if eval_ctx.autoescape:
        text = Markup(text)
    return text


def epoch_to_local(value):
    return utc_to_local(datetime.datetime.utcfromtimestamp(value))


def utc_to_local(utc_dt):
    # get integer timestamp to avoid precision lost
    timestamp = calendar.timegm(utc_dt.timetuple())
    local_dt = datetime.datetime.fromtimestamp(timestamp)
    assert utc_dt.resolution >= datetime.timedelta(microseconds=1)
    return local_dt.replace(microsecond=utc_dt.microsecond)


def get_forum_dir(class_name, stage, verbose_dirs=False):
    parts = ['forum', stage]
    if verbose_dirs:
        parts.insert(0, class_name.upper())
    return os.path.join(*parts)


def get_json_dir(class_name, verbose_dirs=False):
    return get_forum_dir(class_name, 'json', verbose_dirs)


def get_rst_dir(class_name, verbose_dirs=False):
    return get_forum_dir(class_name, 'rst', verbose_dirs)


def get_jinja_env():
    env = Environment(loader=PackageLoader('coursera', 'templates'))
    env.filters['html'] = post_to_html
    env.filters['timestamp'] = epoch_to_local
    return env


def render_thread(template, thread):
    thread['comments_by_post'] = {
        key: list(comments)
        for key, comments in itertools.groupby(
                thread['comments'], operator.itemgetter('post_id'))}
    return thread_template.render(**thread)


def generate_forum(class_name, verbose_dirs=False, max_threads=None):
    def format_thread_fn(thread_id, title, crumbs):
        filename = '%d_%s.rst' % (thread_id, utils.clean_filename(title))
        return os.path.join(rst_dir, *crumbs[1:]), filename

    # render threads
    env = get_jinja_env()
    json_dir = get_json_dir(class_name, verbose_dirs)
    rst_dir = get_rst_dir(class_name, verbose_dirs)
    thread_template = env.get_template('forum/thread.rst')
    index_template = env.get_template('forum/index.rst')

    utils.mkdir_p(rst_dir)
    with open(os.path.join(rst_dir, 'index.rst'), 'w') as f:
        f.write(index_template.render(class_name=class_name))

    toctrees = dict()

    for i, json_fn in enumerate(glob.glob(os.path.join(json_dir, '*.json'))):
        if max_threads and i >= max_threads:
            break
        try:
            with codecs.open(json_fn, 'r', 'utf-8') as f:
                thread = json.load(f)
        except ValueError:
            continue
        base_dir, filename = format_thread_fn(
            thread['id'],
            thread['title'],
            [crumb['title'] for crumb in thread['crumbs']])
        utils.mkdir_p(base_dir)
        thread_fn = os.path.join(base_dir, filename)
        with codecs.open(thread_fn, 'w', 'utf-8') as f:
            f.write(render_thread(thread_template, thread))
        # build toctree
        basename, _ = os.path.splitext(filename)
        subforums = os.path.split(os.path.relpath(base_dir, rst_dir))
        toctree = toctrees
        for subforum in subforums:
            if not subforum:
                continue
            if subforum not in toctree:
                toctree[subforum] = dict()
            toctree = toctree[subforum]
        toctree[basename] = None
        logging.info('Wrote %s', thread_fn)

    get_value_type = lambda v: 0 if isinstance(v, dict) else 1
    def walk_tree(tree, path=[]):
        items = sorted([(get_value_type(v), k) for k, v in tree.iteritems()])
        yield path, items
        for _, key in items:
            subtree = tree[key]
            if not subtree:
                continue
            for subpath, entries in walk_tree(subtree, path + [key]):
                yield subpath, entries

    for path, entries in walk_tree(toctrees):
        base_dir = os.path.join(rst_dir, *path)
        index_fn = os.path.join(base_dir, 'index.rst')
        title = class_name
        if path:
            title = path[-1]
        with codecs.open(index_fn, 'w', 'utf-8') as f:
            index = index_template.render(title=title, crumbs=path, entries=entries)
            f.write(index)

    # copy conf
    for template_fn, dest_fn in [
            ('forum/conf.py', ['conf.py']),
            ('forum/custom.css', ['_static', 'custom.css']),
            ('forum/layout.html', ['_templates', 'layout.html']),
    ]:
        dest = os.path.join('forum', 'rst', *dest_fn)
        utils.mkdir_p(os.path.dirname(dest))
        with codecs.open(dest, 'w', 'utf-8') as f:
            f.write(env.get_template(template_fn).render(class_name=class_name))

    # run sphinx-build
    subprocess.call(['sphinx-build', '-b', 'html', 'rst', 'html'], cwd='forum')
