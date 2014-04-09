# -*- coding: utf-8 -*-
'''
Forum archive generator.

todo:

* retry on ssl handshake error
* download all pages from long threads? (currently maxed at 10)
* subforum filter?
* forum ordering? (need to fetch forum info)
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


hyperlink_re = re.compile(r'(https?://class.coursera.org)?/(?P<class_name>[-\w]+)/forum/(thread|list)\?(?P<type>thread|forum)_id=(?P<id>\d+)')
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
    return TOCNode.make_ref(ref_prefix='forum',
                            node_id=value['forum_id'],
                            title=value['title'])


def utc_to_local(utc_dt):
    # get integer timestamp to avoid precision lost
    timestamp = calendar.timegm(utc_dt.timetuple())
    local_dt = datetime.datetime.fromtimestamp(timestamp)
    assert utc_dt.resolution >= datetime.timedelta(microseconds=1)
    return local_dt.replace(microsecond=utc_dt.microsecond)


def get_forum_dir(class_name, stage, path='', verbose_dirs=False):
    parts = ['forum', stage]
    if verbose_dirs:
        parts.insert(0, class_name.upper())
    parts.insert(0, path)
    return os.path.join(*parts)


def get_json_dir(class_name, path='', verbose_dirs=False):
    return get_forum_dir(class_name, 'json', path, verbose_dirs)


def get_rst_dir(class_name, path='', verbose_dirs=False):
    return get_forum_dir(class_name, 'rst', path, verbose_dirs)


def get_jinja_env():
    env = Environment(loader=PackageLoader('coursera', 'templates'))
    env.filters['html'] = post_to_html
    env.filters['timestamp'] = epoch_to_local
    env.filters['forum_ref'] = crumb_to_forum_ref
    env.filters['escape_punctuation'] = escape_punctuation
    return env


def load_thread(thread_fn, load_pages=False):
    with codecs.open(thread_fn, 'r', 'utf-8') as f:
        thread = json.load(f)

    thread['title'] = thread['title'].strip()
    if not thread['title']:
        thread['title'] = 'untitled thread'

    if not load_pages:
        return thread

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


def render_thread(template, thread, context):
    prepare_thread(thread, context)
    return template.render(ref=context['ref'], **thread)


def prepare_thread(thread, context):
    for text_collection, text_key in [
            ('posts', 'post_text'),
            ('comments', 'comment_text'),
    ]:
        for text in thread[text_collection]:
            if text_key not in text:
                continue
            text[text_key] = replace_links(text[text_key], context)
    thread['comments_by_post'] = {
        key: list(comments)
        for key, comments in itertools.groupby(
                thread['comments'], operator.itemgetter('post_id'))}


def replace_links(s, context):
    s = hyperlink_re.sub(lambda matchobj: url_for(matchobj, context), s)
    return s


def url_for(matchobj, context):
    if matchobj.group('class_name') != context['class_name']:
        return matchobj.group(0)
    object_type = matchobj.group('type')
    object_key = 'threads' if object_type == 'thread' else 'forums'
    object_id = long(matchobj.group('id'))
    if object_id not in context[object_key]:
        return matchobj.group(0)
    return os.path.relpath(
        context[object_key][object_id].html_path,
        context['dirname'])


class TOCNode(dict):
    is_forum = False
    is_root = False
    ref_prefix = 'thread'

    @classmethod
    def make_ref(cls, **context):
        return u'{ref_prefix}_{node_id}'.format(**context)

    def __init__(self, node_id, title, path):
        super(TOCNode, self).__init__()
        self.node_id = node_id
        self.title = title
        self.path = path
        self.html_path = path.replace('rst', 'html')
        self.basename, _ = os.path.splitext(os.path.basename(path))
        self.ref = self.make_ref(ref_prefix=self.ref_prefix, **self.__dict__)

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
    ref_prefix = 'forum'

    def __init__(self, *args, **kwargs):
        super(TOCForumNode, self).__init__(*args, **kwargs)
        self.basename = self.path.split(os.sep)[-2] if os.sep in self.path else ''

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


class TOCRootNode(TOCForumNode):
    is_root = True


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


def build_toc_index(class_name, json_dir, rst_dir, max_threads=None):
    def format_thread_fn(thread_id, title, crumbs):
        filename = '%d_%s.rst' % (thread_id, utils.clean_filename(title))
        return os.path.join(rst_dir, *crumbs), filename

    root = TOCRootNode(0, class_name, 'index.html')
    index = {'threads': {}, 'forums': {}}
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
        thread_node = TOCThreadNode(thread['id'], thread['title'], thread_fn)
        index['threads'][thread['id']] = thread_node

        # build forum toctree
        toctree = root
        for i, subforum in enumerate(crumbs):
            forum_ref = crumb_to_forum_ref(subforum)
            if forum_ref not in toctree:
                forum_node = TOCForumNode(
                    subforum['forum_id'],
                    subforum['title'],
                    os.path.join(
                        rst_dir, 
                        *(map(operator.itemgetter('title'), crumbs[:i+1]) + ['index.rst'])),
                )
                toctree[forum_ref] = forum_node
                index['forums'][subforum['forum_id']] = forum_node
            toctree = toctree[forum_ref]
        toctree[thread_node.ref] = thread_node

        logging.info('Read %s', json_fn)
    return root, index


def generate_forum(class_name, path='', verbose_dirs=False, max_threads=None):
    # render threads
    env = get_jinja_env()
    json_dir = get_json_dir(class_name, path, verbose_dirs)
    rst_dir = get_rst_dir(class_name, path, verbose_dirs)
    thread_template = env.get_template('forum/thread.rst')
    index_template = env.get_template('forum/index.rst')

    utils.mkdir_p(rst_dir)

    toctree, index = build_toc_index(
        class_name,
        json_dir=json_dir,
        rst_dir=rst_dir,
        max_threads=max_threads)
    context = dict(
        class_name=class_name,
        **index)

    for i, json_fn in enumerate(glob.glob(os.path.join(json_dir, '*-1.json'))):
        if max_threads and i >= max_threads:
            break
        try:
            thread = load_thread(json_fn, load_pages=True)
        except ValueError:
            continue
        thread_node = index['threads'][thread['id']]
        utils.mkdir_p(os.path.dirname(thread_node.path))
        context['dirname'] = os.path.dirname(thread_node.html_path)
        context['ref'] = thread_node.ref

        with codecs.open(thread_node.path, 'w', 'utf-8') as f:
            f.write(render_thread(thread_template, thread, context))

        logging.info('Wrote %s', thread_node.path)

    def walk_tree(tree, path=[]):
        items = sorted([(v, k) for k, v in tree.iteritems()])
        yield tree, path, items
        for node, ref in items:
            if not node:
                continue
            for child, subpath, entries in walk_tree(node, path + [node]):
                yield child, subpath, entries

    for node, crumbs, entries in walk_tree(toctree):
        base_dir = os.path.join(rst_dir, *[node.title for node in crumbs])
        index_fn = os.path.join(base_dir, 'index.rst')
        with codecs.open(index_fn, 'w', 'utf-8') as f:
            index = index_template.render(
                is_root=node.is_root,
                ref=node.ref,
                title=node.title,
                crumbs=crumbs,
                entries=entries)
            f.write(index)

    # copy conf
    for template_fn, dest_fn in [
            ('forum/conf.py', ['conf.py']),
            ('forum/custom.css', ['_static', 'custom.css']),
            ('forum/layout.html', ['_templates', 'layout.html']),
            ('forum/Makefile', ['Makefile']),
            ('forum/make.bat', ['make.bat']),
    ]:
        dest = os.path.join(rst_dir, *dest_fn)
        utils.mkdir_p(os.path.dirname(dest))
        with codecs.open(dest, 'w', 'utf-8') as f:
            f.write(env.get_template(template_fn).render(class_name=class_name))

    # run sphinx-build
    subprocess.call(['sphinx-build', '-b', 'html', 'rst', 'html'],
                    cwd=os.path.dirname(rst_dir))
