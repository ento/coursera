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
    # todo: test private/deleted thread
    # todo: test long threads
    # todo: test subforum filter
    def setUp(self):
        self.downloader = downloaders.ExternalDownloader(None, bin='mock')
        self.class_name = 'ml-001'

    def test_thread_download_requests(self):
        thread_data = {
            'crumbs': [{'title': 'Forums'}, {'title': 'General Discussion'}],
            'title': 'thread title',
        }

        # setup mocks
        download_mock = MagicMock(side_effect=[
            '',
            Exception(''),
        ])
        open_mock = mock_open(read_data=json.dumps(thread_data))
        open_mock.return_value.attach_mock(MagicMock(return_value='{'), 'peek')
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
        # should stop downloading thread at 2nd try
        download_mock.assert_has_calls([
            call(define.THREAD_URL.format(class_name=self.class_name, thread_id=1),
                 'ML-001/forum/json/1.json'),
            call(define.THREAD_URL.format(class_name=self.class_name, thread_id=2),
                 'ML-001/forum/json/2.json'),
        ])

    def test_thread_download_end_of_forum(self):
        # setup mocks
        download_mock = MagicMock(side_effect=[
            '',
        ])
        open_mock = mock_open(read_data='Unexpected API error')
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
        # should download thread only once
        download_mock.assert_called_once_with(
            define.THREAD_URL.format(class_name=self.class_name, thread_id=1),
            'ML-001/forum/json/1.json')

    def test_generate_forum(self):
        fixture_dir = os.path.join(os.path.dirname(__file__), 'fixtures', 'forum')
        json_dir = os.path.join(fixture_dir, 'json')
        json_fn = os.path.join(json_dir, '1.json')
        with open(json_fn) as f:
            open_mock = mock_open(read_data=f.read())
        copy_mock = MagicMock()
        call_mock = MagicMock()
        with patch('coursera.forum.get_json_dir', return_value=json_dir),\
             patch('coursera.forum.open', open_mock, create=True),\
             patch('shutil.copyfile', copy_mock),\
             patch('subprocess.call', call_mock):
            forum.generate_forum(self.class_name)
        # should write rst file
        open_mock.assert_any_call(json_fn)
        open_mock.assert_any_call(os.path.join('forum', 'rst', 'Video Lectures', 'Week 5 Lectures', '1_Egg and me.rst'), 'w')
        # should write sphinx conf
        copy_mock.assert_called_once_with(
            os.path.join(
                os.path.dirname(coursera_dl.__file__),
                'assets',
                'conf.py',
            ),
            os.path.join('forum', 'conf.py'))
        # should invoke sphinx-build
        call_mock.assert_called_once_with(
            ['sphinx-build', '-b', 'rst', 'html'],
            cwd='forum',
        )
