# whatlastgenre
# Improves genre metadata of audio files
# based on tags from various music sites.
#
# Copyright (c) 2012-2015 YetAnotherNerd
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

'''whatlastgenre beets plugin'''

from __future__ import absolute_import, division, print_function

from argparse import Namespace

from beets import config
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand, decargs
from beetsplug.lastgenre import WHITELIST as BEET_LG_WHITELIST

from wlg import whatlastgenre
from wlg.whatlastgenre import print_progressbar


class WhatLastGenre(BeetsPlugin):
    '''First version of the whatlastgenre plugin for beets.'''

    def __init__(self):
        super(WhatLastGenre, self).__init__()
        self.config.add({
            'auto': False,
            'force': False,
            'count': 4,
            'separator': u', ',
            'whitelist': u'wlg',  # wlg, beets or custom path
        })
        if self.config['auto'].get(bool):
            self.import_stages = [self.imported]
        self.wlg = None

    def lazy_setup(self, cache=False, verbose=0):
        self.wlg = whatlastgenre.WhatLastGenre(Namespace(
            tag_limit=self.config['count'].get(int),
            update_cache=cache, verbose=verbose,
            interactive=False, dry=False, difflib=False, tag_release=False))
        whitelist = self.config['whitelist'].get()
        if not whitelist:
            whitelist = 'wlg'
        if whitelist != 'wlg':
            if whitelist == 'beets':
                whitelist = BEET_LG_WHITELIST
            self.wlg.read_whitelist(whitelist)
        self._log.debug(u'use {0} whitelist with {1} entries.',
                        whitelist, len(self.wlg.whitelist))

    def commands(self):
        cmds = Subcommand('wlg', help='get genres with whatlastgenre')
        cmds.parser.add_option('-v', '--verbose', dest='verbose',
                               action='count', default=0,
                               help='verbose output (-vv for debug)')
        cmds.parser.add_option('-f', '--force', dest='force',
                               action='store_true', default=False,
                               help='force overwrite existing genres')
        cmds.parser.add_option('-u', '--update-cache', dest='cache',
                               action='store_true', default=False,
                               help='force update cache')
        cmds.func = self.commanded
        return [cmds]

    def commanded(self, lib, opts, args):
        if not self.wlg:
            self.lazy_setup(opts.cache, opts.verbose)
        if opts.force:
            self.config['force'] = True
        write = config['import']['write'].get(bool)
        self.config.set_args(opts)
        albums = lib.albums(decargs(args))
        i = len(albums)
        try:
            for i, album in enumerate(albums, start=1):
                print_progressbar(i, len(albums))
                album.genre = self.genres(album)
                album.store()
                for item in album.items():
                    item.genre = album.genre
                    item.store()
                    if write:
                        item.try_write()
        except KeyboardInterrupt:
            print()
        self.wlg.print_stats(i)

    def imported(self, session, task):
        if not self.wlg:
            self.lazy_setup()
        if task.is_album:
            genres = self.genres(task.album)
            task.album.genre = genres
            task.album.store()
            for item in task.album.items():
                item.genre = genres
                item.store()
        else:
            genres = self.genres(task.item.get_album())
            item.genre = genres
            item.store()

    def genres(self, album):
        if self.config['force'] or not album.genre:
            metadata = whatlastgenre.Metadata(
                path=album.item_dir(), type='beet',
                artists=[(t.artist, t.mb_artistid) for t in album.items()],
                albumartist=(album.albumartist, album.mb_albumartistid),
                album=album.album, mbid_album=album.mb_albumid,
                mbid_relgrp=album.mb_releasegroupid,
                year=album.year, releasetype=album.albumtype)
            genres, _ = self.wlg.query_album(metadata)
            genres = self.config['separator'].get(unicode).join(genres)
            self._log.info(u'genres for album {0}: {1}', album, genres)
            return genres
        else:
            self._log.info(u'not forcing genre update for album {0}', album)
        return album.genre