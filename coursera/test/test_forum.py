#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test functionality of forum module.
"""

import json
import unittest
from mock import call, mock_open, MagicMock, patch

from coursera import coursera_dl, downloaders, define


class TestForum(unittest.TestCase):

    def setUp(self):
        """
        As setup, we mock some methods that would, otherwise, create
        repeateadly many web requests.

        More specifically, we mock:

        * the search for hidden videos
        * the actual download of videos
        """
        self.m = mock_open()

    def test_thread_download_requests(self):
        # todo: test private thread
        # todo: test long threads
        # todo: test subforum filter
        downloader = downloaders.ExternalDownloader(None, bin='mock')
        class_name = 'ml-001'
        thread_data = {
            'crumbs': [{'title': 'Forums'}, {'title': 'General Discussion'}],
            'title': 'thread title',
        }
        # setup mocks
        download_mock = MagicMock(side_effect=[
            '',
            Exception(),
        ])
        gzip_open_mock = mock_open(read_data=json.dumps(thread_data))
        part_mock = MagicMock()
        part_name = part_mock.__enter__().name
        tempfile_mock = MagicMock()
        tempfile_mock.return_value = part_mock
        open_mock = MagicMock()
        # patch and call download_forum
        with patch('gzip.open', gzip_open_mock, create=True),\
            patch.object(downloader, 'download', download_mock),\
            patch('tempfile.NamedTemporaryFile', tempfile_mock, create=True),\
            patch('coursera.coursera_dl.open', open_mock):
            coursera_dl.download_forum(
                downloader,
                class_name,
                verbose_dirs=True,
                sleep_interval=None,
            )
        # should download thread
        download_mock.assert_has_calls([
            call(define.THREAD_URL.format(class_name=class_name, thread_id=1),
                 part_name),
            call(define.THREAD_URL.format(class_name=class_name, thread_id=2),
                 part_name),
        ])
        # should read downloaded file
        gzip_open_mock.assert_called_once_with(part_name, 'rb')
        # should copy to appropriate path
        open_mock.assert_called_once_with(
            part_name, 'ML-001/Forums/General Discussion/1_thread title.json')
