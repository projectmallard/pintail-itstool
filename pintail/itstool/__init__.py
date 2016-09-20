# pintail - Build static sites from collections of Mallard documents
# Copyright (c) 2016 Shaun McCance <shaunm@gnome.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import shutil
import subprocess

import pintail.translation
import pintail.site

class ItstoolTranslationProvider(pintail.translation.TranslationProvider):
    def __init__(self, site):
        pintail.translation.TranslationProvider.__init__(self, site)
        self._po_for_directory = {}
        self._mo_for_po = {}
        self._batched_dirs = {}

    def get_directory_langs(self, directory):
        langs = []
        pardir = os.path.dirname(directory.get_source_path())
        for d in os.listdir(pardir):
            pd = os.path.join(pardir, d)
            if os.path.isdir(pd):
                po = os.path.join(pd, d + '.po')
                if os.path.isfile(po):
                    self._po_for_directory.setdefault(directory, {})
                    self._po_for_directory[directory][d] = po
                    langs.append(d)
        if len(langs) > 0:
            return langs
        # FIXME:
        # otherwise, if -d po, use that
        # otherwise, if directory.parent, get_directory_langs(directory.parent)
        # otherwise, return []
        return []

    def translate_page(self, page, lang):
        if page.directory not in self._po_for_directory:
            return False
        if lang not in self._po_for_directory[page.directory]:
            return False
        pofile = self._po_for_directory[page.directory][lang]
        if pofile not in self._mo_for_po:
            pintail.site.Site._makedirs(page.directory.get_stage_path(lang))
            mofile = os.path.join(page.directory.get_stage_path(lang), lang + '.mo')
            subprocess.call(['msgfmt', '-o', mofile, pofile])
            self._mo_for_po[pofile] = mofile
        mofile = self._mo_for_po[pofile]

        if self.site.config.get('itstool_batch_dirs') == 'True':
            self._batched_dirs.setdefault(page.directory.path, [])
            if lang in self._batched_dirs[page.directory.path]:
                return True
            self._batched_dirs[page.directory.path].append(lang)
            self.site.log('TRANS', lang + ' ' + page.directory.path)
            cmd = ['itstool',
                   '--path', os.path.dirname(page.get_source_path()),
                   '-m', mofile,
                   '-o', page.directory.get_stage_path(lang)]
            cmd += [p.get_stage_path() for p in page.directory.pages]
            ret = subprocess.call(cmd)
            if ret != 0:
                self.site.logger.warn('Could not translate %s to %s' % (page.directory.path, lang))
                return False
            return True
        else:
            self.site.log('TRANS', lang + ' ' + page.site_id)
            ret = subprocess.call([
                'itstool',
                '--path', os.path.dirname(page.get_source_path()),
                '-m', mofile,
                '-o', page.get_stage_path(lang),
                page.get_stage_path()
            ])
            if ret != 0:
                self.site.logger.warn('Could not translate %s to %s' % (page.site_id, lang))
                return False
            return True

    def translate_media(self, directory, mediafile, lang):
        if directory not in self._po_for_directory:
            return False
        if lang not in self._po_for_directory[directory]:
            return False
        podir = os.path.dirname(self._po_for_directory[directory][lang])
        mfile = os.path.join(podir, mediafile)
        try:
            target = os.path.join(directory.get_stage_path(lang), mediafile)
            pintail.site.Site._makedirs(os.path.dirname(target))
            shutil.copyfile(mfile, target)
        except Exception as e:
            return False
        return True
