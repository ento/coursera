# -*- coding: utf-8 -*-
'''
Forum archive generator.

todo:

* readme
* hyperlink
  https://class.coursera.org/ml-004/forum/list?forum_id=10001
  https://class.coursera.org/ml-004/forum/thread?thread_id=1129
* retry on ssl handshake error
* subforum filter?
* forum ordering? (need to fetch forum info)
* thread tags?
* download all pages from long threads? (currently maxed at 10)
'''

import os
import datetime
import re
import glob
import itertools
import operator
import codecs
import string
import json
import logging
import shutil
import subprocess
import calendar
from jinja2 import Environment, PackageLoader, Markup, evalcontextfilter
import markdown
from . import utils


punctuation_re = re.compile(r'([{}])'.format(string.punctuation))


def escape_punctuation(s):
    return punctuation_re.sub(r'\\\1', s)


@evalcontextfilter
def post_to_html(eval_ctx, post, is_comment=False):
    text = post['post_text' if not is_comment else 'comment_text']
    if post['text_type'] == 'markdown':
        text = markdown.markdown(text)
    if eval_ctx.autoescape:
        text = Markup(text)
    return text


def epoch_to_local(value):
    return utc_to_local(datetime.datetime.utcfromtimestamp(value))


def crumb_to_forum_ref(value):
    return 'forum_{forum_id}_{title}'.format(**value)


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
    env.filters['forum_ref'] = crumb_to_forum_ref
    env.filters['escape_punctuation'] = escape_punctuation
    return env


def load_thread(thread_fn):
    with codecs.open(thread_fn, 'r', 'utf-8') as f:
        thread = json.load(f)
    thread['title'] = thread['title'].strip()
    if not thread['title']:
        thread['title'] = 'untitled thread'
    thread['ref'] = 'thread_{id}_{title}'.format(**thread)
    page_pattern = os.path.join(
        os.path.dirname(thread_fn),
        '{0}-*.json'.format(thread['id']))
    basename = os.path.basename(thread_fn)
    for page_fn in glob.glob(page_pattern):
        if os.path.basename(page_fn) == basename:
            continue
        try:
            with codecs.open(page_fn, 'r', 'utf-8') as f:
                page = json.load(f)
        except ValueError:
            continue
        for post in page['posts']:
            if 'thread_id' not in post:
                continue
            thread['posts'].append(post)
        for comment in page['comments']:
            if 'post_id' not in comment:
                continue
            thread['comments'].append(comment)
    return thread


def render_thread(template, thread):
    thread['comments_by_post'] = {
        key: list(comments)
        for key, comments in itertools.groupby(
                thread['comments'], operator.itemgetter('post_id'))}
    return template.render(**thread)


class TOCNode(dict):
    is_forum = False

    def __init__(self, node_id, ref, title, filename):
        super(TOCNode, self).__init__()
        self.node_id = node_id
        self.ref = ref
        self.title = title
        self.filename = filename
    def __lt__(self, other):
        return self.ref < other.ref
    def __le__(self, other):
        return self.ref <= other.ref
    def __eq__(self, other):
        return self.ref == other.ref
    def __ne__(self, other):
        return self.ref != other.ref
    def __gt__(self, other):
        return self.ref > other.ref
    def __ge__(self, other):
        return self.ref >= other.ref


class TOCForumNode(TOCNode):
    is_forum = True

    def __lt__(self, other):
        if isinstance(other, TOCThreadNode):
            return True
        return super(TOCForumNode, self).__lt__(other)
    def __le__(self, other):
        if isinstance(other, TOCThreadNode):
            return True
        return super(TOCForumNode, self).__lt__(other)
    def __gt__(self, other):
        if isinstance(other, TOCThreadNode):
            return False
        return super(TOCForumNode, self).__lt__(other)
    def __ge__(self, other):
        if isinstance(other, TOCThreadNode):
            return False
        return super(TOCForumNode, self).__lt__(other)


class TOCThreadNode(TOCNode):
    def __lt__(self, other):
        if isinstance(other, TOCForumNode):
            return False
        return super(TOCThreadNode, self).__lt__(other)
    def __le__(self, other):
        if isinstance(other, TOCForumNode):
            return False
        return super(TOCThreadNode, self).__lt__(other)
    def __gt__(self, other):
        if isinstance(other, TOCForumNode):
            return True
        return super(TOCThreadNode, self).__lt__(other)
    def __ge__(self, other):
        if isinstance(other, TOCForumNode):
            return True
        return super(TOCThreadNode, self).__lt__(other)


def generate_forum(class_name, verbose_dirs=False, max_threads=None):
    def format_thread_fn(thread_id, title, crumbs):
        filename = '%d_%s.rst' % (thread_id, utils.clean_filename(title))
        return os.path.join(rst_dir, *crumbs), filename

    # render threads
    env = get_jinja_env()
    json_dir = get_json_dir(class_name, verbose_dirs)
    rst_dir = get_rst_dir(class_name, verbose_dirs)
    thread_template = env.get_template('forum/thread.rst')
    index_template = env.get_template('forum/index.rst')

    utils.mkdir_p(rst_dir)
    with open(os.path.join(rst_dir, 'index.rst'), 'w') as f:
        f.write(index_template.render(class_name=class_name))

    toctrees = TOCForumNode(0, class_name, class_name, 'index')

    for i, json_fn in enumerate(glob.glob(os.path.join(json_dir, '*-1.json'))):
        if max_threads and i >= max_threads:
            break
        try:
            thread = load_thread(json_fn)
        except ValueError:
            continue
        crumbs = thread['crumbs'][1:]
        base_dir, filename = format_thread_fn(
            thread['id'],
            thread['title'],
            [crumb['title'] for crumb in crumbs])
        utils.mkdir_p(base_dir)
        thread_fn = os.path.join(base_dir, filename)
        with codecs.open(thread_fn, 'w', 'utf-8') as f:
            f.write(render_thread(thread_template, thread))
        # build toctree
        basename, _ = os.path.splitext(filename)
        toctree = toctrees
        for subforum in crumbs:
            forum_ref = crumb_to_forum_ref(subforum)
            if forum_ref not in toctree:
                toctree[forum_ref] = TOCForumNode(subforum['forum_id'], forum_ref, subforum['title'], subforum['title'])
            toctree = toctree[forum_ref]
        toctree[thread['ref']] = TOCThreadNode(thread['id'], thread['ref'], thread['title'], basename)
        logging.info('Wrote %s', thread_fn)

    def walk_tree(tree, path=[]):
        items = sorted([(v, k) for k, v in tree.iteritems()])
        yield tree, path, items
        for subtree, ref in items:
            if not subtree:
                continue
            for tree, subpath, entries in walk_tree(subtree, path + [subtree]):
                yield tree, subpath, entries

    for tree, crumbs, entries in walk_tree(toctrees):
        base_dir = os.path.join(rst_dir, *[node.title for node in crumbs])
        index_fn = os.path.join(base_dir, 'index.rst')
        with codecs.open(index_fn, 'w', 'utf-8') as f:
            index = index_template.render(
                ref=tree.ref,
                title=tree.title,
                crumbs=crumbs,
                entries=entries)
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
