#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test functionality of forum module.
"""

import os
import json
import unittest
from nose.tools import ok_, eq_
from mock import call, mock_open, MagicMock, patch

from coursera import coursera_dl, downloaders, define, forum


class TestForum(unittest.TestCase):

    def setUp(self):
        self.downloader = downloaders.ExternalDownloader(None, bin='mock')
        self.class_name = 'ml-001'

    def _run_download_forum(self,
                            download_side_effect,
                            open_read_data,
                            **kwargs):
        # setup mocks
        download_mock = MagicMock(side_effect=download_side_effect)
        open_mock = mock_open(read_data=open_read_data)
        # patch and call download_forum
        with patch.object(self.downloader, 'download', download_mock),\
             patch('os.path.isfile', return_value=True),\
            patch('coursera.coursera_dl.open', open_mock, create=True):
            coursera_dl.download_forum(
                self.downloader,
                self.class_name,
                verbose_dirs=True,
                wait_time=None,
                **kwargs)
        yield download_mock, open_mock

    def assert_single_download_call(self, download_mock, path_prefix=''):
        download_mock.assert_called_once_with(
            define.THREAD_URL.format(
                class_name=self.class_name,
                thread_id=1),
            os.path.join(path_prefix, 'ML-001/forum/json/1-1.json'))

    def assert_two_download_calls(self, download_mock):
        download_mock.assert_has_calls([
            call(define.THREAD_URL.format(
                class_name=self.class_name,
                thread_id=1),
                 'ML-001/forum/json/1-1.json'),
            call(define.THREAD_URL.format(
                class_name=self.class_name,
                thread_id=2),
                 'ML-001/forum/json/2-1.json'),
        ])

    def assert_paginated_download_calls(self, download_mock):
        download_mock.assert_has_calls([
            call(define.THREAD_URL.format(
                class_name=self.class_name,
                thread_id=1),
                 'ML-001/forum/json/1-1.json'),
            call(define.THREAD_URL.format(
                class_name=self.class_name,
                thread_id=1) + '?post_id=4&position=after',
                 'ML-001/forum/json/1-2.json'),
            call(define.THREAD_URL.format(
                class_name=self.class_name,
                thread_id=2),
                 'ML-001/forum/json/2-1.json'),
        ])

    def test_thread_download_single_page(self):
        thread_data = {
            'crumbs': [{'title': 'Forums'}, {'title': 'General Discussion'}],
            'title': 'thread title',
        }
        for download_mock, open_mock in self._run_download_forum(
                download_side_effect=[
                    '',
                    Exception(''),
                ],
                open_read_data=json.dumps(thread_data),
        ):
            # should stop downloading thread at 2nd try
            self.assert_two_download_calls(download_mock)

    def test_thread_download_two_pages(self):
        thread_data = {
            'crumbs': [{'title': 'Forums'}, {'title': 'General Discussion'}],
            'title': 'thread title',
            'posts': [
                {'id': 1, 'order': 1},
                {'id': 2, 'order': 2, 'thread_id': 1},
                {'id': 3, 'order': 3, 'thread_id': 1},
                {'id': 4, 'order': 4},
                {'id': 5, 'order': 5},
            ],
            'num_pages': 2,
        }
        for download_mock, open_mock in self._run_download_forum(
                download_side_effect=[
                    '',
                    '',
                    Exception(''),
                ],
                open_read_data=json.dumps(thread_data),
        ):
            # should stop downloading thread at 2nd try
            self.assert_paginated_download_calls(download_mock)

    def test_thread_download_skip_private_thread(self):
        for download_mock, open_mock in self._run_download_forum(
                download_side_effect=[''],
                open_read_data='This thread is marked private',
        ):
            # should skip the first
            self.assert_two_download_calls(download_mock)

    def test_thread_download_skip_deleted_thread(self):
        for download_mock, open_mock in self._run_download_forum(
                download_side_effect=[''],
                open_read_data='This thread is deleted',
        ):
            # should skip the first
            self.assert_two_download_calls(download_mock)

    def test_thread_download_end_of_forum(self):
        for download_mock, open_mock in self._run_download_forum(
                download_side_effect=[''],
                open_read_data='Unexpected API error',
        ):
            self.assert_single_download_call(download_mock)

    def test_thread_download_path(self):
        for download_mock, open_mock in self._run_download_forum(
                download_side_effect=[''],
                open_read_data='Unexpected API error',
                path='custom_path',
        ):
            self.assert_single_download_call(download_mock, 'custom_path')

    def test_generate_forum(self):
        fixture_dir = os.path.join(os.path.dirname(__file__), 'fixtures')
        json_dir = os.path.join(fixture_dir, 'forum', 'json')
        json_fn = os.path.join(json_dir, '1-1.json')
        json_fn_2 = os.path.join(json_dir, '1-2.json')
        with open(json_fn) as f:
            open_mock = mock_open(read_data=f.read())
        call_mock = MagicMock()
        with patch('codecs.open', open_mock),\
             patch('os.path.isdir', return_value=False),\
             patch('os.path.isfile', return_value=False),\
             patch('coursera.utils.mkdir_p'),\
             patch('subprocess.call', call_mock):
            forum.generate_forum(self.class_name, path=fixture_dir)
        # should write rst file
        forum_dir = os.path.join(fixture_dir, 'forum')
        rst_dir = os.path.join(forum_dir, 'rst')
        open_mock.assert_any_call(json_fn, 'r', 'utf-8')
        open_mock.assert_any_call(json_fn_2, 'r', 'utf-8')
        open_mock.assert_any_call(os.path.join(rst_dir, 'Video_Lectures', 'Week_5_Lectures', '1_Egg_and_me.rst'), 'w', 'utf-8')
        # should write subforum index
        open_mock.assert_any_call(os.path.join(rst_dir, 'Video_Lectures', 'Week_5_Lectures', 'index.rst'), 'w', 'utf-8')
        open_mock.assert_any_call(os.path.join(rst_dir, 'Video_Lectures', 'index.rst'), 'w', 'utf-8')
        # should write global index
        open_mock.assert_any_call(os.path.join(rst_dir, 'index.rst'), 'w', 'utf-8')
        # should write sphinx conf
        open_mock.assert_any_call(os.path.join(rst_dir, 'conf.py'), 'w', 'utf-8')
        open_mock.assert_any_call(os.path.join(rst_dir, 'Makefile'), 'w', 'utf-8')
        open_mock.assert_any_call(os.path.join(rst_dir, 'make.bat'), 'w', 'utf-8')
        # should invoke sphinx-build
        call_mock.assert_called_once_with(
            'sphinx-build -b html rst html',
            shell=True,
            cwd=forum_dir,
        )

    def test_load_thread_strips_whitespaces_etc(self):
        thread_data = {
            'title': ' ',
            'crumbs': [
                {'title': '  no: whitespace around me?\<>*?|:;/"^ '},
                {'title': '   '},
                {'title': u'\u2211a\u2099'},
            ]
        }
        open_mock = mock_open(read_data=json.dumps(thread_data))
        with patch('codecs.open', open_mock):
            thread = forum.load_thread('test.json')
        eq_('untitled thread', thread['title'])
        eq_('no: whitespace around me?\<>*?|:;/"^', thread['crumbs'][0]['title'])
        eq_('no-_whitespace_around_me------------', thread['crumbs'][0]['fssafe_title'])
        eq_('untitled forum', thread['crumbs'][1]['title'])
        eq_('-a-', thread['crumbs'][2]['fssafe_title'])

    def test_prepare_thread_thread_hyperlinking(self):
        thread = {
            'comments': [
                {
                    'post_id': 1,
                    'title': 'link to parent thread',
                    'post_text': '<a href="https://class.coursera.org/ml-001/forum/thread?thread_id=10"></a>',
                },
                {
                    'post_id': 1,
                    'title': 'link to cousin thread',
                    'post_text': '<a href="/ml-001/forum/thread?thread_id=11"></a>',
                },
                {
                    'post_id': 1,
                    'title': 'link to sibling thread',
                    'post_text': '/ml-001/forum/thread?thread_id=12',
                },
                {
                    'post_id': 1,
                    'title': 'link to child thread',
                    'post_text': '[here](/ml-001/forum/thread?thread_id=13)',
                },
                {
                    'post_id': 1,
                    'title': 'link to non-existent thread',
                    'post_text': '[here](https://class.coursera.org/ml-001/forum/thread?thread_id=14)',
                },
                {
                    'post_id': 1,
                    'title': 'link to thread from another class',
                    'post_text': '[here](https://class.coursera.org/ml-002/forum/thread?thread_id=10)',
                },
            ],
        }
        thread['posts'] = thread['comments']
        context = {
            'class_name': self.class_name,
            'dirname': 'Subforum',
            'threads': {
                10: forum.TOCThreadNode(10, '', '10_parent.rst'),
                11: forum.TOCThreadNode(11, '', 'Parent Forum/11_cousin.rst'),
                12: forum.TOCThreadNode(12, '', 'Subforum/12_sibling.rst'),
                13: forum.TOCThreadNode(13, '', 'Subforum/Sibling Forum/13_nephew.rst'),
            }
        }
        forum.prepare_thread(thread, context)
        for key in ['posts', 'comments']:
            ok_('../10_parent.html' in thread[key][0]['post_text'])
            ok_('../Parent Forum/11_cousin.html' in thread[key][1]['post_text'])
            ok_('12_sibling.html' in thread[key][2]['post_text'])
            ok_('Sibling Forum/13_nephew.html' in thread[key][3]['post_text'])
            ok_('thread_id=14' in thread[key][4]['post_text'])
            ok_('thread_id=10' in thread[key][5]['post_text'])

    def test_prepare_thread_forum_hyperlinking(self):
        thread = {
            'comments': [
                {
                    'post_id': 1,
                    'title': 'link to parent forum',
                    'post_text': '<a href="https://class.coursera.org/ml-001/forum/list?forum_id=10"></a>',
                },
                {
                    'post_id': 1,
                    'title': 'link to cousin forum',
                    'post_text': '<a href="/ml-001/forum/list?forum_id=11"></a>',
                },
                {
                    'post_id': 1,
                    'title': 'link to sibling forum',
                    'post_text': '/ml-001/forum/list?forum_id=12',
                },
                {
                    'post_id': 1,
                    'title': 'link to nephew forum',
                    'post_text': '[here](/ml-001/forum/list?forum_id=13)',
                },
                {
                    'post_id': 1,
                    'title': 'link to non-existent forum',
                    'post_text': '[here](https://class.coursera.org/ml-001/forum/list?forum_id=14)',
                },
                {
                    'post_id': 1,
                    'title': 'link to forum from another class',
                    'post_text': '[here](https://class.coursera.org/ml-002/forum/list?forum_id=10)',
                },
            ],
        }
        thread['posts'] = thread['comments']
        context = {
            'class_name': self.class_name,
            'dirname': 'Subforum',
            'forums': {
                10: forum.TOCForumNode(10, '', 'Parent Forum/index.rst'),
                11: forum.TOCForumNode(11, '', 'Parent Forum/Cousin Forum/index.rst'),
                12: forum.TOCForumNode(12, '', 'Subforum/Sibling Forum/index.rst'),
                13: forum.TOCForumNode(13, '', 'Subforum/Sibling Forum/Nephew Forum/index.rst'),
            }
        }
        forum.prepare_thread(thread, context)
        for key in ['posts', 'comments']:
            ok_('../Parent Forum/index.html' in thread[key][0]['post_text'])
            ok_('../Parent Forum/Cousin Forum/index.html' in thread[key][1]['post_text'])
            ok_('Sibling Forum/index.html' in thread[key][2]['post_text'])
            ok_('Sibling Forum/Nephew Forum/index.html' in thread[key][3]['post_text'])
            ok_('forum_id=14' in thread[key][4]['post_text'])
            ok_('forum_id=10' in thread[key][5]['post_text'])


    def test_escape_punctutation(self):
        eq_('a\\*', forum.escape_punctuation('a*'))
