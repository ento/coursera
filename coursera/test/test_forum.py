#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test functionality of forum module.
"""

import os
import json
import unittest
from mock import call, mock_open, MagicMock, patch

from coursera import coursera_dl, downloaders, define, forum


class TestForum(unittest.TestCase):

    def setUp(self):
        self.downloader = downloaders.ExternalDownloader(None, bin='mock')
        self.class_name = 'ml-001'

    def _run_download_forum(self,
                             download_side_effect,
                             open_read_data):
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
                sleep_interval=None,
            )
        yield download_mock, open_mock

    def assert_single_download_call(self, download_mock):
        download_mock.assert_called_once_with(
            define.THREAD_URL.format(
                class_name=self.class_name,
                thread_id=1),
            'ML-001/forum/json/1-1.json')

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

    def test_generate_forum(self):
        fixture_dir = os.path.join(os.path.dirname(__file__), 'fixtures', 'forum')
        json_dir = os.path.join(fixture_dir, 'json')
        json_fn = os.path.join(json_dir, '1-1.json')
        json_fn_2 = os.path.join(json_dir, '1-2.json')
        with open(json_fn) as f:
            open_mock = mock_open(read_data=f.read())
        call_mock = MagicMock()
        with patch('coursera.forum.get_json_dir', return_value=json_dir),\
             patch('codecs.open', open_mock),\
             patch('os.path.isdir', return_value=False),\
             patch('os.path.isfile', return_value=False),\
             patch('coursera.utils.mkdir_p'),\
             patch('subprocess.call', call_mock):
            forum.generate_forum(self.class_name)
        # should write rst file
        base_dir = os.path.join('forum', 'rst')
        open_mock.assert_any_call(json_fn, 'r', 'utf-8')
        print open_mock.mock_calls
        open_mock.assert_any_call(json_fn_2, 'r', 'utf-8')
        open_mock.assert_any_call(os.path.join(base_dir, 'Video Lectures', 'Week 5 Lectures', '1_Egg_and_me.rst'), 'w', 'utf-8')
        # should write subforum index
        open_mock.assert_any_call(os.path.join(base_dir, 'Video Lectures', 'Week 5 Lectures', 'index.rst'), 'w', 'utf-8')
        open_mock.assert_any_call(os.path.join(base_dir, 'Video Lectures', 'index.rst'), 'w', 'utf-8')
        # should write global index
        open_mock.assert_any_call(os.path.join(base_dir, 'index.rst'), 'w', 'utf-8')
        # should write sphinx conf
        open_mock.assert_any_call(os.path.join(base_dir, 'conf.py'), 'w', 'utf-8')
        # should invoke sphinx-build
        call_mock.assert_called_once_with(
            ['sphinx-build', '-b', 'html', 'rst', 'html'],
            cwd='forum',
        )
